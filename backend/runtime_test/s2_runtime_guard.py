"""Admission guards for the explicitly owned S2 test runtime."""

import hashlib
import json
import os
import re
from pathlib import Path

from sqlalchemy.engine import make_url

from knora.access.api_keys import ApiKeyAuthenticator, credentials_from_json


def require_owned_s2_database(value):
    url = make_url(value)
    if (
        os.environ.get("KNORA_S2_ISOLATED_TESTS") != "1"
        or (url.drivername, url.username, url.password, url.host, url.port, url.database)
        != ("postgresql+psycopg", "knora_s2", "isolated_s2", "127.0.0.1", 15433, "knora_153_s2")
        or dict(url.query) not in ({}, {"connect_timeout": "3"})
    ):
        raise ValueError(
            "the exact owned S2 database is required; connection overrides are forbidden"
        )


def require_reference_file(path, expected_sha256):
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha256:
        raise ValueError("runtime reference file does not match its approved SHA-256")


def selected_s2_volumes():
    run_id = os.environ.get("KNORA_S2_RUN_ID", "")
    if not re.fullmatch(r"[a-f0-9]{32}", run_id):
        raise ValueError("S2 run ID requires a 32-character lowercase hex UUID")
    expected_project = f"knora-retrieval-test-{run_id}"
    project = os.environ.get("KNORA_S2_PROJECT", expected_project)
    if project != expected_project:
        raise ValueError(f"S2 project must equal {expected_project}")

    expected_pg = f"{expected_project}_verification-pgdata"
    expected_qd = f"{expected_project}_verification-qdrantdata"

    pg_vol = os.environ.get("KNORA_S2_POSTGRES_VOLUME")
    if pg_vol is not None and pg_vol != expected_pg:
        raise ValueError(f"S2 volume requires exact project-scoped name {expected_pg}")
    qd_vol = os.environ.get("KNORA_S2_QDRANT_VOLUME")
    if qd_vol is not None and qd_vol != expected_qd:
        raise ValueError(f"S2 volume requires exact project-scoped name {expected_qd}")

    return {
        "postgres": expected_pg,
        "qdrant": expected_qd,
        "verification-postgres": expected_pg,
        "verification-qdrant": expected_qd,
    }


def require_owned_s2_storage(rows, root):
    volumes = selected_s2_volumes()
    try:
        by_service = {row["Config"]["Labels"]["com.docker.compose.service"]: row for row in rows}
        if len(rows) != 2 or set(by_service) != {"verification-postgres", "verification-qdrant"}:
            raise ValueError("S2 storage service identity is incomplete")
        run_id = os.environ.get("KNORA_S2_RUN_ID")
        expected_project = f"knora-retrieval-test-{run_id}"
        dev_compose = (root / "docker-compose.dev.yml").resolve()

        for service, cpu, memory, internal, port, destination, vol_key in (
            (
                "verification-postgres",
                1,
                1024,
                "5432/tcp",
                "15433",
                "/var/lib/postgresql/data",
                "postgres",
            ),
            (
                "verification-qdrant",
                2,
                2048,
                "6333/tcp",
                "16433",
                "/qdrant/storage",
                "qdrant",
            ),
        ):
            row = by_service[service]
            labels = row["Config"]["Labels"]
            working_dir = labels.get("com.docker.compose.project.working_dir", "")
            config_files = labels.get("com.docker.compose.project.config_files", "")
            mounts = [mount for mount in row["Mounts"] if mount["Destination"] == destination]
            ports = {key: value for key, value in row["NetworkSettings"]["Ports"].items() if value}
            if (
                not re.fullmatch(r"[a-f0-9]{64}", row["Id"])
                or not re.fullmatch(r"sha256:[a-f0-9]{64}", row["Image"])
                or not row["State"]["Running"]
                or row["State"]["Restarting"]
                or labels.get("com.docker.compose.project") != expected_project
                or not working_dir.strip()
                or Path(working_dir).resolve() != root.resolve()
                or not config_files.strip()
                or Path(config_files).resolve() != dev_compose
                or row["HostConfig"]["NanoCpus"] != cpu * 1_000_000_000
                or row["HostConfig"]["Memory"] != memory * 1024 * 1024
                or ports != {internal: [{"HostIp": "127.0.0.1", "HostPort": port}]}
                or len(mounts) != 1
                or mounts[0]["Type"] != "volume"
                or mounts[0]["Name"] != volumes[vol_key]
                or mounts[0]["RW"] is not True
            ):
                raise ValueError("S2 storage identity, resources or volume differs from admission")
    except (KeyError, TypeError) as exc:
        raise ValueError("S2 storage inspection is incomplete") from exc


def require_owned_s2_application_rows(rows, root):
    """Validate full S2 application and storage container rows against admission rules."""
    if len(rows) != 3:
        raise ValueError("S2 application admission requires exactly 3 container rows")

    by_service = {
        row.get("Config", {}).get("Labels", {}).get("com.docker.compose.service"): row
        for row in rows
    }
    if "verification-api" not in by_service:
        raise ValueError("verification-api container row is missing")

    api_row = by_service["verification-api"]
    storage = [r for r in rows if r is not api_row]
    require_owned_s2_storage(storage, root)

    run_id = os.environ.get("KNORA_S2_RUN_ID")
    expected_project = (
        f"knora-retrieval-test-{run_id}"
        if run_id
        else os.environ.get("KNORA_S2_PROJECT", "knora-153-s2")
    )
    dev_compose = (root / "docker-compose.dev.yml").resolve()

    if not re.fullmatch(r"[a-f0-9]{64}", str(api_row.get("Id", ""))):
        raise ValueError("API container Id differs from admission")
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", str(api_row.get("Image", ""))):
        raise ValueError("API container Image differs from admission")
    if not api_row.get("State", {}).get("Running") or api_row.get("State", {}).get("Restarting"):
        raise ValueError("API container must be running and not restarting")

    labels = api_row.get("Config", {}).get("Labels", {})
    if labels.get("com.docker.compose.project") != expected_project:
        raise ValueError("API project label differs from admission")

    working_dir = labels.get("com.docker.compose.project.working_dir", "")
    if not working_dir or not working_dir.strip() or Path(working_dir).resolve() != root.resolve():
        raise ValueError("API working_dir label differs from admission")

    config_files = labels.get("com.docker.compose.project.config_files", "")
    if not config_files or not config_files.strip() or Path(config_files).resolve() != dev_compose:
        raise ValueError("API config_files label differs from admission")

    if api_row.get("HostConfig", {}).get("NanoCpus") != 1_000_000_000:
        raise ValueError("API NanoCpus differs from admission")
    if api_row.get("HostConfig", {}).get("Memory") != 768 * 1024 * 1024:
        raise ValueError("API Memory differs from admission")

    ports = api_row.get("NetworkSettings", {}).get("Ports", {})
    if ports != {"8000/tcp": [{"HostIp": "127.0.0.1", "HostPort": "18053"}]}:
        raise ValueError("API port mapping differs from admission")

    env_list = api_row.get("Config", {}).get("Env", [])
    settings = dict(item.split("=", 1) for item in env_list if "=" in item)
    for name in ("PROVIDER_MODE", "EMBEDDING_PROVIDER", "GENERATION_PROVIDER"):
        if settings.get("KNORA_" + name) != "deterministic-local":
            raise ValueError(f"API KNORA_{name} must be deterministic-local")

    if settings.get("KNORA_DATABASE_URL") != (
        "postgresql+psycopg://knora_s2:isolated_s2@postgres:5432/knora_153_s2"
    ):
        raise ValueError("API database URL differs from admission")
    if settings.get("KNORA_RETRIEVAL_CONFIGURATION_ID") != (
        "retrieval-bm25-upload-fixture-top8-v1"
    ):
        raise ValueError("API retrieval configuration ID differs from admission")
    if settings.get("KNORA_LEXICAL_QDRANT_URL") != "http://qdrant:6333":
        raise ValueError("API lexical Qdrant URL differs from admission")
    if settings.get("KNORA_LEXICAL_POPULATION_MANIFEST") != (
        "/app/evals/fixtures/pdf_retrieval_v3_s2/upload-lexical-population-v1.json"
    ):
        raise ValueError("API lexical population manifest differs from admission")
    if settings.get("KNORA_OBJECT_STORE_BACKEND") != "filesystem":
        raise ValueError("API object store backend must be filesystem")
    if settings.get("KNORA_OBJECT_STORE_ROOT") != "/s2-objects":
        raise ValueError("API object store root must be /s2-objects")

    if "KNORA_S2_OBJECT_STORE_ROOT" in os.environ:
        obj_root = Path(os.environ["KNORA_S2_OBJECT_STORE_ROOT"]).resolve()
        if "KNORA_S2_EVIDENCE_ROOT" in os.environ:
            evidence_root = Path(os.environ["KNORA_S2_EVIDENCE_ROOT"]).resolve()
            expected_obj = evidence_root / "http-objects"
            if obj_root != expected_obj:
                raise ValueError("API object store root mismatch with evidence root")
        mounts = [m for m in api_row.get("Mounts", []) if m.get("Destination") == "/s2-objects"]
        if len(mounts) != 1 or mounts[0].get("Type") != "bind" or not mounts[0].get("RW"):
            raise ValueError("API /s2-objects bind mount differs from admission")
        if Path(mounts[0].get("Source", "")).resolve() != obj_root:
            raise ValueError("API bind mount source differs from admission")

    if (
        "KNORA_S2_APPLICATION_COLLECTION" in os.environ
        and settings.get("KNORA_LEXICAL_QDRANT_COLLECTION")
        != os.environ["KNORA_S2_APPLICATION_COLLECTION"]
    ):
        raise ValueError("API collection differs from admission")

    if "KNORA_S2_HTTP_API_KEY" in os.environ:
        try:
            credentials = credentials_from_json(settings.get("KNORA_API_CREDENTIALS_JSON", ""))
            principal = ApiKeyAuthenticator(credentials).authenticate(
                os.environ["KNORA_S2_HTTP_API_KEY"]
            )
            if (
                len(credentials) != 1
                or principal.workspace_id != os.environ["KNORA_S2_HTTP_WORKSPACE_ID"]
            ):
                raise ValueError("credential owner differs")
        except Exception:
            raise ValueError("API credentials differ from admission") from None

    return api_row


def reserve_native_request(request, calls, *, limit, collection=None, query_limit=None):
    """Count attempted sends, including lost responses; response hooks only record results."""
    url = request.url
    if (url.scheme, url.host, url.port) != ("http", "127.0.0.1", 16433):
        raise ValueError("native target differs from the owned S2 endpoint")
    if collection is not None:
        prefix = "/collections/" + collection
        if url.path != prefix and not url.path.startswith(prefix + "/"):
            raise ValueError("native target differs from the owned collection")
    if len(calls) >= limit:
        raise ValueError("native call budget exhausted before send")
    if (
        query_limit is not None
        and url.path.endswith("/points/query")
        and sum(call["url"].split("?")[0].endswith("/points/query") for call in calls)
        >= query_limit
    ):
        raise ValueError("native query budget exhausted before send")
    record = {
        "method": request.method,
        "url": str(url),
        "request": json.loads(request.content) if request.content else None,
    }
    calls.append(record)
    return record
