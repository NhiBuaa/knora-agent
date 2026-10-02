"""Owner-approved extraction/model feasibility through an owned process per call."""

import argparse
import asyncio
import hashlib
import inspect
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import httpx
from evals.runners.ollama_evidence_first_probe import (
    EXTRACTION_SCHEMA,
    REQUEST_POLICY_ID,
    EvidenceFirstProbeProvider,
    EvidenceFirstProbeTransport,
    extraction_prompt_version,
    extraction_system_prompt,
)
from evals.runners.ollama_grounding import collect
from evals.runners.process_probe import run_process_async, safe_invalid_output_stage
from evals.runners.vietnamese_conversation import code_provenance, validate_private_output

from knora.answering.generation_validation import validate_generation
from knora.domain.errors import KnoraError
from knora.providers.generation import GenerationResult
from knora.providers.ollama.generation import OllamaGenerationProvider


def runtime_module_sources():
    root = Path(__file__).resolve().parents[2]
    sources = {}
    for symbol, relative in (
        (OllamaGenerationProvider, "backend/src/knora/providers/ollama/generation.py"),
        (GenerationResult, "backend/src/knora/providers/generation.py"),
        (validate_generation, "backend/src/knora/answering/generation_validation.py"),
    ):
        actual = Path(inspect.getfile(symbol)).resolve()
        if actual != (root / relative).resolve():
            raise ValueError("runtime checkout mismatch")
        content = actual.read_bytes()
        committed = subprocess.check_output(["git", "show", f"HEAD:{relative}"], cwd=root)
        if content.replace(b"\r\n", b"\n") != committed:
            raise ValueError("runtime source differs from commit")
        sources[relative] = {
            "runtime_sha256": hashlib.sha256(content).hexdigest(),
            "committed_sha256": hashlib.sha256(committed).hexdigest(),
        }
    return sources


def extraction_worker(connection, arguments):
    config, question, evidence = arguments

    async def generate():
        transport = EvidenceFirstProbeTransport(
            sampling_profile=config["sampling_profile"],
            seed=config["seed"],
            context_tokens=config["context_tokens"],
            observe_request=lambda row: connection.send({"kind": "request", "observation": row}),
        )
        async with httpx.AsyncClient(transport=transport, timeout=240, trust_env=False) as client:
            provider = EvidenceFirstProbeProvider(
                base_url=config["base_url"],
                model=config["model"],
                expected_digest=config["expected_digest"],
                client=client,
                sampling_profile=config["sampling_profile"],
            )
            return await provider.generate(question=question, evidence=evidence)

    try:
        sources = runtime_module_sources()
        if sources != config["runtime_sources"]:
            raise ValueError("child runtime source mismatch")
        connection.send({"kind": "runtime", "runtime_sources": sources})
        result = asyncio.run(generate())
        connection.send({"kind": "result", "result": result})
    except Exception as error:
        code = (
            error.code
            if isinstance(error, KnoraError) and error.code == "GENERATION_OUTPUT_INVALID"
            else "PROVIDER_REQUEST_FAILED"
        )
        connection.send(
            {
                "kind": "error",
                "error": code,
                "invalid_output_stage": safe_invalid_output_stage(
                    getattr(error, "invalid_output_stage", None)
                )
                if code == "GENERATION_OUTPUT_INVALID"
                else None,
            }
        )
    finally:
        connection.close()


class ProcessEvidenceProvider:
    def __init__(self, **config):
        self.runtime_sources = runtime_module_sources()
        self.config = {**config, "runtime_sources": self.runtime_sources}
        self.requests = []
        self.process_observations = []
        self.deadline_expired = False
        self.supervisor_failed = False

    async def generate(self, *, question, evidence):
        print(
            json.dumps({"process_probe_call_started": len(self.process_observations) + 1}),
            flush=True,
        )
        try:
            observation = await run_process_async(
                extraction_worker, (self.config, question, evidence)
            )
        except Exception:
            self.supervisor_failed = True
            self.process_observations.append({"supervisor_failed": True, "elapsed_seconds": None})
            raise KnoraError("PROVIDER_REQUEST_FAILED") from None
        self.requests.extend(observation["requests"])
        self.deadline_expired = observation["deadline_expired"]
        self.supervisor_failed = observation["supervisor_failed"]
        if observation.get("runtime_sources") != self.runtime_sources:
            self.supervisor_failed = True
        self.process_observations.append(
            {
                "elapsed_seconds": observation["elapsed_seconds"],
                "deadline_expired": self.deadline_expired,
                "request_count": len(observation["requests"]),
                "supervisor_failed": self.supervisor_failed,
                "runtime_sources": observation.get("runtime_sources"),
                "invalid_output_stage": safe_invalid_output_stage(
                    observation.get("invalid_output_stage")
                ),
            }
        )
        if self.supervisor_failed:
            raise KnoraError("PROVIDER_REQUEST_FAILED")
        if observation["error"]:
            raise KnoraError(observation["error"])
        result = observation["result"]
        if (
            len(observation["requests"]) != 1
            or result.model != self.config["model"]
            or result.finish_reason != "stop"
            or type(result.usage.get("prompt_tokens")) is not int
            or not 0 < result.usage["prompt_tokens"] <= self.config["context_tokens"] - 2048
            or type(result.usage.get("completion_tokens")) is not int
            or not 0 < result.usage["completion_tokens"] <= 2048
        ):
            raise KnoraError("GENERATION_OUTPUT_INVALID")
        return result


async def run_live(args):
    provider = ProcessEvidenceProvider(
        base_url=args.base_url,
        model=args.model,
        expected_digest=args.digest,
        sampling_profile=args.sampling_profile,
        seed=args.seed,
        context_tokens=args.context_tokens,
    )
    captures = []
    report = await collect(provider, captured_responses=captures, stop_on_deadline=True)
    policy = (
        f"{REQUEST_POLICY_ID}:process-v1:{args.model}:ctx{args.context_tokens}:"
        f"{args.sampling_profile}:seed{args.seed}"
    )
    prompt_hash = hashlib.sha256(
        extraction_system_prompt(args.sampling_profile).encode()
    ).hexdigest()
    private = {
        "fixture_sha256": report["fixture_sha256"],
        "system_prompt_sha256": prompt_hash,
        "request_policy_id": policy,
        "responses": captures,
    }
    content = (json.dumps(private, ensure_ascii=False, indent=2) + "\n").encode()
    args.private_output.parent.mkdir(parents=True, exist_ok=True)
    args.private_output.write_bytes(content)
    report.update(
        prompt_version=extraction_prompt_version(args.sampling_profile),
        request_policy_id=policy,
        model=args.model,
        sampling_profile=args.sampling_profile,
        seed=args.seed,
        context_tokens=args.context_tokens,
        system_prompt_sha256=prompt_hash,
        extraction_schema_sha256=hashlib.sha256(
            json.dumps(EXTRACTION_SCHEMA, sort_keys=True).encode()
        ).hexdigest(),
        generation_expected_digest=args.digest,
        requests=provider.requests,
        process_observations=provider.process_observations,
        runtime_sources=provider.runtime_sources,
        timeout_seconds=240,
        timeout_scope="parent_supervised_process_per_generate_timer_includes_startup_and_digest",
        startup_blocking_bound_proven=False,
        child_cleanup_wait_budget_seconds=0.65,
        runtime_gate=(
            "FAILED_SUPERVISOR"
            if provider.supervisor_failed
            else "FAILED_DEADLINE"
            if provider.deadline_expired
            else "NO_DEADLINE_OR_SUPERVISOR_FAILURE"
        ),
        server_cancellation_proven=False,
        private_responses_sha256=hashlib.sha256(content).hexdigest(),
        transport_gate="PROVIDER_PROBE_NOT_CONVERSATION",
        deployment_selection=False,
        release_gate="NOT_EVALUATED",
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:11435")
    parser.add_argument("--model", choices=("qwen3:8b", "qwen3:14b", "gpt-oss:20b"), required=True)
    parser.add_argument("--digest", required=True)
    parser.add_argument(
        "--sampling-profile",
        choices=(
            "qwen-nonthinking-v1",
            "qwen-thinking-v1",
            "gpt-oss-low-v1",
            "gpt-oss-extraction-v2",
            "gpt-oss-extraction-v3",
        ),
        default="qwen-nonthinking-v1",
    )
    parser.add_argument("--seed", choices=(105, 106, 107), type=int, default=105)
    parser.add_argument("--context-tokens", choices=(4096, 8192), type=int, default=4096)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"http://(?:127\.0\.0\.1|localhost):[0-9]{1,5}", args.base_url):
        raise ValueError("local probe endpoint required")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", args.digest):
        raise ValueError("model digest required")
    validate_private_output(args.private_output)
    provenance = code_provenance(Path(__file__).resolve().parents[2])
    report = asyncio.run(run_live(args))
    report.update(
        code_provenance=provenance,
        observed_at=datetime.now(UTC).isoformat(),
        source_sha256={
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (
                Path(__file__),
                Path(__file__).with_name("process_probe.py"),
                Path(__file__).with_name("ollama_evidence_first_probe.py"),
            )
        },
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes((json.dumps(report, indent=2, sort_keys=True) + "\n").encode())
    print(json.dumps({key: report[key] for key in ("observation_count", "literal_passed_count")}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("Process probe failed; no complete report was produced.") from None
