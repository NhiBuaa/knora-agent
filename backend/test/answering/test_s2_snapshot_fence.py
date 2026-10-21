"""Application ordering at the lexical lifecycle boundary; no runtime claims."""

import pytest
from test_bm25_contract import LexicalStore, LocalGenerator, generation

from knora.answering.interface import QuestionCommand
from knora.answering.module import AnswerQuestion
from knora.answering.stores import RetrievalConfiguration
from knora.domain.access import WorkspacePrincipal
from knora.domain.errors import KnoraError


@pytest.mark.asyncio
async def test_archive_during_selection_prevents_generator_and_citations():
    class ArchivedStore(LexicalStore):
        archived = False

        def revalidate_lexical_snapshot(self, workspace_id, lexical_policy_id, generations):
            assert (workspace_id, lexical_policy_id, generations) == (
                "workspace",
                "bm25-word-frozen47-population-v1",
                (generation(),),
            )
            if self.archived:
                raise KnoraError("LEXICAL_RETRIEVAL_UNAVAILABLE")

    store = ArchivedStore()
    generator = LocalGenerator()
    service = AnswerQuestion(
        embedding_provider=None,
        embedding_configuration=None,
        generation_provider=generator,
        store=store,
        retrieval_configuration=RetrievalConfiguration.bm25_top8_v1(),
    )

    def archive_before_generation(stage):
        if stage == "generating":
            store.archived = True

    with pytest.raises(KnoraError, match="LEXICAL_RETRIEVAL_UNAVAILABLE"):
        await service.execute(
            QuestionCommand(workspace_id="workspace", question="Fact?"),
            WorkspacePrincipal(workspace_id="workspace", key_id="offline"),
            stage_callback=archive_before_generation,
        )
    assert generator.calls == 0
    assert store.traces == []
