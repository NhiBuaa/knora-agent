"""Admission guards for the explicitly owned S2 test runtime."""

import hashlib
import os

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
