from datetime import UTC, datetime

from knora.main import create_app


class ObjectStore:
    def put_stream(self, *, workspace_id, stream, media_type):
        del workspace_id, stream, media_type
        raise AssertionError("not used")

    def open_read(self, *, workspace_id, object_key):
        del workspace_id, object_key
        raise AssertionError("not used")

    def head(self, *, workspace_id, object_key):
        del workspace_id, object_key
        raise AssertionError("not used")

    def delete(self, *, workspace_id, object_key):
        del workspace_id, object_key


class Inventory:
    def objects(self, *, workspace_id):
        del workspace_id
        return []


class Clock:
    def now(self):
        return datetime.now(UTC)


def test_create_app_composes_lifecycle_worker_and_optional_reconciler() -> None:
    application = create_app(
        object_store=ObjectStore(),
        lifecycle_inventory=Inventory(),
        lifecycle_clock=Clock(),
    )

    assert application.state.object_lifecycle_worker is not None
    assert application.state.object_lifecycle_reconciler is not None
    assert application.state.operational_observability is not None
