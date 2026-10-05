import asyncio
import importlib
from types import SimpleNamespace

import pytest


def test_acceptance_server_refuses_production_database_before_composition(monkeypatch):
    monkeypatch.setenv("KNORA_DATABASE_URL", "postgresql://knora@127.0.0.1/knora_dev")
    try:
        module = importlib.import_module("evals.runners.ollama_acceptance_server")
    except ModuleNotFoundError:
        pytest.fail("isolated acceptance server composition is missing")
    with pytest.raises(ValueError, match="isolated"):
        module.create_application()


def test_acceptance_guard_rejects_issuer_only_api_key_authentication():
    module = importlib.import_module("evals.runners.ollama_acceptance_server")
    settings = SimpleNamespace(
        embedding_provider="ollama",
        generation_provider="ollama",
        expected_generation_model_digest="sha256:" + "a" * 64,
        keycloak_issuer="http://127.0.0.1:8180/realms/knora-dev",
        keycloak_audience=None,
        keycloak_jwks_url=None,
    )
    with pytest.raises(ValueError, match="OIDC"):
        module.validate_runtime_settings(settings, "conversation-context-v2")


def test_shutdown_drains_current_turn_without_claiming_another():
    module = importlib.import_module("evals.runners.ollama_acceptance_server")

    async def scenario():
        started, finish, stopping = asyncio.Event(), asyncio.Event(), asyncio.Event()
        calls = []

        class Runner:
            async def run_once(self, **command):
                calls.append(command)
                started.set()
                await finish.wait()
                return True

        task = asyncio.create_task(module.run_worker(Runner(), "workspace", stopping))
        await started.wait()
        stopping.set()
        await asyncio.sleep(0)
        assert not task.done()
        finish.set()
        await task
        assert len(calls) == 1
        assert calls[0]["workspace_id"] == "workspace"

    asyncio.run(scenario())
