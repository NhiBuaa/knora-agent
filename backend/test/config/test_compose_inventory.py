"""Comprehensive inventory and scan tests for Docker Compose sources.

Ensures that repository-maintained Docker Compose sources are strictly bounded
to at most two canonical entrypoints:
  - docker-compose.yml
  - docker-compose.dev.yml
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]

IGNORED_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "vendor",
    "cache",
    ".cache",
    ".pytest_cache",
    ".verification",
    "evidence",
    "history",
}

CONVENTIONAL_COMPOSE_RE = re.compile(
    r"^(docker-compose.*|compose|compose\..*)\.(ya?ml)$",
    re.IGNORECASE,
)

COMPOSE_CMD_RE = re.compile(
    r"\bdocker(?:\.exe)?(?:-compose|\s+(?:-[^;\n\r|&]*?\s+)?compose)\b"
    r"(?P<args>[^;\n\r|&]+)",
    re.IGNORECASE,
)
FILE_FLAG_RE = re.compile(r"(?:^|\s)(?:-f|--file)(?:\s+|=)(?:\"([^\"]+)\"|'([^']+)'|([^\s'\";]+))")
COMPOSE_FILE_ASSIGN_RE = re.compile(
    r"^\s*(?:export\s+|\$env:)?COMPOSE_FILE\s*=\s*(['\"]?)(.+?)\1\s*$",
    re.MULTILINE | re.IGNORECASE,
)

NON_CODE_EXTENSIONS = {
    ".md",
    ".markdown",
    ".rst",
    ".txt",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".pdf",
    ".lock",
}


def _is_ignored(rel: Path) -> bool:
    return any(part in IGNORED_DIRS for part in rel.parts)


def _resolve_owned_file(target_str: str, base_dir: Path, root: Path) -> Path | None:
    clean = target_str.strip("'\" \t\r\n")
    if not clean or clean.startswith(("$", "%", "{", "<")):
        # shortcut: literal paths only; review dynamic callers when adding launchers.
        return None
    root_res = root.resolve()
    outside_root = False
    for candidate in (base_dir / clean, root / clean):
        try:
            cand_res = candidate.resolve()
            cand_res.relative_to(root_res)
        except ValueError:
            outside_root = True
            continue
        except OSError:
            continue
        if cand_res.is_file():
            return cand_res
    if outside_root:
        raise ValueError("COMPOSE_REFERENCE_OUTSIDE_ROOT")
    return None


def _mapping_fields(
    node: yaml.Node | None, active: frozenset[int] = frozenset()
) -> dict[str, yaml.Node]:
    if not isinstance(node, yaml.MappingNode) or id(node) in active:
        return {}
    active = active | {id(node)}
    fields = {}
    for key, value in node.value:
        if key.tag == "tag:yaml.org,2002:merge":
            merged = value.value if isinstance(value, yaml.SequenceNode) else [value]
            for source in reversed(merged):
                fields.update(_mapping_fields(source, active))
    for key, value in node.value:
        if isinstance(key, yaml.ScalarNode) and key.tag != "tag:yaml.org,2002:merge":
            fields[key.value] = value
    return fields


def _extract_include_paths(node: yaml.Node, active: frozenset[int] = frozenset()) -> list[str]:
    if id(node) in active:
        return []
    active = active | {id(node)}
    paths: list[str] = []
    if isinstance(node, yaml.ScalarNode):
        paths.append(node.value)
    elif isinstance(node, yaml.MappingNode):
        value = _mapping_fields(node).get("path")
        if value is not None:
            paths.extend(_extract_include_paths(value, active))
    elif isinstance(node, yaml.SequenceNode):
        for item in node.value:
            paths.extend(_extract_include_paths(item, active))
    return paths


def _extract_services_extends_paths(services_node: yaml.MappingNode) -> list[str]:
    paths: list[str] = []
    for svc_body in _mapping_fields(services_node).values():
        extends = _mapping_fields(svc_body).get("extends")
        target = _mapping_fields(extends).get("file")
        if isinstance(target, yaml.ScalarNode):
            paths.append(target.value)
    return paths


def _extract_yaml_references(nodes: list[yaml.Node]) -> list[str]:
    refs: list[str] = []
    for doc in nodes:
        for key, v_node in _mapping_fields(doc).items():
            if key == "include":
                refs.extend(_extract_include_paths(v_node))
            elif key == "services" and isinstance(v_node, yaml.MappingNode):
                refs.extend(_extract_services_extends_paths(v_node))
    return refs


def _is_compose_yaml(nodes: list[yaml.Node]) -> bool:
    for doc in nodes:
        fields = _mapping_fields(doc)
        if isinstance(fields.get("services"), yaml.MappingNode) or "include" in fields:
            return True
    return False


def compose_sources(root: Path) -> set[str]:
    """Discover repository-maintained Docker Compose sources and references."""
    root_res = root.resolve()
    git_marker = root / ".git"
    candidate_files: list[Path] = []

    if git_marker.exists():
        proc = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=root,
            capture_output=True,
            check=True,
        )
        raw_output = proc.stdout.decode("utf-8", errors="replace")
        for item in raw_output.split("\0"):
            if not item:
                continue
            rel = Path(item)
            if _is_ignored(rel):
                continue
            full_path = root / rel
            if full_path.is_file() and not full_path.is_symlink():
                try:
                    full_path.resolve().relative_to(root_res)
                    candidate_files.append(full_path)
                except (ValueError, OSError):
                    pass
    else:
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            dp = Path(dirpath)
            dirnames[:] = [
                d
                for d in dirnames
                if d not in IGNORED_DIRS
                and not (dp / d).is_symlink()
                and (dp / d).resolve().is_relative_to(root_res)
            ]
            for fname in filenames:
                fp = dp / fname
                if fp.is_file() and not fp.is_symlink():
                    try:
                        rel = fp.relative_to(root)
                        if not _is_ignored(rel):
                            fp.resolve().relative_to(root_res)
                            candidate_files.append(fp)
                    except (ValueError, OSError):
                        pass

    found: set[str] = set()
    compose_queue: list[Path] = []

    for fp in candidate_files:
        rel_posix = fp.relative_to(root).as_posix()
        is_yaml = fp.suffix.lower() in (".yml", ".yaml")
        is_conventional = bool(CONVENTIONAL_COMPOSE_RE.match(fp.name))

        if is_conventional:
            found.add(rel_posix)
            compose_queue.append(fp)
        elif is_yaml:
            try:
                content = fp.read_text(encoding="utf-8", errors="replace")
                nodes = list(yaml.compose_all(content, Loader=yaml.SafeLoader))
                if _is_compose_yaml(nodes):
                    found.add(rel_posix)
                    compose_queue.append(fp)
            except (yaml.YAMLError, OSError):
                pass

        if fp.suffix.lower() not in NON_CODE_EXTENSIONS:
            try:
                content = fp.read_text(encoding="utf-8", errors="replace")
            except OSError:
                content = ""
            if content:
                for m in COMPOSE_CMD_RE.finditer(content):
                    for groups in FILE_FLAG_RE.findall(m.group("args")):
                        target = next(value for value in groups if value)
                        resolved = _resolve_owned_file(target, fp.parent, root)
                        if resolved is not None:
                            r_rel = resolved.relative_to(root_res).as_posix()
                            if r_rel not in found:
                                found.add(r_rel)
                                compose_queue.append(resolved)
                for m in COMPOSE_FILE_ASSIGN_RE.finditer(content):
                    parts = re.split(r"(?<!^[a-zA-Z])(?<![;:\s][a-zA-Z])[:;]", m.group(2).strip())
                    for part in parts:
                        resolved = _resolve_owned_file(part.strip(), fp.parent, root)
                        if resolved is not None:
                            r_rel = resolved.relative_to(root_res).as_posix()
                            if r_rel not in found:
                                found.add(r_rel)
                                compose_queue.append(resolved)

    visited_queue: set[Path] = set()
    while compose_queue:
        current_fp = compose_queue.pop(0)
        if current_fp in visited_queue:
            continue
        visited_queue.add(current_fp)
        if _is_ignored(current_fp.relative_to(root_res)):
            continue

        try:
            content = current_fp.read_text(encoding="utf-8", errors="replace")
            nodes = list(yaml.compose_all(content, Loader=yaml.SafeLoader))
        except (yaml.YAMLError, OSError):
            nodes = []
        for ref_str in _extract_yaml_references(nodes):
            resolved = _resolve_owned_file(ref_str, current_fp.parent, root)
            if resolved is not None:
                r_rel = resolved.relative_to(root_res).as_posix()
                if r_rel not in found:
                    found.add(r_rel)
                    compose_queue.append(resolved)

    return found


def test_repo_has_exact_canonical_compose_sources() -> None:
    """The repository must have exactly two maintained Compose entrypoints."""
    expected = {
        "docker-compose.yml",
        "docker-compose.dev.yml",
    }
    actual = compose_sources(ROOT)
    assert actual == expected, (
        f"Compose inventory mismatch: extra={actual - expected}, missing={expected - actual}"
    )


@pytest.mark.parametrize(
    "path",
    [
        "test/fixtures/compose.yml",
        "nested/compose.yaml",
        "docker-compose.gate.yml",
        "nested/renamed.yaml",
    ],
)
def test_extra_compose_is_found(tmp_path: Path, path: str) -> None:
    candidate = tmp_path / path
    candidate.parent.mkdir(parents=True, exist_ok=True)
    candidate.write_text("services:\n  worker:\n    image: busybox\n", encoding="utf-8")
    assert path in compose_sources(tmp_path)


def test_nested_standard_compose_names_detected(tmp_path: Path) -> None:
    nested1 = tmp_path / "deep/sub/dir/compose.yml"
    nested1.parent.mkdir(parents=True, exist_ok=True)
    nested1.write_text("services:\n  app:\n    image: alpine\n", encoding="utf-8")

    nested2 = tmp_path / "another/sub/dir/docker-compose.yaml"
    nested2.parent.mkdir(parents=True, exist_ok=True)
    nested2.write_text("services:\n  db:\n    image: postgres\n", encoding="utf-8")

    sources = compose_sources(tmp_path)
    assert "deep/sub/dir/compose.yml" in sources
    assert "another/sub/dir/docker-compose.yaml" in sources


def test_renamed_yaml_with_services_mapping_detected(tmp_path: Path) -> None:
    renamed = tmp_path / "deploy/custom-topology.yaml"
    renamed.parent.mkdir(parents=True, exist_ok=True)
    renamed.write_text("services:\n  custom-worker:\n    image: worker:v1\n", encoding="utf-8")

    assert "deploy/custom-topology.yaml" in compose_sources(tmp_path)


def test_multidoc_yaml_services_in_second_doc_detected(tmp_path: Path) -> None:
    multi = tmp_path / "manifests/multi.yaml"
    multi.parent.mkdir(parents=True, exist_ok=True)
    content = (
        "---\n"
        "apiVersion: v1\n"
        "kind: ConfigMap\n"
        "metadata:\n"
        "  name: test-config\n"
        "---\n"
        "services:\n"
        "  service-in-doc-two:\n"
        "    image: redis:alpine\n"
    )
    multi.write_text(content, encoding="utf-8")

    assert "manifests/multi.yaml" in compose_sources(tmp_path)


def test_malformed_or_empty_standard_compose_name_recognized(tmp_path: Path) -> None:
    empty_compose = tmp_path / "sub/compose.yml"
    empty_compose.parent.mkdir(parents=True, exist_ok=True)
    empty_compose.write_text("", encoding="utf-8")

    malformed_compose = tmp_path / "nested/docker-compose.yml"
    malformed_compose.parent.mkdir(parents=True, exist_ok=True)
    malformed_compose.write_text("::invalid yaml:: {[[", encoding="utf-8")

    sources = compose_sources(tmp_path)
    assert "sub/compose.yml" in sources
    assert "nested/docker-compose.yml" in sources


def test_compose_include_only_external_thirdsource_flagged(tmp_path: Path) -> None:
    include_only = tmp_path / "nested/include-stack.yml"
    include_only.parent.mkdir(parents=True, exist_ok=True)
    include_only.write_text(
        "include:\n  - path: ./service-base.yml\n",
        encoding="utf-8",
    )

    sources = compose_sources(tmp_path)
    assert "nested/include-stack.yml" in sources


def test_compose_extends_file_external_thirdsource_flagged(tmp_path: Path) -> None:
    base = tmp_path / "docker-compose.yml"
    base.write_text(
        "services:\n"
        "  app:\n"
        "    extends:\n"
        "      file: common/base-services.yml\n"
        "      service: base-app\n",
        encoding="utf-8",
    )
    common = tmp_path / "common/base-services.yml"
    common.parent.mkdir(parents=True, exist_ok=True)
    common.write_text("services:\n  base-app:\n    image: base\n", encoding="utf-8")

    sources = compose_sources(tmp_path)
    assert "common/base-services.yml" in sources


def test_extends_outside_owned_root_must_not_follow_or_bless(tmp_path: Path) -> None:
    owned_root = tmp_path / "owned"
    owned_root.mkdir()
    outside = tmp_path / "outside.yml"
    outside.write_text("services:\n  external:\n    image: ext\n", encoding="utf-8")

    compose_file = owned_root / "docker-compose.yml"
    compose_file.write_text(
        "services:\n  app:\n    extends:\n      file: ../outside.yml\n      service: external\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="COMPOSE_REFERENCE_OUTSIDE_ROOT"):
        compose_sources(owned_root)


def test_normal_ci_workflow_and_non_compose_yaml_not_false_positive(tmp_path: Path) -> None:
    workflow = tmp_path / ".github/workflows/ci.yml"
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow_content = (
        "name: CI\n"
        "on: [push]\n"
        "jobs:\n"
        "  build:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - run: echo 'build with services in comment'\n"
    )
    workflow.write_text(workflow_content, encoding="utf-8")

    realm = tmp_path / "test/fixtures/keycloak/realm-config.yaml"
    realm.parent.mkdir(parents=True, exist_ok=True)
    realm.write_text("realm: test\nenabled: true\nroles:\n  - name: admin\n", encoding="utf-8")

    scalar_services = tmp_path / "config/settings.yaml"
    scalar_services.parent.mkdir(parents=True, exist_ok=True)
    scalar_services.write_text("app_name: demo\nservices: disabled\n", encoding="utf-8")

    sources = compose_sources(tmp_path)
    assert ".github/workflows/ci.yml" not in sources
    assert "test/fixtures/keycloak/realm-config.yaml" not in sources
    assert "config/settings.yaml" not in sources


def test_avoid_blanket_string_match_on_services_scalar_or_comment(tmp_path: Path) -> None:
    doc = tmp_path / "documentation.yaml"
    doc.write_text(
        "description: |\n"
        "  services: this is text inside a multiline scalar\n"
        "  not a top-level mapping.\n",
        encoding="utf-8",
    )
    comment = tmp_path / "commented.yaml"
    comment.write_text(
        "# services:\n#   app:\n#     image: redis\ntitle: commented sample\n",
        encoding="utf-8",
    )

    sources = compose_sources(tmp_path)
    assert "documentation.yaml" not in sources
    assert "commented.yaml" not in sources


def test_custom_yaml_tag_parsed_without_arbitrary_object_construction(
    tmp_path: Path,
) -> None:
    custom_tag = tmp_path / "nested/custom-tagged.yaml"
    custom_tag.parent.mkdir(parents=True, exist_ok=True)
    custom_tag.write_text(
        "services:\n  tagged-svc:\n    image: !CustomType 'alpine'\n",
        encoding="utf-8",
    )

    sources = compose_sources(tmp_path)
    assert "nested/custom-tagged.yaml" in sources


@pytest.mark.parametrize(
    "content",
    [
        "services:\n  api:\n    image: knora-api\n",
        "",
        "::malformed yaml content {[[",
    ],
)
def test_launcher_shell_docker_compose_f_reference_recognized(tmp_path: Path, content: str) -> None:
    """A target referenced via 'docker compose -f' in caller scripts is recognized
    even if unconventional/empty/malformed.
    """
    target = tmp_path / "deploy/custom.conf"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")

    launcher = tmp_path / "scripts/launch.sh"
    launcher.parent.mkdir(parents=True, exist_ok=True)
    launcher.write_text("docker compose -f deploy/custom.conf up -d\n", encoding="utf-8")

    sources = compose_sources(tmp_path)
    assert "deploy/custom.conf" in sources


@pytest.mark.parametrize("prefix", ["", "export ", "$env:"])
def test_compose_file_assignment_list_paths_recognized(tmp_path: Path, prefix: str) -> None:
    """Targets referenced via COMPOSE_FILE list are recognized even if content
    is not independently standard Compose.
    """
    file1 = tmp_path / "env/first.conf"
    file1.parent.mkdir(parents=True, exist_ok=True)
    file1.write_text("SOME_SETTING=1\n", encoding="utf-8")

    file2 = tmp_path / "env/second.conf"
    file2.parent.mkdir(parents=True, exist_ok=True)
    file2.write_text("", encoding="utf-8")

    env_file = tmp_path / ".env"
    env_file.write_text(f"{prefix}COMPOSE_FILE=env/first.conf:env/second.conf\n", encoding="utf-8")

    sources = compose_sources(tmp_path)
    assert "env/first.conf" in sources
    assert "env/second.conf" in sources


def test_include_and_extends_targets_with_empty_or_nonservices_content_reported(
    tmp_path: Path,
) -> None:
    """When a Compose file includes or extends a target with empty or
    non-services content, both are reported.
    """
    include_target = tmp_path / "config/included.yaml"
    include_target.parent.mkdir(parents=True, exist_ok=True)
    include_target.write_text("metadata:\n  title: no-services\n", encoding="utf-8")

    extends_target = tmp_path / "config/extended.yaml"
    extends_target.parent.mkdir(parents=True, exist_ok=True)
    extends_target.write_text("", encoding="utf-8")

    root_compose = tmp_path / "docker-compose.yml"
    root_compose.write_text(
        "include:\n"
        "  - path: config/included.yaml\n"
        "services:\n"
        "  app:\n"
        "    image: app:v1\n"
        "    extends:\n"
        "      file: config/extended.yaml\n"
        "      service: base\n",
        encoding="utf-8",
    )

    sources = compose_sources(tmp_path)
    assert "docker-compose.yml" in sources
    assert "config/included.yaml" in sources
    assert "config/extended.yaml" in sources


def test_ignored_directories_in_sandbox_excluded(tmp_path: Path) -> None:
    """Maintained scan excludes dependency, cache, .verification, evidence,
    and history directories.
    """
    ignored_paths = [
        "node_modules/pkg/compose.yml",
        ".venv/lib/docker-compose.yml",
        ".cache/tool/compose.yaml",
        ".verification/run-uuid/docker-compose.yml",
        "evidence/http-objects/compose.yml",
        "history/checkpoint/compose.yml",
    ]
    for rel in ignored_paths:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("services:\n  dummy:\n    image: busybox\n", encoding="utf-8")

    sources = compose_sources(tmp_path)
    for rel in ignored_paths:
        assert rel not in sources, f"Directory for {rel} must be excluded from inventory scan"


def test_git_ignored_third_yaml_excluded_and_untracked_included(tmp_path: Path) -> None:
    if shutil.which("git") is None:
        pytest.skip("git CLI unavailable")

    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
    (tmp_path / ".git/hooks/compose.yaml").write_text("services: {}\n", encoding="utf-8")
    subprocess.run(
        ["git", "config", "user.email", "ci@knora.local"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "CI"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )

    (tmp_path / ".gitignore").write_text("ignored/\n", encoding="utf-8")

    ignored_dir = tmp_path / "ignored"
    ignored_dir.mkdir()
    (ignored_dir / "compose.yaml").write_text(
        "services:\n  ignored:\n    image: alpine\n", encoding="utf-8"
    )

    untracked_dir = tmp_path / "untracked"
    untracked_dir.mkdir()
    (untracked_dir / "compose.yaml").write_text(
        "services:\n  active:\n    image: alpine\n", encoding="utf-8"
    )

    sources = compose_sources(tmp_path)
    assert "untracked/compose.yaml" in sources
    assert "ignored/compose.yaml" not in sources
    assert ".git/hooks/compose.yaml" not in sources


def test_services_mapping_is_detected_even_with_jobs_key(tmp_path: Path) -> None:
    (tmp_path / "mixed.yaml").write_text("jobs: {}\nservices: {}\n", encoding="utf-8")
    assert "mixed.yaml" in compose_sources(tmp_path)


def test_references_follow_nonstandard_extension_chain(tmp_path: Path) -> None:
    (tmp_path / "compose.yml").write_text("include: {path: first.conf}\n", encoding="utf-8")
    (tmp_path / "first.conf").write_text("include: [second.conf]\n", encoding="utf-8")
    (tmp_path / "second.conf").write_text("", encoding="utf-8")
    assert compose_sources(tmp_path) == {"compose.yml", "first.conf", "second.conf"}


def test_sandbox_does_not_traverse_external_directory_link(tmp_path: Path, monkeypatch) -> None:
    owned = tmp_path / "owned"
    outside = tmp_path / "outside"
    owned.mkdir()
    outside.mkdir()
    (outside / "compose.yml").write_text("services: {}\n", encoding="utf-8")
    link = owned / "linked"
    if os.name == "nt":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(outside)],
            check=True,
            capture_output=True,
        )
    else:
        link.symlink_to(outside, target_is_directory=True)
    walk = os.walk

    def checked_walk(*args, **kwargs):
        for entry in walk(*args, **kwargs):
            assert Path(entry[0]).resolve().is_relative_to(owned.resolve())
            yield entry

    monkeypatch.setattr(os, "walk", checked_walk)
    try:
        assert compose_sources(owned) == set()
    finally:
        if os.name == "nt":
            link.rmdir()
        else:
            link.unlink()


@pytest.mark.parametrize(
    "reference",
    [
        "docker compose -f .verification/third.conf up -d\n",
        "include: [.verification/third.conf]\n",
    ],
)
def test_explicit_reference_to_evidence_is_still_an_operational_source(
    tmp_path: Path, reference: str
) -> None:
    evidence = tmp_path / ".verification/third.conf"
    evidence.parent.mkdir()
    evidence.write_text("", encoding="utf-8")
    name = "launch.sh" if reference.startswith("docker") else "compose.yml"
    (tmp_path / name).write_text(reference, encoding="utf-8")
    assert ".verification/third.conf" in compose_sources(tmp_path)


@pytest.mark.parametrize(
    "invocation",
    [
        'docker --host npipe:////./pipe/dockerDesktopLinuxEngine compose -f "third source.conf" up',
        'docker compose --file="third source.conf" up',
        "docker-compose -f 'third source.conf' up",
    ],
)
def test_literal_compose_global_options_and_quoted_paths(tmp_path: Path, invocation: str) -> None:
    (tmp_path / "third source.conf").write_text("", encoding="utf-8")
    (tmp_path / "launch.sh").write_text(invocation, encoding="utf-8")
    assert "third source.conf" in compose_sources(tmp_path)


def test_yaml_merge_reveals_services_and_inherited_references(tmp_path: Path) -> None:
    (tmp_path / "renamed.yaml").write_text(
        "x-stack: &stack\n  services:\n    app:\n      <<: &base\n"
        "        extends: {file: base.conf, service: base}\n"
        "  include: [included.conf]\n<<: *stack\n",
        encoding="utf-8",
    )
    for name in ("base.conf", "included.conf"):
        (tmp_path / name).write_text("", encoding="utf-8")
    assert compose_sources(tmp_path) == {"renamed.yaml", "base.conf", "included.conf"}


def test_yaml_merge_alias_cycle_is_bounded(tmp_path: Path) -> None:
    (tmp_path / "recursive.yaml").write_text(
        "x-stack: &stack\n  <<: *stack\n  services: {}\n<<: *stack\n", encoding="utf-8"
    )
    assert compose_sources(tmp_path) == {"recursive.yaml"}
