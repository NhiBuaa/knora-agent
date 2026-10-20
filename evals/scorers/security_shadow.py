from __future__ import annotations

from typing import Any

APPROVED_PACKAGES = {
    "guardrails-ai": "0.11.0",
    "guardrails-ai-secrets-present": "0.1.0",
    "detect-secrets": "1.5.0",
}


def scan_text(text: str, *, validator: Any) -> dict[str, Any]:
    if not isinstance(text, str):
        return {
            "status": "error",
            "finding_type": None,
            "diagnostics": {"error": "invalid_text"},
        }
    try:
        result = validator.validate(text, {})
    except TimeoutError:
        return {
            "status": "timeout",
            "finding_type": None,
            "diagnostics": {"error": "validator_timeout"},
        }
    except Exception:
        return {
            "status": "error",
            "finding_type": None,
            "diagnostics": {"error": "validator_error"},
        }

    outcome = getattr(result, "outcome", None)
    if outcome == "fail":
        return {
            "status": "detected",
            "finding_type": "secrets_present",
            "diagnostics": {"validator": "SecretsPresent"},
        }
    return {
        "status": "clear" if outcome == "pass" else "unknown",
        "finding_type": None,
        "diagnostics": {"validator": "SecretsPresent"},
    }


def scan_local(text: str, *, timeout: float = 30) -> dict[str, Any]:
    """Run one scan in a fresh credential-free process; discard vendor diagnostics."""
    import json
    import os
    import subprocess
    import sys
    import tempfile
    import time
    from pathlib import Path

    if not isinstance(text, str):
        return {"status": "error", "finding_type": None, "diagnostics": {"error": "invalid_text"}}
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="knora-shadow-") as folder:
        env = {
            key: os.environ[key] for key in ("SystemRoot", "WINDIR", "COMSPEC") if key in os.environ
        }
        env.update(
            {
                "HOME": folder,
                "USERPROFILE": folder,
                "APPDATA": folder,
                "LOCALAPPDATA": folder,
                "TEMP": folder,
                "TMP": folder,
                "HF_HOME": folder,
                "XDG_CACHE_HOME": folder,
                "PYTHONUTF8": "1",
                "PYTHONIOENCODING": "utf-8",
                "PYTHONDONTWRITEBYTECODE": "1",
                "HF_HUB_OFFLINE": "1",
                "TRANSFORMERS_OFFLINE": "1",
                "OTEL_SDK_DISABLED": "true",
                "OTEL_TRACES_EXPORTER": "none",
                "OTEL_METRICS_EXPORTER": "none",
                "OTEL_LOGS_EXPORTER": "none",
                "LITELLM_LOCAL_MODEL_COST_MAP": "True",
                "DO_NOT_TRACK": "1",
                "LANGCHAIN_TRACING_V2": "false",
                "LANGSMITH_TRACING": "false",
                "ANONYMIZED_TELEMETRY": "False",
            }
        )
        Path(folder, ".guardrailsrc").write_text(
            "enable_metrics=false\nuse_remote_inferencing=false\ntoken=\n", encoding="utf-8"
        )
        try:
            completed = subprocess.run(
                [sys.executable, "-X", "utf8", str(Path(__file__).resolve()), "--worker"],
                input=json.dumps({"text": text}),
                text=True,
                encoding="utf-8",
                capture_output=True,
                timeout=timeout,
                env=env,
                cwd=folder,
                check=False,
            )
            if completed.returncode:
                raise ValueError("WORKER_ERROR")
            result = json.loads(completed.stdout)
            if result.get("status") not in {"detected", "clear", "unknown", "error"}:
                raise ValueError("WORKER_ERROR")
        except subprocess.TimeoutExpired:
            return {
                "status": "timeout",
                "finding_type": None,
                "diagnostics": {"error": "validator_timeout"},
            }
        except (OSError, ValueError, TypeError):
            return {
                "status": "error",
                "finding_type": None,
                "diagnostics": {"error": "worker_error"},
            }
    result["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 3)
    return result


def _worker() -> None:
    import contextlib
    import importlib.metadata
    import json
    import logging
    import os
    import sys
    import warnings

    attempts = 0

    def audit(event: str, args: tuple) -> None:
        nonlocal attempts
        if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto", "subprocess.Popen"}:
            attempts += 1
            raise PermissionError("SHADOW_EGRESS_DISABLED")

    sys.addaudithook(audit)
    logging.disable(logging.CRITICAL)
    request = json.load(sys.stdin)
    result = {"status": "error", "finding_type": None, "diagnostics": {"error": "worker_error"}}
    packages = {}
    with (
        open(os.devnull, "w", encoding="utf-8") as sink,
        contextlib.redirect_stdout(sink),
        contextlib.redirect_stderr(sink),
        warnings.catch_warnings(),
    ):
        warnings.simplefilter("ignore")
        try:
            packages = {name: importlib.metadata.version(name) for name in APPROVED_PACKAGES}
            if packages != APPROVED_PACKAGES:
                result["diagnostics"]["error"] = "dependency_version_mismatch"
                result["packages"] = packages
                # Version drift must fail before importing or invoking the validator.
                raise ValueError("DEPENDENCY_VERSION_MISMATCH")
            from guardrails.settings import settings
            from guardrails_ai.secrets_present import SecretsPresent

            settings.rc.enable_metrics = False
            settings.rc.use_remote_inferencing = False
            settings.disable_tracing = True
            validator = SecretsPresent(on_fail="noop", use_local=True)
            result = scan_text(request["text"], validator=validator)
        except (ImportError, importlib.metadata.PackageNotFoundError):
            result["diagnostics"]["error"] = "dependency_unavailable"
        except Exception:
            pass
    if attempts:
        result = {
            "status": "error",
            "finding_type": None,
            "diagnostics": {"error": "network_attempt"},
        }
    result["diagnostics"]["blocked_network_attempts"] = attempts
    result["packages"] = packages
    print(json.dumps(result))


if __name__ == "__main__":
    _worker()
