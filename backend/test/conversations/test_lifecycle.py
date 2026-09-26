from __future__ import annotations

from importlib import import_module

import pytest

from knora.access.identity import Identity
from knora.access.workspace_authorization import WorkspaceAuthorizer
from knora.domain.errors import KnoraError


class OwnerStore:
    def __init__(self, owner: Identity | None) -> None:
        self.owner = owner
        self.lookups: list[str] = []

    def owner_for(self, workspace_id: str) -> Identity | None:
        self.lookups.append(workspace_id)
        return self.owner


class ConversationStore:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.result = object()

    def create(self, workspace_id: str, idempotency_key: str):
        self.calls.append(("create", workspace_id, idempotency_key))
        return self.result

    def get(self, workspace_id: str, conversation_id: str):
        self.calls.append(("get", workspace_id, conversation_id))
        return self.result

    def list(self, workspace_id: str, archived: bool, cursor: str | None, limit: int):
        self.calls.append(("list", workspace_id, archived, cursor, limit))
        return self.result

    def mutate(
        self,
        workspace_id: str,
        conversation_id: str,
        expected_revision: int,
        *,
        title: str | None = None,
        archived: bool | None = None,
    ):
        self.calls.append(
            ("mutate", workspace_id, conversation_id, expected_revision, title, archived)
        )
        return self.result


def conversation_service_module():
    try:
        return import_module("knora.conversations.service")
    except ModuleNotFoundError as error:
        pytest.fail(f"Conversation service is not implemented: {error}", pytrace=False)


def conversation_service():
    return conversation_service_module().ConversationService


def test_create_authorizes_workspace_before_creating_conversation() -> None:
    identity = Identity("https://issuer", "owner", ("questions:ask",))
    owners = OwnerStore(Identity(identity.issuer, identity.subject))
    store = ConversationStore()
    service = conversation_service()(
        store=store,
        workspace_authorizer=WorkspaceAuthorizer(owners),
    )

    result = service.create(identity, "workspace-1", "create-key-1")

    assert result is store.result
    assert owners.lookups == ["workspace-1"]
    assert store.calls == [("create", "workspace-1", "create-key-1")]


def test_foreign_workspace_is_denied_before_conversation_lookup() -> None:
    identity = Identity("https://issuer", "intruder")
    store = ConversationStore()
    service = conversation_service()(
        store=store,
        workspace_authorizer=WorkspaceAuthorizer(OwnerStore(None)),
    )

    with pytest.raises(KnoraError, match="WORKSPACE_ACCESS_DENIED"):
        service.read(identity, "foreign-workspace", "private-conversation")

    assert store.calls == []


@pytest.mark.parametrize("title", ["", "   ", "x" * 121])
def test_rename_rejects_invalid_title_before_persistence(title: str) -> None:
    identity = Identity("https://issuer", "owner")
    owners = OwnerStore(Identity(identity.issuer, identity.subject))
    store = ConversationStore()
    service = conversation_service()(
        store=store,
        workspace_authorizer=WorkspaceAuthorizer(owners),
    )

    with pytest.raises(KnoraError, match="INVALID_CONVERSATION_TITLE"):
        service.rename(identity, "workspace-1", "conversation-1", title, expected_revision=0)

    assert store.calls == []


def test_title_from_question_collapses_whitespace_and_caps_at_eighty_characters() -> None:
    service_module = conversation_service_module()

    assert service_module.title_from_question("  Bao cao   gom may chuong?  ") == (
        "Bao cao gom may chuong?"
    )
    assert service_module.title_from_question("x" * 100) == "x" * 80


def test_turn_view_exposes_the_original_submitted_question() -> None:
    try:
        turn_view = import_module("knora.conversations.types").TurnView
    except ModuleNotFoundError as error:
        pytest.fail(f"Conversation types are not implemented: {error}", pytrace=False)

    original_question = "Why is this archived?"
    turn = turn_view(
        id="turn-1",
        conversation_id="conversation-1",
        sequence=1,
        question=original_question,
        status="queued",
        stage=None,
        result=None,
        error_code=None,
    )

    assert turn.question == original_question
