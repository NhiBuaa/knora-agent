from __future__ import annotations

import time
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from knora.access.identity import Identity
from knora.access.keycloak import KeycloakAuthenticator
from knora.access.workspace_authorization import WorkspaceAuthorizer
from knora.answering.interface import QuestionResult
from knora.conversations.service import ConversationService
from knora.conversations.types import (
    ConversationPage,
    ConversationView,
    TurnAdmission,
    TurnPage,
    TurnView,
)
from knora.domain.errors import KnoraError
from knora.main import create_app


def make_turn(status: str = "answered") -> TurnView:
    result = QuestionResult(
        decision="ANSWER",
        answer="The guide suggests seven chapters.",
        citations=(),
        refusal_reason=None,
        trace_id="trace-1",
        workspace_id="workspace-1",
    )
    return TurnView(
        id="turn-1",
        conversation_id="conversation-1",
        sequence=1,
        question="How many chapters does the guide suggest?",
        status=status,
        stage=None,
        result=result if status == "answered" else None,
        error_code=None,
    )


class ConversationServiceFake:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.busy = False
        self.replayed = False
        self.submitted_turn: TurnView | None = None
        self.conversation = ConversationView(
            id="conversation-1",
            workspace_id="workspace-1",
            title="New conversation",
            title_source="auto",
            archived=False,
            revision=0,
            updated_at=datetime(2026, 9, 26, tzinfo=UTC),
        )

    def create(self, identity, workspace_id, idempotency_key):
        self.calls.append(("create", workspace_id, idempotency_key))
        return self.conversation

    def list(self, identity, workspace_id, archived=False, cursor=None, limit=20):
        self.calls.append(("list", workspace_id, archived, cursor, limit))
        return ConversationPage((self.conversation,), "older-conversations")

    def read(self, identity, workspace_id, conversation_id):
        self.calls.append(("read", workspace_id, conversation_id))
        return self.conversation

    def rename(self, identity, workspace_id, conversation_id, title, expected_revision):
        self.calls.append(("rename", workspace_id, conversation_id, title, expected_revision))
        self.conversation = ConversationView(
            id=conversation_id,
            workspace_id=workspace_id,
            title=title,
            title_source="manual",
            archived=self.conversation.archived,
            revision=expected_revision + 1,
            updated_at=self.conversation.updated_at,
        )
        return self.conversation

    def archive(self, identity, workspace_id, conversation_id, expected_revision):
        self.calls.append(("archive", workspace_id, conversation_id, expected_revision))
        self.conversation = ConversationView(
            id=conversation_id,
            workspace_id=workspace_id,
            title=self.conversation.title,
            title_source=self.conversation.title_source,
            archived=True,
            revision=expected_revision + 1,
            updated_at=self.conversation.updated_at,
        )
        return self.conversation

    def restore(self, identity, workspace_id, conversation_id, expected_revision):
        self.calls.append(("restore", workspace_id, conversation_id, expected_revision))
        self.conversation = ConversationView(
            id=conversation_id,
            workspace_id=workspace_id,
            title=self.conversation.title,
            title_source=self.conversation.title_source,
            archived=False,
            revision=expected_revision + 1,
            updated_at=self.conversation.updated_at,
        )
        return self.conversation

    def list_turns(self, identity, workspace_id, conversation_id, cursor=None, limit=50):
        self.calls.append(("list_turns", workspace_id, conversation_id, cursor, limit))
        return TurnPage((make_turn(),), "older-page")

    def get_turn(self, identity, workspace_id, conversation_id, turn_id):
        self.calls.append(("get_turn", workspace_id, conversation_id, turn_id))
        return make_turn()

    def submit_turn(
        self, identity, workspace_id, conversation_id, idempotency_key, question
    ):
        self.calls.append(
            ("submit_turn", workspace_id, conversation_id, idempotency_key, question)
        )
        if self.busy:
            raise KnoraError("CONVERSATION_BUSY")
        return TurnAdmission(
            self.submitted_turn or make_turn("queued"),
            replayed=self.replayed,
        )


def make_client(
    service: ConversationServiceFake, *, capabilities: list[str] | None = None
) -> TestClient:
    authenticator = KeycloakAuthenticator(
        issuer="https://issuer",
        audience="knora-api",
        token_validator=lambda _: {
            "iss": "https://issuer",
            "aud": "knora-api",
            "exp": time.time() + 60,
            "sub": "alice",
            "capabilities": ["questions:ask"] if capabilities is None else capabilities,
        },
    )
    application = create_app(keycloak_authenticator=authenticator)
    application.state.conversation_service = service
    return TestClient(application)


def test_history_and_status_return_original_question_without_caching() -> None:
    service = ConversationServiceFake()
    client = make_client(service)
    headers = {"Authorization": "Bearer token"}
    path = "/v1/workspaces/workspace-1/conversations/conversation-1/turns"

    history = client.get(path, headers=headers)
    status = client.get(f"{path}/turn-1", headers=headers)

    assert history.status_code == 200
    assert history.json()["items"][0]["question"] == make_turn().question
    assert history.json()["next_cursor"] == "older-page"
    assert history.headers["Cache-Control"] == "no-store"
    assert status.status_code == 200
    assert status.json()["question"] == make_turn().question
    assert status.json()["result"]["answer"] == "The guide suggests seven chapters."
    assert status.headers["Cache-Control"] == "no-store"
    assert service.calls == [
        ("list_turns", "workspace-1", "conversation-1", None, 50),
        ("get_turn", "workspace-1", "conversation-1", "turn-1"),
    ]


def test_conversation_lifecycle_routes_keep_workspace_owner_contracts() -> None:
    service = ConversationServiceFake()
    client = make_client(service)
    headers = {
        "Authorization": "Bearer token",
        "Idempotency-Key": "conversation-create-1",
    }
    path = "/v1/workspaces/workspace-1/conversations"

    missing_key = client.post(path, headers={"Authorization": "Bearer token"})
    created = client.post(path, headers=headers)
    listed = client.get(path, headers={"Authorization": "Bearer token"})
    read = client.get(f"{path}/conversation-1", headers=headers)
    renamed = client.patch(
        f"{path}/conversation-1",
        json={"title": "A useful title"},
        headers={**headers, "If-Match": '"0"'},
    )
    archived = client.post(
        f"{path}/conversation-1/archive",
        headers={**headers, "If-Match": '"1"'},
    )
    restored = client.post(
        f"{path}/conversation-1/restore",
        headers={**headers, "If-Match": '"2"'},
    )

    assert missing_key.status_code == 400
    assert missing_key.json()["error"]["code"] == "MISSING_IDEMPOTENCY_KEY"
    assert created.status_code == 201
    assert created.json()["title"] == "New conversation"
    assert listed.status_code == 200
    assert listed.json()["items"][0]["id"] == "conversation-1"
    assert listed.json()["next_cursor"] == "older-conversations"
    assert read.status_code == 200
    assert renamed.json()["title"] == "A useful title"
    assert renamed.json()["title_source"] == "manual"
    assert archived.json()["archived"] is True
    assert restored.json()["archived"] is False
    assert all(
        response.headers["Cache-Control"] == "no-store"
        for response in (created, listed, read, renamed, archived, restored)
    )


def test_new_turn_returns_status_location_and_busy_turn_returns_retryable_conflict() -> None:
    service = ConversationServiceFake()
    client = make_client(service)
    headers = {
        "Authorization": "Bearer token",
        "Idempotency-Key": "request-1",
    }
    path = "/v1/workspaces/workspace-1/conversations/conversation-1/turns"
    question = "How many chapters does the guide suggest?"

    accepted = client.post(path, json={"question": question}, headers=headers)

    assert accepted.status_code == 202
    assert accepted.headers["Location"] == f"{path}/turn-1"
    assert accepted.headers["Cache-Control"] == "no-store"
    assert accepted.json()["question"] == question

    service.busy = True
    busy = client.post(
        path,
        json={"question": question},
        headers={**headers, "Idempotency-Key": "request-2"},
    )

    assert busy.status_code == 409
    assert busy.json()["error"]["code"] == "CONVERSATION_BUSY"
    assert busy.headers["Retry-After"] == "2"
    assert busy.headers["Cache-Control"] == "no-store"

    service.busy = False
    service.replayed = True
    service.submitted_turn = make_turn()
    replayed = client.post(path, json={"question": question}, headers=headers)

    assert replayed.status_code == 200
    assert replayed.json()["status"] == "answered"
    assert replayed.json()["question"] == question
    assert replayed.headers["Location"] == f"{path}/turn-1"


def test_history_authorizes_workspace_owner_before_turn_lookup() -> None:
    owner = Identity("https://issuer", "bob")

    class OwnershipStore:
        def owner_for(self, workspace_id):
            return owner

    class ReadStore:
        def __init__(self):
            self.calls = []

        def list_turns(self, *args, **kwargs):
            self.calls.append((args, kwargs))
            return TurnPage((), None)

    read_store = ReadStore()
    service = ConversationService(
        store=read_store,
        workspace_authorizer=WorkspaceAuthorizer(OwnershipStore()),
    )
    client = make_client(service)
    response = client.get(
        "/v1/workspaces/workspace-1/conversations/conversation-1/turns",
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "WORKSPACE_ACCESS_DENIED"
    assert read_store.calls == []


def test_workspace_owner_can_read_retained_history_without_ask_capability() -> None:
    owner = Identity("https://issuer", "alice")

    class OwnershipStore:
        def owner_for(self, workspace_id):
            return owner

    class ReadStore:
        def get(self, workspace_id, conversation_id):
            return ConversationView(
                id=conversation_id,
                workspace_id=workspace_id,
                title="Archived Conversation",
                title_source="manual",
                archived=True,
                revision=2,
                updated_at=datetime(2026, 9, 26, tzinfo=UTC),
            )

        def list_turns(self, workspace_id, conversation_id, cursor=None, limit=50):
            return TurnPage((make_turn(),), None)

    service = ConversationService(
        store=ReadStore(),
        workspace_authorizer=WorkspaceAuthorizer(OwnershipStore()),
    )
    client = make_client(service, capabilities=[])
    response = client.get(
        "/v1/workspaces/workspace-1/conversations/conversation-1/turns",
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 200
    assert response.json()["items"][0]["question"] == make_turn().question
