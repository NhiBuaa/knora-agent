"""Guard test to enforce that Docker Compose files targeting backend/Dockerfile

use the repository root as the build context.
"""

from pathlib import Path

import pytest

try:
    import yaml
except ImportError:
    yaml = None


def test_all_compose_backend_build_contexts():
    repo_root = Path(__file__).resolve().parents[2]
    compose_files = (repo_root / "docker-compose.yml", repo_root / "docker-compose.dev.yml")

    for compose_path in compose_files:
        text = compose_path.read_text(encoding="utf-8")

        # Fast text-based guard
        assert "build: ./backend" not in text, (
            f"In {compose_path}, found legacy string 'build: ./backend'. "
            f"Must specify context: . and dockerfile: backend/Dockerfile"
        )
        assert "context: ./backend" not in text, (
            f"In {compose_path}, found 'context: ./backend'. "
            f"backend/Dockerfile requires repo root context to include "
            f"pyproject.toml, evals, and docs."
        )

        # Structured validation if PyYAML is installed
        if yaml is not None:
            try:
                data = yaml.safe_load(text)
            except Exception as e:
                pytest.fail(f"Failed to parse compose file {compose_path}: {e}")

            if not isinstance(data, dict) or "services" not in data:
                continue

            for service_name, service_config in data["services"].items():
                if not isinstance(service_config, dict) or "build" not in service_config:
                    continue

                build = service_config["build"]
                if isinstance(build, dict):
                    dockerfile = build.get("dockerfile", "")
                    context = build.get("context", "")
                    if dockerfile == "backend/Dockerfile":
                        assert context in (".", str(repo_root)), (
                            f"In {compose_path}, service '{service_name}' specifies "
                            f"dockerfile: {dockerfile} but context is '{context}' "
                            f"instead of repository root '.'."
                        )
