from types import SimpleNamespace

from knora.adapters.cli import cleanup_lexical


def test_run_cleanup_calls_authority_then_native_delete(monkeypatch):
    calls = []

    monkeypatch.setattr(
        cleanup_lexical,
        "settings",
        SimpleNamespace(
            retrieval_configuration_id="retrieval-bm25-top8-v1",
            vector_min_similarity=None,
            lexical_population_manifest="manifest.json",
            lexical_qdrant_url="http://127.0.0.1:16433",
            lexical_qdrant_collection="s2-cleanup",
        ),
    )
    monkeypatch.setattr(
        cleanup_lexical, "resolve_retrieval_configuration", lambda *a, **k: object()
    )
    population = SimpleNamespace(profile=object())
    monkeypatch.setattr(cleanup_lexical, "load_lexical_population", lambda *a: population)

    class Client:
        def __init__(self, **kwargs):
            calls.append(("client", kwargs))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            calls.append(("close",))

    class Index:
        def __init__(self, **kwargs):
            calls.append(("index", kwargs))

        def remove_generation(self, generation):
            calls.append(("remove", generation))

    class Store:
        def __init__(self, sessions):
            calls.append(("store", sessions))

        def cleanup_generation_in_transaction(self, session, generation_id, remove):
            calls.append(("authority", session, generation_id))
            remove("decoded-generation")
            return "removed"

    class Factory:
        @staticmethod
        def begin():
            class Context:
                def __enter__(self):
                    return "session"

                def __exit__(self, *args):
                    pass

            return Context()

    monkeypatch.setattr(cleanup_lexical.httpx, "Client", Client)
    monkeypatch.setattr(cleanup_lexical, "NativeQdrantSearchIndex", Index)
    monkeypatch.setattr(cleanup_lexical, "PostgresSearchIndexStore", Store)
    monkeypatch.setattr(cleanup_lexical, "SessionFactory", Factory)
    assert cleanup_lexical.run_cleanup("generation") == {
        "generation_id": "generation",
        "outcome": "removed",
    }
    assert [entry[0] for entry in calls] == [
        "client",
        "index",
        "store",
        "authority",
        "remove",
        "close",
    ]
