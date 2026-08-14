from knora.answering.corpus_cutover_v2 import CorpusMember, evaluate_cutover


def test_cutover_requires_complete_new_embeddings_for_entire_population() -> None:
    pending = evaluate_cutover(
        (
            CorpusMember("a", "chunk-a", "chunk-a", True, True, True),
            CorpusMember("b", "chunk-b", "chunk-b", False, True, True),
        )
    )
    complete = evaluate_cutover(
        (
            CorpusMember("a", "chunk-a", "chunk-a", True, True, True),
            CorpusMember("b", "chunk-b", "chunk-b", True, True, True),
        )
    )

    assert pending.production_enablement_allowed is False
    assert pending.pending_source_keys == ("b",)
    assert complete.production_enablement_allowed is True


def test_cutover_rejects_rechunk_or_reused_or_mutated_v1_vectors() -> None:
    result = evaluate_cutover(
        (CorpusMember("a", "before", "after", True, False, False),)
    )

    assert result.production_enablement_allowed is False
    assert result.invariant_violations == (
        "a:CHUNK_SET_CHANGED",
        "a:V2_VECTOR_NOT_NEW",
        "a:V1_MUTATED",
    )
