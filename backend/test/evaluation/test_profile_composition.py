"""Trusted application wiring is separate from browser configuration and live permission."""

from knora.domain.access import WorkspacePrincipal
from knora.evaluation.pdf_runtime import PdfRuntimeProfile
from knora.evaluation.proposals import ProposalProfile
from knora.evaluation.runs import RuntimeProfile
from knora.evaluation.scoring import ScoringProfile
from knora.main import create_app


def test_application_composes_explicit_profiles_without_preparing_or_calling_providers():
    calls = []

    def forbidden(*args):
        calls.append(args)
        raise AssertionError("Composition must not invoke providers or prepare a corpus")

    principal = WorkspacePrincipal("w1", "owner", ("operator:read", "documents:read"))
    app = create_app(
        evaluation_profiles=(RuntimeProfile("native", "offline", forbidden, forbidden),),
        evaluation_pdf_profiles=(PdfRuntimeProfile("pdf", "offline", forbidden, forbidden),),
        evaluation_proposal_profiles={
            "ragas": ProposalProfile("ragas", "offline", "fixture", "v1", forbidden)
        },
        evaluation_scoring_profiles=(
            ScoringProfile("judge", "offline", "fixture", "v1", {}, forbidden),
        ),
    )
    assert app.state.evaluation_runs.list_profiles("w1", principal) == [
        {"profile_id": "native", "kind": "offline", "status": "READY"},
        {"profile_id": "pdf", "kind": "offline", "status": "READY"},
        {"profile_id": "live", "kind": "live", "status": "BLOCKED"},
    ]
    assert app.state.dataset_service.proposal_profiles("w1", principal)[0]["profile_id"] == "ragas"
    assert app.state.evaluation_scoring._profiles["judge"].model == "fixture"
    assert calls == []


def test_default_application_has_no_executable_evaluation_profiles():
    app = create_app()
    principal = WorkspacePrincipal("w1", "owner", ("operator:read", "documents:read"))
    assert app.state.evaluation_runs.list_profiles("w1", principal) == [
        {"profile_id": "live", "kind": "live", "status": "BLOCKED"}
    ]
    assert app.state.dataset_service.proposal_profiles("w1", principal) == []
    assert app.state.evaluation_scoring._profiles == {}
