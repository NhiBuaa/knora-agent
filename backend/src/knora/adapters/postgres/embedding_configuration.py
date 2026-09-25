"""Reconstruct immutable embedding identity from PostgreSQL rows."""

from knora.adapters.postgres.tables import EmbeddingConfigurationTable
from knora.providers.embedding import EmbeddingConfiguration


def configuration_from_row(row: EmbeddingConfigurationTable) -> EmbeddingConfiguration:
    return EmbeddingConfiguration(
        id=row.id,
        provider=row.provider,
        model=row.model,
        dimensions=row.dimensions,
        distance_metric=row.distance_metric,
        deployment_identity=row.deployment_identity,
        api_contract_version=row.api_contract_version,
        input_normalization=row.input_normalization,
        input_policy_id=row.input_policy_id,
        output_dimensionality=row.output_dimensionality,
        vector_normalization=row.vector_normalization,
    )
