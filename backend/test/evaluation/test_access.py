import importlib

import pytest

from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError


def authorize(action, capabilities, *, principal_workspace="workspace-a"):
    policy = importlib.import_module("knora.evaluation.access")
    return policy.authorize_evaluation(
        workspace_id="workspace-a",
        principal=WorkspacePrincipal(principal_workspace, "owner-a", capabilities),
        action=action,
    )


@pytest.mark.parametrize("action", ["write", "upload", "approve", "run"])
def test_operator_read_does_not_authorize_evaluation_mutations(action):
    with pytest.raises(KnoraError, match="CAPABILITY_ACCESS_DENIED"):
        authorize(action, ("operator:read", "documents:write", "questions:ask"))


@pytest.mark.parametrize("action", ["write", "upload", "approve", "run"])
def test_legacy_api_key_does_not_implicitly_gain_new_evaluation_mutations(action):
    with pytest.raises(KnoraError, match="CAPABILITY_ACCESS_DENIED"):
        authorize(action, None)


def test_workspace_denial_precedes_capability_checks():
    with pytest.raises(KnoraError, match="WORKSPACE_ACCESS_DENIED"):
        authorize("run", (), principal_workspace="workspace-b")


@pytest.mark.parametrize(
    ("action", "capabilities"),
    [
        ("read", ("operator:read",)),
        ("read_source", ("operator:read", "documents:read")),
        ("write", ("operator:read", "evaluations:write")),
        ("upload", ("operator:read", "evaluations:write", "documents:write")),
        ("approve", ("operator:read", "evaluations:approve")),
        ("run", ("operator:read", "evaluations:run", "questions:ask")),
    ],
)
def test_explicit_workspace_capabilities_authorize_the_requested_action(action, capabilities):
    assert authorize(action, capabilities) is None


@pytest.mark.parametrize(
    ("action", "capabilities"),
    [
        ("read_source", ("operator:read",)),
        ("upload", ("operator:read", "evaluations:write")),
        ("run", ("operator:read", "evaluations:run")),
        ("write", ("evaluations:write",)),
    ],
)
def test_evaluation_permission_does_not_replace_document_question_or_operator_permission(
    action, capabilities
):
    with pytest.raises(KnoraError, match="CAPABILITY_ACCESS_DENIED"):
        authorize(action, capabilities)


def test_legacy_operator_read_retains_existing_compatibility():
    assert authorize("read", None) is None


def test_unknown_action_fails_closed():
    with pytest.raises(ValueError, match="Unknown evaluation action"):
        authorize("execute-shell", ("operator:read",))
