from knora.domain.access import WorkspacePrincipal
from knora.ingestion.documents import DocumentLifecycleService, DocumentProjection


class FakeLifecycle:
    def __init__(self):
        self.calls = []

    def archive(self, **kwargs):
        self.calls.append(("archive", kwargs["document_id"]))
        return DocumentProjection(
            document_id=kwargs["document_id"],
            workspace_id=kwargs["workspace_id"],
            source_key="x",
            source_name="X",
            archived=True,
            revision=1,
        )

    def unarchive(self, **kwargs):
        self.calls.append(("unarchive", kwargs["document_id"]))
        return DocumentProjection(
            document_id=kwargs["document_id"],
            workspace_id=kwargs["workspace_id"],
            source_key="x",
            source_name="X",
            archived=False,
            revision=2,
        )

    def request_deletion(self, **kwargs):
        self.calls.append(("delete", kwargs["document_id"], kwargs["idempotency_key"]))
        from knora.ingestion.documents import DocumentDeletionRequestProjection

        return DocumentDeletionRequestProjection("r1", kwargs["document_id"], "requested")


def test_lifecycle_delegates_typed_commands():
    principal = WorkspacePrincipal("w", "k", ("documents:write", "documents:delete"))
    service = DocumentLifecycleService(FakeLifecycle())
    assert service.archive("w", "d", principal, 0).archived is True
    assert service.unarchive("w", "d", principal, 1).archived is False
    assert service.request_deletion("w", "d", principal, "idem").request_id == "r1"
