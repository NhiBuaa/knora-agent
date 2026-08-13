from knora.answering.stores import RetrievalConfiguration


def resolve_retrieval_configuration(
    configuration_id: str, *, vector_min_similarity: float | None
) -> RetrievalConfiguration:
    if configuration_id == "retrieval-m1-v1":
        return RetrievalConfiguration.milestone_one()
    if configuration_id == "retrieval-m3-rrf-v1":
        return RetrievalConfiguration.milestone_three_hybrid()
    if vector_min_similarity is None:
        raise ValueError("v2 retrieval requires a passed calibrated numeric threshold")
    if configuration_id == "retrieval-m3-vector-v2":
        return RetrievalConfiguration.milestone_three_vector_v2(
            min_similarity=vector_min_similarity
        )
    if configuration_id == "retrieval-m3-rrf-v2":
        return RetrievalConfiguration.milestone_three_hybrid_v2(
            min_similarity=vector_min_similarity
        )
    raise ValueError("unsupported retrieval configuration")
