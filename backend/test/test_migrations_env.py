from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_offline_migrations_accept_percent_encoded_database_password() -> None:
    environment = os.environ.copy()
    environment["KNORA_DATABASE_URL"] = (
        "postgresql+psycopg://postgres.example:encoded%25password@"
        "db.example:5432/postgres?sslmode=require"
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            "backend/alembic.ini",
            "upgrade",
            "20260810_0025",
            "--sql",
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
