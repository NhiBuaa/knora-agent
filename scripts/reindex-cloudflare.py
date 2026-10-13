"""Inventory, stage and atomically activate retained Cloudflare embeddings."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "src"))

from knora.adapters.postgres.reembedding_store import (  # noqa: E402
    PostgresCloudflareReindexStore,
    ReindexInventory,
)
from knora.domain.errors import KnoraError  # noqa: E402
from knora.infrastructure.settings import Settings  # noqa: E402
from knora.providers.cloudflare.embedding import CloudflareEmbeddingProvider  # noqa: E402
from knora.providers.embedding import EmbeddingConfiguration  # noqa: E402


class _SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        print("error=REINDEX_ARGUMENT_INVALID", file=sys.stderr)
        raise SystemExit(2)


def apply(store, inventory: ReindexInventory, provider, config: EmbeddingConfiguration) -> int:
    if inventory.blockers or not inventory.eligible:
        raise KnoraError("REINDEX_POPULATION_INCOMPLETE")
    staged = {}
    newly_embedded = 0
    for document in inventory.eligible:
        existing = store.completed_set(document, config)
        if existing is not None:
            staged[document.document_id] = existing
            continue
        batch = provider.embed_documents([chunk.content for chunk in document.chunks], config)
        staged[document.document_id] = store.stage(document, config, batch)
        newly_embedded += 1
    store.activate(inventory, staged, config)
    return newly_embedded


def main(argv: list[str] | None = None) -> int:
    parser = _SafeArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument(
        "--apply", action="store_true", help="stage vectors and activate after full coverage"
    )
    action.add_argument("--cleanup", action="store_true", help="delete obsolete vectors after E2E")
    parser.add_argument("--workspace-id", action="append", default=[])
    parser.add_argument("--approve-unindexable-id", action="append", default=[])
    parser.add_argument("--acknowledge-data-permission", action="store_true")
    parser.add_argument("--acknowledge-free-quota", action="store_true")
    parser.add_argument("--e2e-confirmed", action="store_true")
    args = parser.parse_args(argv)
    mode = "apply" if args.apply else "cleanup" if args.cleanup else "inventory"
    if not os.environ.get("KNORA_DATABASE_URL"):
        print("error=KNORA_DATABASE_URL_REQUIRED", file=sys.stderr)
        return 2
    if args.apply and not (args.acknowledge_data_permission and args.acknowledge_free_quota):
        print("error=REINDEX_ACKNOWLEDGEMENTS_REQUIRED", file=sys.stderr)
        return 2
    if args.cleanup and not args.e2e_confirmed:
        print("error=REINDEX_E2E_CONFIRMATION_REQUIRED", file=sys.stderr)
        return 2
    try:
        settings = Settings(_env_file=None)
        config = EmbeddingConfiguration.cloudflare_qwen3_06b()
        if args.apply and (
            not settings.cloudflare_account_id
            or settings.cloudflare_api_token is None
            or not settings.cloudflare_api_token.get_secret_value()
        ):
            raise KnoraError("REINDEX_CLOUDFLARE_CREDENTIALS_REQUIRED")
        engine = create_engine(settings.database_url, pool_pre_ping=True)
        try:
            store = PostgresCloudflareReindexStore(sessionmaker(bind=engine))
            inventory = store.inventory(
                workspace_ids=tuple(args.workspace_id) if args.workspace_id else None,
                approved_unindexable_ids=tuple(args.approve_unindexable_id),
            )
            print(
                f"mode={mode} profile={config.id} workspaces={len(inventory.workspace_ids)} "
                f"total={len(inventory.document_ids)} eligible={len(inventory.eligible)} "
                f"unindexable={len(inventory.unindexable)} blockers={len(inventory.blockers)}"
            )
            for document in inventory.eligible:
                print(
                    f"eligible id={document.document_id} workspace={document.workspace_id} "
                    f"source={document.source_key} version={document.version_id} "
                    f"chunk_set={document.chunk_set_id} chunks={len(document.chunks)} "
                    f"active_profile={document.active_embedding_configuration_id or 'none'} "
                    f"active_vectors={document.active_vector_count} derivation=complete "
                    f"revision={document.revision} archived={str(document.archived).lower()}"
                )
            for document_id, reason in inventory.unindexable:
                print(f"unindexable id={document_id} reason={reason}")
            for document_id, reason in inventory.blockers:
                print(f"blocker id={document_id} reason={reason}")
            if mode == "inventory":
                return 0 if not inventory.blockers else 1
            if inventory.blockers:
                raise KnoraError("REINDEX_POPULATION_INCOMPLETE")
            if args.apply:
                provider = CloudflareEmbeddingProvider(
                    account_id=settings.cloudflare_account_id,
                    api_token=settings.cloudflare_api_token.get_secret_value(),
                    timeout_seconds=settings.cloudflare_timeout_seconds,
                )
                try:
                    count = apply(store, inventory, provider, config)
                finally:
                    provider.close()
                print(f"activated={len(inventory.eligible)} newly_embedded={count}")
            else:
                removed = store.cleanup(inventory, config, e2e_confirmed=True)
                print(f"obsolete_vectors_deleted={removed}")
            return 0
        finally:
            engine.dispose()
    except KnoraError as error:
        print(f"error={error.code}", file=sys.stderr)
        return 1
    except Exception:
        print("error=REINDEX_FAILED", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
