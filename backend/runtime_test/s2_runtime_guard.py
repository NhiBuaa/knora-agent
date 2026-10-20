"""Admission guards for the explicitly owned S2 test runtime."""

import hashlib
import json
import os
import re
from pathlib import Path

from sqlalchemy.engine import make_url


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
    volumes = {}
    for service, variable, prefix in (
        ("postgres", "KNORA_S2_POSTGRES_VOLUME", "knora-153-s2-pgdata-"),
        ("qdrant", "KNORA_S2_QDRANT_VOLUME", "knora-153-s2-qdrantdata-"),
    ):
        value = os.environ.get(variable, "")
        if not re.fullmatch(prefix + r"[a-f0-9]{32}", value):
            raise ValueError("S2 volume requires an explicit fresh run UUID")
        volumes[service] = value
    return volumes


def require_owned_s2_storage(rows, root):
    volumes = selected_s2_volumes()
    try:
        by_service = {row["Config"]["Labels"]["com.docker.compose.service"]: row for row in rows}
        if len(rows) != 2 or set(by_service) != {"postgres", "qdrant"}:
            raise ValueError("S2 storage service identity is incomplete")
        for service, cpu, memory, internal, port, destination in (
            ("postgres", 1, 1024, "5432/tcp", "15433", "/var/lib/postgresql/data"),
            ("qdrant", 2, 2048, "6333/tcp", "16433", "/qdrant/storage"),
        ):
            row = by_service[service]
            labels = row["Config"]["Labels"]
            mounts = [mount for mount in row["Mounts"] if mount["Destination"] == destination]
            ports = {key: value for key, value in row["NetworkSettings"]["Ports"].items() if value}
            if (
                not re.fullmatch(r"[a-f0-9]{64}", row["Id"])
                or not re.fullmatch(r"sha256:[a-f0-9]{64}", row["Image"])
                or not row["State"]["Running"]
                or row["State"]["Restarting"]
                or labels["com.docker.compose.project"] != "knora-153-s2"
                or Path(labels["com.docker.compose.project.working_dir"]).resolve()
                != root.resolve()
                or Path(labels["com.docker.compose.project.config_files"]).resolve()
                != (root / "docker-compose.s2.yml").resolve()
                or row["HostConfig"]["NanoCpus"] != cpu * 1_000_000_000
                or row["HostConfig"]["Memory"] != memory * 1024 * 1024
                or ports != {internal: [{"HostIp": "127.0.0.1", "HostPort": port}]}
                or len(mounts) != 1
                or mounts[0]["Type"] != "volume"
                or mounts[0]["Name"] != volumes[service]
                or mounts[0]["RW"] is not True
            ):
                raise ValueError("S2 storage identity, resources or volume differs from admission")
    except (KeyError, TypeError) as exc:
        raise ValueError("S2 storage inspection is incomplete") from exc


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
