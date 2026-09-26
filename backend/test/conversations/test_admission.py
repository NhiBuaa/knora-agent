from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from knora.access.identity import Identity
from knora.access.workspace_authorization import WorkspaceAuthorizer
from knora.conversations.service import ConversationService
from knora.domain.errors import KnoraError


class OwnerStore:
    def __init__(self, owner: Identity | None) -> None:
        self.owner = owner
        self.lookups: list[str] = []

    def owner_for(self, workspace_id: str) -> Identity | None:
        self.lookups.append(workspace_id)
        return self.owner


@dataclass
class RecordingConversationStore:
    calls: list[tuple[str, str, str, str, str, str]] = field(default_factory=list)
    result: object = field(default_factory=object)

    def submit_turn(
        self,
        workspace_id: str,
        conversation_id: str,
        idempotency_key: str,
        question: str,
        auto_title: str,
        request_fingerprint: str,
    ) -> object:
        self.calls.append(
            (
                workspace_id,
                conversation_id,
                idempotency_key,
                question,
                auto_title,
                request_fingerprint,
            )
        )
        return self.result


def service_for(
    identity: Identity | None,
) -> tuple[ConversationService, OwnerStore, RecordingConversationStore]:
    owner_store = OwnerStore(identity)
    conversation_store = RecordingConversationStore()
    service = ConversationService(
        store=conversation_store,
        workspace_authorizer=WorkspaceAuthorizer(owner_store),
    )
    return service, owner_store, conversation_store


def test_submit_turn_preserves_original_question_and_fingerprints_normalized_text() -> None:
    identity = Identity("https://issuer", "owner", ("questions:ask",))
    owner = Identity(identity.issuer, identity.subject)
    service, owner_store, store = service_for(owner)
    original_question = "  Why  is this archived?  "

    result = service.submit_turn(
        identity,
        "workspace-1",
        "conversation-1",
        "request-key-1",
        original_question,
    )

    assert result is store.result
    assert owner_store.lookups == ["workspace-1"]
    assert store.calls == [
        (
            "workspace-1",
            "conversation-1",
            "request-key-1",
            original_question,
            "Why is this archived?",
            "39817aa493faa5bb019ad5257e55d3d4b7a4e8eba99db66c25d68aaa512c10e3",
        )
    ]


def test_foreign_workspace_is_denied_before_turn_admission() -> None:
    identity = Identity("https://issuer", "intruder", ("questions:ask",))
    service, owner_store, store = service_for(None)

    with pytest.raises(KnoraError, match="WORKSPACE_ACCESS_DENIED"):
        service.submit_turn(
            identity,
            "workspace-private",
            "conversation-private",
            "request-key-1",
            "What is in this conversation?",
        )

    assert owner_store.lookups == ["workspace-private"]
    assert store.calls == []


def test_missing_questions_capability_is_denied_before_turn_admission() -> None:
    identity = Identity("https://issuer", "owner")
    service, owner_store, store = service_for(Identity(identity.issuer, identity.subject))

    with pytest.raises(KnoraError, match="CAPABILITY_ACCESS_DENIED"):
        service.submit_turn(
            identity,
            "workspace-1",
            "conversation-1",
            "request-key-1",
            "What is in this conversation?",
        )

    assert owner_store.lookups == ["workspace-1"]
    assert store.calls == []


def test_invalid_idempotency_key_is_rejected_without_persistence() -> None:
    identity = Identity("https://issuer", "owner", ("questions:ask",))
    service, _, store = service_for(Identity(identity.issuer, identity.subject))

    with pytest.raises(KnoraError, match="INVALID_IDEMPOTENCY_KEY"):
        service.submit_turn(
            identity,
            "workspace-1",
            "conversation-1",
            "",
            "What is in this conversation?",
        )

    assert store.calls == []
