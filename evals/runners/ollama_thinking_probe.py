"""Experimental inference probe only; never selected by the production bootstrap.

This disposable transport answers the owner-approved thinking feasibility question.
It reuses the actual adapter's digest, parsing and validation behavior. Only request
mode and token budget change; response thinking is neither projected nor captured.
"""

import argparse
import asyncio
import hashlib
import inspect
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import httpx
from evals.runners.ollama_grounding import collect
from evals.runners.vietnamese_conversation import code_provenance, validate_private_output

from knora.domain.errors import KnoraError
from knora.providers.ollama.generation import OllamaGenerationProvider

REQUEST_POLICY_ID = "ollama-thinking-feasibility-v1"


class BoundedThinkingProbeProvider:
    def __init__(self, provider, *, deadline_seconds=240):
        if not 0 < deadline_seconds <= 240:
            raise ValueError("probe deadline must be within 240 seconds")
        self.provider = provider
        self.deadline_seconds = deadline_seconds

    async def generate(self, *, question, evidence):
        try:
            async with asyncio.timeout(self.deadline_seconds):
                return await self.provider.generate(question=question, evidence=evidence)
        except TimeoutError:
            raise KnoraError("PROVIDER_REQUEST_FAILED") from None


class ThinkingProbeTransport(httpx.AsyncBaseTransport):
    def __init__(self, *, inner=None):
        self.inner = inner if inner is not None else httpx.AsyncHTTPTransport()
        self.observations = []

    async def handle_async_request(self, request):
        if request.method == "POST" and request.url.path == "/api/chat":
            payload = json.loads(await request.aread())
            payload["think"] = True
            payload["options"]["num_predict"] = 2048
            self.observations.append(
                {
                    "model": payload["model"],
                    "think": payload["think"],
                    "options": payload["options"],
                    "system_prompt_sha256": hashlib.sha256(
                        payload["messages"][0]["content"].encode()
                    ).hexdigest(),
                    "user_message_sha256": hashlib.sha256(
                        payload["messages"][1]["content"].encode()
                    ).hexdigest(),
                }
            )
            print(json.dumps({"probe_request_started": len(self.observations)}), flush=True)
            # Rebuild length after changing JSON; preserve the caller's timeout bounds.
            request = httpx.Request(
                request.method,
                request.url,
                json=payload,
                headers=[
                    (key, value)
                    for key, value in request.headers.raw
                    if key.lower() != b"content-length"
                ],
                extensions=request.extensions,
            )
        return await self.inner.handle_async_request(request)

    async def aclose(self):
        await self.inner.aclose()


async def run_live(args):
    captures = []
    transport = ThinkingProbeTransport()
    async with httpx.AsyncClient(transport=transport, timeout=240, trust_env=False) as client:
        provider = OllamaGenerationProvider(
            base_url=args.base_url,
            model="qwen3:8b",
            expected_digest=args.digest,
            client=client,
        )
        report = await collect(BoundedThinkingProbeProvider(provider), captured_responses=captures)
    if len(transport.observations) != report["observation_count"]:
        raise ValueError("probe request count mismatch")
    prompt_hashes = {item["system_prompt_sha256"] for item in transport.observations}
    if len(prompt_hashes) != 1:
        raise ValueError("probe prompt mismatch")
    prompt_sha256 = prompt_hashes.pop()
    private_payload = {
        "fixture_sha256": report["fixture_sha256"],
        "system_prompt_sha256": prompt_sha256,
        "request_policy_id": REQUEST_POLICY_ID,
        "responses": captures,
    }
    content = (json.dumps(private_payload, ensure_ascii=False, indent=2) + "\n").encode()
    args.private_output.parent.mkdir(parents=True, exist_ok=True)
    args.private_output.write_bytes(content)
    report.update(
        request_policy_id=REQUEST_POLICY_ID,
        system_prompt_sha256=prompt_sha256,
        requests=transport.observations,
        timeout_seconds=240,
        timeout_scope="wall_deadline_per_provider_generate_including_digest_lookup",
        generation_expected_digest=args.digest,
        private_responses_sha256=hashlib.sha256(content).hexdigest(),
        transport_gate="PROVIDER_PROBE_NOT_CONVERSATION",
        deployment_selection=False,
        release_gate="NOT_EVALUATED",
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:11435")
    parser.add_argument("--digest", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"http://(?:127\.0\.0\.1|localhost):[0-9]{1,5}", args.base_url):
        raise ValueError("local probe endpoint required")
    validate_private_output(args.private_output)
    provenance = code_provenance(Path(__file__).resolve().parents[2])
    report = asyncio.run(run_live(args))
    report.update(
        code_provenance=provenance,
        observed_at=datetime.now(UTC).isoformat(),
        probe_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        provider_source_sha256=hashlib.sha256(
            Path(inspect.getfile(OllamaGenerationProvider)).read_bytes()
        ).hexdigest(),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("observation_count", "literal_passed_count")}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("Thinking probe failed; no complete report was produced.") from None
