"""Registered native Milestone 3 dataset for the Evaluation Workbench."""

from dataclasses import dataclass
from pathlib import Path

from evals.datasets import milestone_3 as native_m3
from evals.datasets.milestone_3 import (
    Milestone3CorpusManifest,
    Milestone3Dataset,
    load_milestone_3_corpus_manifest,
    load_milestone_3_dataset,
    load_milestone_3_dataset_manifest,
    validate_milestone_3_references,
)

from knora.domain.errors import KnoraError
from knora.evaluation.contracts import LegacyDatasetReference


@dataclass(frozen=True)
class Milestone3CatalogEntry:
    reference: LegacyDatasetReference
    dataset: Milestone3Dataset
    corpus: Milestone3CorpusManifest


class Milestone3Catalog:
    def __init__(self, repository_root: Path | None = None) -> None:
        self._root = repository_root or Path(native_m3.__file__).resolve().parents[2]

    def list_datasets(self, workspace_id: str) -> tuple[Milestone3CatalogEntry, ...]:
        entry = self._load()
        return (entry,) if entry.reference.workspace_id == workspace_id else ()

    def get_dataset(self, workspace_id: str, dataset_id: str) -> Milestone3CatalogEntry:
        entry = self._load()
        if entry.reference.workspace_id != workspace_id or entry.reference.dataset_id != dataset_id:
            raise KnoraError("EVALUATION_DATASET_NOT_FOUND")
        return entry

    def _load(self) -> Milestone3CatalogEntry:
        dataset_path = self._root / "evals/datasets/milestone_3.jsonl"
        manifest_path = self._root / "evals/datasets/milestone_3.manifest.json"
        corpus_path = self._root / "evals/corpora/milestone_3/manifest.json"
        dataset = load_milestone_3_dataset(dataset_path)
        identity = load_milestone_3_dataset_manifest(manifest_path, dataset_path)
        corpus = load_milestone_3_corpus_manifest(corpus_path)
        validate_milestone_3_references(dataset, corpus)
        if identity.version != "m3-dataset-v1":
            raise ValueError("Unsupported M3 dataset version")
        return Milestone3CatalogEntry(
            LegacyDatasetReference(
                format="m3-native-v1",
                dataset_id=identity.version,
                version=1,
                workspace_id=corpus.workspace_id,
                native_digest=identity.checksum,
                metric_contract="m3-retrieval-metrics-v1",
            ),
            dataset,
            corpus,
        )
