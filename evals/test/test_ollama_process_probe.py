import asyncio
import importlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from knora.domain.errors import KnoraError
from knora.providers.generation import GenerationEvidence


def test_supervisor_exception_stops_profile_before_starting_another_child(monkeypatch):
    from evals.runners import ollama_process_probe as module
    from evals.runners.ollama_grounding import collect

    calls = []

    async def cleanup_failure(*args, **kwargs):
        calls.append(True)
        raise RuntimeError("owned probe worker did not terminate")

    monkeypatch.setattr(module, "run_process_async", cleanup_failure)
    provider = module.ProcessEvidenceProvider(model="qwen3:14b")
    report = asyncio.run(collect(provider, stop_on_deadline=True))
    assert len(calls) == report["observation_count"] == 1
    assert provider.supervisor_failed is True
    assert report["stopped_after_supervisor_failure"] is True
    assert report["unmeasured_case_count"] == 10
    assert provider.process_observations[0]["supervisor_failed"] is True


def test_runtime_guard_rejects_an_adapter_imported_from_another_checkout(monkeypatch):
    from evals.runners import ollama_process_probe as module

    with monkeypatch.context() as patched:
        try:
            getfile = module.inspect.getfile
        except AttributeError:
            pytest.fail("runtime source guard is missing")
        another_checkout = module.Path(__file__).resolve().parents[2].parent / "other-checkout"
        patched.setattr(
            module.inspect,
            "getfile",
            lambda item: (
                str(another_checkout / "backend/src/knora/providers/ollama/generation.py")
                if item is module.OllamaGenerationProvider
                else getfile(item)
            ),
        )
        with pytest.raises(ValueError, match="runtime checkout mismatch"):
            module.runtime_module_sources()


@pytest.mark.parametrize(
    ("model", "profile", "think", "failure_stage"),
    [
        ("qwen3:14b", "qwen-nonthinking-v1", False, None),
        ("gpt-oss:20b", "gpt-oss-low-v1", "low", None),
        ("gpt-oss:20b", "gpt-oss-extraction-v2", "low", None),
        ("gpt-oss:20b", "gpt-oss-extraction-v2", "low", "EXTRACTION_FIELDS"),
        ("gpt-oss:20b", "gpt-oss-extraction-v2", "low", "SOURCE_QUOTE"),
    ],
)
def test_spawned_adapter_returns_only_validated_result_and_actual_request_metadata(
    model, profile, think, failure_stage
):
    try:
        module = importlib.import_module("evals.runners.ollama_process_probe")
    except ModuleNotFoundError:
        pytest.fail("process-isolated Ollama composition is missing")
    digest = "sha256:" + "b" * 64
    observed_requests = []

    class Endpoint(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def reply(self, value):
            body = json.dumps(value).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            self.reply({"models": [{"name": model, "digest": digest}]})

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            observed_requests.append(payload)
            extraction = {
                "decision": "ANSWER",
                "facts": [],
                "rules": [{"evidence_id": "E1", "quote": "Không ghi tên."}],
                "exceptions": [],
                "refusal_reason": None,
            }
            if failure_stage == "EXTRACTION_FIELDS":
                del extraction["decision"]
            elif failure_stage == "SOURCE_QUOTE":
                extraction["rules"][0]["quote"] = "PRIVATE_INVALID_QUOTE"
            self.reply(
                {
                    "model": model,
                    "done_reason": "stop",
                    "prompt_eval_count": 450,
                    "eval_count": 40,
                    "message": {
                        "thinking": "PRIVATE_THINKING",
                        "content": json.dumps(extraction),
                    },
                }
            )

    server = ThreadingHTTPServer(("127.0.0.1", 0), Endpoint)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        provider = module.ProcessEvidenceProvider(
            base_url=f"http://127.0.0.1:{server.server_port}",
            model=model,
            expected_digest=digest,
            sampling_profile=profile,
            seed=105,
            context_tokens=4096,
        )

        async def generate():
            return await provider.generate(
                question="Có được ghi tên?",
                evidence=(GenerationEvidence("E1", "Không ghi tên."),),
            )

        if failure_stage:
            with pytest.raises(KnoraError) as error:
                asyncio.run(generate())
            assert error.value.code == "GENERATION_OUTPUT_INVALID"
            assert provider.process_observations[0]["invalid_output_stage"] == failure_stage
            assert "PRIVATE" not in repr(error.value) + json.dumps(provider.process_observations)
            assert len(observed_requests) == len(provider.requests) == 1
            return
        result = asyncio.run(generate())
        assert result.answer == "Không ghi tên. [[E1]]"
        assert result.model == model
        if profile == "gpt-oss-extraction-v2":
            assert result.prompt_version == "ollama-evidence-first-gpt-extraction-v2"
        assert provider.deadline_expired is False
        assert len(observed_requests) == len(provider.requests) == 1
        assert provider.requests[0]["options"]["num_ctx"] == 4096
        assert provider.requests[0]["think"] == think
        assert "PRIVATE_THINKING" not in repr(result) + json.dumps(provider.requests)
        assert provider.process_observations[0]["deadline_expired"] is False
        assert provider.process_observations[0]["runtime_sources"] == provider.runtime_sources
        assert len(provider.runtime_sources) == 3
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
