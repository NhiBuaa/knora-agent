"""Evaluation-only Free admission and counters; no monetary budget framework."""

import json
import os
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

from evals.runners.pdf_source_binding import digest


class FreeOnlyGuard:
    def __init__(self, path: Path, *, run_identity, preflight, clock=None):
        self.path, self.clock = path, clock or (lambda: datetime.now(UTC))
        self.lock = threading.Lock()
        now = self.clock()
        checked = datetime.fromisoformat(preflight["checked_at"])
        if (
            preflight.get("plan") != "Workers Free"
            or checked.tzinfo is None
            or checked.date() != now.date()
            or not timedelta(0) <= now - checked <= timedelta(minutes=15)
            or type(preflight.get("neurons_used")) is not int
            or not 0 <= preflight["neurons_used"] < 10000
            or preflight.get("daily_limit") != 10000
            or preflight.get("models_free_eligible") is not True
            or preflight.get("no_paid_gateway") is not True
            or not preflight.get("evidence")
        ):
            raise ValueError("fresh verified Cloudflare Free/quota evidence required")
        self.account_id = preflight["account_id"]
        self.preflight = preflight
        identity = digest(run_identity | {"cloudflare_account_id": self.account_id})
        self.state = (
            json.loads(path.read_text())
            if path.exists()
            else {
                "identity_sha256": identity,
                "generation_attempts": 0,
                "embedding_inputs": 0,
                "paused_until": None,
                "stop_reason": None,
            }
        )
        if self.state["identity_sha256"] != identity:
            raise ValueError("counter baseline identity mismatch")
        for key in ("generation_attempts", "embedding_inputs"):
            if type(self.state[key]) is not int or self.state[key] < 0:
                raise ValueError("invalid persisted request counter")
        self.state["run_identity"] = run_identity
        if self.state["stop_reason"] == "FREE_PREFLIGHT_EXPIRED":
            self.state["stop_reason"] = None
        if self.state["paused_until"] and now >= datetime.fromisoformat(self.state["paused_until"]):
            self.state["paused_until"] = None
            if self.state["stop_reason"] == "QUOTA_PAUSED":
                self.state["stop_reason"] = None
        self.state["free_preflight"] = preflight
        self.save()

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(self.state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        os.replace(temporary, self.path)

    def before_request(self, request):
        with self.lock:
            now = self.clock()
            if self.state["stop_reason"] in {"REQUEST_LIMIT", "FREE_ACCESS_DENIED"}:
                raise RuntimeError(self.state["stop_reason"])
            if self.state["paused_until"] and now < datetime.fromisoformat(
                self.state["paused_until"]
            ):
                raise RuntimeError("QUOTA_PAUSED")
            if now.date() != datetime.fromisoformat(self.preflight["checked_at"]).date():
                self.state["stop_reason"] = "FREE_PREFLIGHT_EXPIRED"
                self.save()
                raise RuntimeError("FREE_PREFLIGHT_EXPIRED")
            base = f"/client/v4/accounts/{self.account_id}/ai"
            if (
                request.method != "POST"
                or request.url.host != "api.cloudflare.com"
                or request.url.scheme != "https"
                or request.url.query
            ):
                raise RuntimeError("AI_ENDPOINT_NOT_APPROVED")
            if any(key.startswith("cf-aig") for key in request.headers):
                raise RuntimeError("AI_ENDPOINT_NOT_APPROVED")
            payload = json.loads(request.content)
            if request.url.path == f"{base}/run/@cf/qwen/qwen3-embedding-0.6b":
                texts = payload.get("documents", payload.get("queries"))
                if (
                    not isinstance(texts, list)
                    or not 1 <= len(texts) <= 32
                    or any(not isinstance(s, str) for s in texts)
                ):
                    raise RuntimeError("EMBEDDING_REQUEST_INVALID")
                key, count, maximum = "embedding_inputs", len(texts), 2500
            elif (
                request.url.path == f"{base}/v1/chat/completions"
                and payload.get("model") == "@cf/openai/gpt-oss-20b"
                and payload.get("max_tokens") == 1024
            ):
                key, count, maximum = "generation_attempts", 1, 70
            else:
                raise RuntimeError("AI_ENDPOINT_NOT_APPROVED")
            if self.state[key] + count > maximum:
                self.state["stop_reason"] = "REQUEST_LIMIT"
                self.save()
                raise RuntimeError("REQUEST_LIMIT")
            self.state[key] += count
            self.state["paused_until"] = None
            self.state["stop_reason"] = None
            self.save()

    def after_response(self, response):
        if response.status_code in {402, 403, 429}:
            with self.lock:
                tomorrow = self.clock().replace(
                    hour=0, minute=0, second=0, microsecond=0
                ) + timedelta(days=1)
                self.state["paused_until"] = (
                    tomorrow.isoformat() if response.status_code == 429 else None
                )
                self.state["stop_reason"] = (
                    "QUOTA_PAUSED" if response.status_code == 429 else "FREE_ACCESS_DENIED"
                )
                self.save()

    async def before_async_request(self, request):
        self.before_request(request)

    async def after_async_response(self, response):
        self.after_response(response)


def build_evaluation_app(
    *, embedding_provider, generation_provider, embedding_configuration, objects_root, authenticator
):
    """Use current composition seams; every application AI caller shares guarded clients."""
    from knora.adapters.execution.thread_attempt_runner import FixedCapacityThreadAttemptRunner
    from knora.adapters.object_store.filesystem import FileSystemObjectStore
    from knora.adapters.pdf.pypdf import PypdfTextExtractor
    from knora.adapters.postgres.answering_store import PostgresAnsweringStore
    from knora.adapters.postgres.database import SessionFactory
    from knora.adapters.postgres.ingestion_job_store import PostgresIngestionJobStore
    from knora.adapters.postgres.ingestion_store import PostgresIngestionStore
    from knora.adapters.postgres.workspace_admission import PostgresWorkspaceAdmissionStore
    from knora.answering.module import AnswerQuestion
    from knora.answering.stores import RetrievalConfiguration
    from knora.ingestion.job_processing import (
        AttemptTimingV1,
        PdfDerivationHandler,
        ProcessIngestionJob,
        RetryPolicyV1,
        SystemRandomSource,
        UuidOperationIds,
    )
    from knora.ingestion.module import IngestDocument
    from knora.ingestion.processing import DocumentProcessor
    from knora.main import create_app

    jobs = PostgresIngestionJobStore(SessionFactory)
    admissions = PostgresWorkspaceAdmissionStore(SessionFactory)
    objects = FileSystemObjectStore(objects_root)
    return create_app(
        embedding_configuration=embedding_configuration,
        keycloak_authenticator=authenticator,
        object_store=objects,
        ingest_document=IngestDocument(
            processor=DocumentProcessor(),
            embedding_provider=embedding_provider,
            store=PostgresIngestionStore(SessionFactory),
            admission_store=admissions,
        ),
        answer_question=AnswerQuestion(
            embedding_provider=embedding_provider,
            generation_provider=generation_provider,
            store=PostgresAnsweringStore(SessionFactory),
            embedding_configuration=embedding_configuration,
            retrieval_configuration=RetrievalConfiguration.evidence_containment_v1(),
            admission_store=admissions,
        ),
        ingestion_worker=ProcessIngestionJob(
            store=jobs,
            handler=PdfDerivationHandler(
                object_store=objects,
                extractor=PypdfTextExtractor(),
                embedding_provider=embedding_provider,
                profile_resolver=jobs.pdf_profile_for_work,
                runtime_embedding_configuration=embedding_configuration,
            ),
            operation_ids=UuidOperationIds(),
            timing=AttemptTimingV1.standard(),
            retry_policy=RetryPolicyV1(SystemRandomSource()),
            runner=FixedCapacityThreadAttemptRunner(max_concurrency=1),
        ),
    )


def main():
    import argparse
    import asyncio
    from contextlib import asynccontextmanager, suppress
    from urllib.parse import urlparse

    parser = argparse.ArgumentParser(
        description="Serve owned S1 baseline with gold approval and verified Free snapshot"
    )
    parser.add_argument(
        "--manifest", type=Path, default=Path("evals/datasets/pdf_retrieval_v3_v1.manifest.json")
    )
    parser.add_argument(
        "--dataset", type=Path, default=Path("evals/datasets/pdf_retrieval_v3_v1.jsonl")
    )
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--free-preflight", type=Path, required=True)
    parser.add_argument("--counters", type=Path, required=True)
    parser.add_argument("--objects", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    from evals.datasets.pdf_retrieval_v3_v1 import load_dataset, validate_approval

    dataset = load_dataset(args.manifest, args.dataset)
    validate_approval(dataset, json.loads(args.approval.read_text(encoding="utf-8-sig")))
    database = urlparse(os.environ["KNORA_DATABASE_URL"])
    if (
        database.hostname not in {"127.0.0.1", "localhost"}
        or database.port != 55453
        or not database.path.startswith("/knora153s1_")
    ):
        parser.error("use the owned loopback55453 knora153s1_ database; daily database forbidden")
    # Defaults are unused deterministic clients; all real AI callers receive guarded providers.
    os.environ.update(
        KNORA_PROVIDER_MODE="deterministic-local",
        KNORA_EMBEDDING_PROVIDER="deterministic-local",
        KNORA_GENERATION_PROVIDER="deterministic-local",
        KNORA_EMBEDDING_DIMENSION="1536",
        KNORA_OPENAI_EMBEDDING_MODEL="text-embedding-3-small",
        KNORA_EXPECTED_EMBEDDING_CONFIGURATION_ID="embedding-local-m1-v2",
    )
    preflight = json.loads(args.free_preflight.read_text(encoding="utf-8-sig"))
    if preflight.get("account_id") != os.environ["KNORA_CLOUDFLARE_ACCOUNT_ID"]:
        parser.error("Free evidence account mismatch")
    guard = FreeOnlyGuard(
        args.counters,
        run_identity={
            "run_id": args.run_id,
            "corpus_sha256": dataset.corpus_sha256,
            "dataset_sha256": dataset.dataset_sha256,
            "baseline": "pypdf-layout-v2/qwen3-06b/gpt-oss20b/containment0.65",
        },
        preflight=preflight,
    )
    import platform
    import subprocess

    guard.state["runtime_provenance"] = {
        "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "python": platform.python_version(),
        "database": f"{database.hostname}:{database.port}{database.path}",
        "api": "http://127.0.0.1:8153",
    }
    guard.save()
    import time

    import httpx
    import uvicorn

    from knora.access.keycloak import KeycloakAuthenticator
    from knora.domain.errors import KnoraError
    from knora.providers.cloudflare.embedding import CloudflareEmbeddingProvider
    from knora.providers.embedding import EmbeddingConfiguration
    from knora.providers.openai_compatible.generation import OpenAICompatibleGenerationProvider

    # Same owner/capability authorization services, with a local eval credential on loopback.
    token = os.environ["KNORA_S1_BEARER_TOKEN"]

    def claims(value):
        import secrets

        if not secrets.compare_digest(value, token):
            raise KnoraError("UNAUTHENTICATED")
        return {
            "iss": "https://s1-evaluation.local",
            "aud": "knora-api",
            "sub": args.run_id,
            "exp": time.time() + 60,
            "capabilities": ["questions:ask", "documents:write", "documents:read"],
        }

    authenticator = KeycloakAuthenticator(
        issuer="https://s1-evaluation.local", audience="knora-api", token_validator=claims
    )
    sync_client = httpx.Client(
        timeout=60,
        event_hooks={"request": [guard.before_request], "response": [guard.after_response]},
    )
    async_client = httpx.AsyncClient(
        timeout=60,
        event_hooks={
            "request": [guard.before_async_request],
            "response": [guard.after_async_response],
        },
    )
    embedding = CloudflareEmbeddingProvider(
        account_id=guard.account_id,
        api_token=os.environ["KNORA_CLOUDFLARE_API_TOKEN"],
        client=sync_client,
    )
    generation = OpenAICompatibleGenerationProvider(
        base_url=f"https://api.cloudflare.com/client/v4/accounts/{guard.account_id}/ai/v1",
        api_key=os.environ["KNORA_CLOUDFLARE_API_TOKEN"],
        model="@cf/openai/gpt-oss-20b",
        input_cost_per_million_tokens=None,
        output_cost_per_million_tokens=None,
        pricing_version=None,
        provider_identity="cloudflare-workers-ai",
        max_tokens=1024,
        direct_json_schema=True,
        client=async_client,
    )
    app = build_evaluation_app(
        embedding_provider=embedding,
        generation_provider=generation,
        embedding_configuration=EmbeddingConfiguration.cloudflare_qwen3_06b(),
        objects_root=args.objects,
        authenticator=authenticator,
    )
    original_lifespan = app.router.lifespan_context

    async def ingestion():
        while not guard.state["stop_reason"]:
            await asyncio.to_thread(app.state.ingestion_worker.run_once, f"{args.run_id}:pdf")
            await asyncio.sleep(0.2)

    async def conversations():
        while not guard.state["stop_reason"]:
            await app.state.conversation_runner.run_once(worker_id=f"{args.run_id}:turn")
            await asyncio.sleep(0.2)

    @asynccontextmanager
    async def lifespan(application):
        async with original_lifespan(application):
            tasks = [asyncio.create_task(ingestion()), asyncio.create_task(conversations())]
            try:
                yield
            finally:
                for task in tasks:
                    task.cancel()
                for task in tasks:
                    with suppress(asyncio.CancelledError):
                        await task
                sync_client.close()
                await async_client.aclose()

    app.router.lifespan_context = lifespan
    uvicorn.run(app, host="127.0.0.1", port=8153)


if __name__ == "__main__":
    main()
