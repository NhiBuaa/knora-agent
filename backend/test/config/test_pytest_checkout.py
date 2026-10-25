"""Pytest must test this checkout even when an interpreter is shared."""

import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def checkout(path: Path, identity: str) -> Path:
    for name in ("pytest.ini", "conftest.py", "backend/pyproject.toml"):
        target = path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    package = path / "backend/src/knora"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(f"IDENTITY = {identity!r}\n", encoding="utf-8")
    tests = path / "backend/test"
    tests.mkdir()
    (tests / "test_origin.py").write_text(
        "import json, os\n"
        "from pathlib import Path\n"
        "import knora\n"
        "def test_origin(pytestconfig):\n"
        "    root = Path(__file__).resolve().parents[2]\n"
        "    assert Path(knora.__file__).resolve() == root / 'backend/src/knora/__init__.py'\n"
        "    assert pytestconfig.rootpath == root\n"
        "    assert pytestconfig.inipath == root / 'pytest.ini'\n"
        "    result = json.dumps({'identity': knora.IDENTITY})\n"
        "    Path(os.environ['CHECKOUT_RESULT']).write_text(result)\n",
        encoding="utf-8",
    )
    return path


def run_checkout(root: Path, foreign: Path, entrypoint: str, *, preload: bool = False):
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in {"PYTEST_ADDOPTS", "PYTEST_PLUGINS", "PYTHONPATH"}
    }
    environment.update(
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONPATH=str(foreign / "backend/src"),
        CHECKOUT_RESULT=str(root / "result.json"),
    )
    arguments = ["-p", "no:cacheprovider", "-q", f"--junitxml={root / 'report.xml'}"]
    if entrypoint == "backend":
        cwd = root / "backend"
        arguments += ["test/test_origin.py"]
    else:
        cwd = root
        if entrypoint == "explicit-config":
            arguments += ["-c", "pytest.ini"]
        elif entrypoint == "explicit-root":
            arguments += ["--rootdir=."]
        arguments += ["backend/test/test_origin.py"]
    command = [sys.executable, "-B"]
    if preload:
        command += [
            "-c",
            "import knora, pytest, sys; raise SystemExit(pytest.main(sys.argv[1:]))",
        ]
    else:
        command += ["-m", "pytest"]
    return subprocess.run(
        [*command, *arguments],
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


@pytest.mark.parametrize("entrypoint", ("root", "backend", "explicit-root", "explicit-config"))
def test_pytest_uses_its_checkout_despite_foreign_pythonpath(tmp_path: Path, entrypoint: str):
    first = checkout(tmp_path / "first", "first")
    second = checkout(tmp_path / "second", "second")
    pairs = ((first, second, "first"), (second, first, "second"))
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(run_checkout, own, foreign, entrypoint) for own, foreign, _ in pairs
        ]
        results = [future.result() for future in futures]
    for (own, _, identity), result in zip(pairs, results, strict=True):
        assert result.returncode == 0, result.stdout + result.stderr
        assert json.loads((own / "result.json").read_text()) == {"identity": identity}
        assert (own / "report.xml").is_file()
        assert not (own / ".pytest_cache").exists()
        assert not list(own.rglob("__pycache__"))
    assert not (first / "backend-report.xml").exists()
    assert not (second / "backend-report.xml").exists()


@pytest.mark.parametrize("entrypoint", ("root", "backend", "explicit-root", "explicit-config"))
def test_pytest_rejects_a_foreign_package_loaded_before_configuration(
    tmp_path: Path, entrypoint: str
):
    own = checkout(tmp_path / "own", "own")
    foreign = checkout(tmp_path / "foreign", "foreign")
    result = run_checkout(own, foreign, entrypoint, preload=True)
    assert result.returncode == pytest.ExitCode.USAGE_ERROR, result.stdout + result.stderr
    assert "KNORA_CHECKOUT_MISMATCH" in result.stderr
    expected_path = str((own / "backend/src/knora/__init__.py").resolve())
    actual_path = str((foreign / "backend/src/knora/__init__.py").resolve())
    assert f"expected={expected_path}" in result.stderr
    assert f"actual={actual_path}" in result.stderr
    assert not (own / "result.json").exists()
