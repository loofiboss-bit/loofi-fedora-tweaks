#!/usr/bin/env python3
"""Generate and verify checksums, CycloneDX SBOM, and in-toto provenance."""

from __future__ import annotations

import argparse
import hashlib
import json
import uuid
from pathlib import Path
from typing import Any

CHECKSUMS_NAME = "SHA256SUMS.txt"
SBOM_NAME = "loofi-fedora-tweaks.cdx.json"
PROVENANCE_NAME = "loofi-fedora-tweaks.intoto.jsonl"
EVIDENCE_NAMES = frozenset({CHECKSUMS_NAME, SBOM_NAME, PROVENANCE_NAME})


def sha256(path: Path) -> str:
    """Return the SHA-256 digest for one regular file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_files(root: Path, *, include_evidence: bool = False) -> list[Path]:
    files = [path for path in root.iterdir() if path.is_file()]
    if not include_evidence:
        files = [path for path in files if path.name not in EVIDENCE_NAMES]
    return sorted(files, key=lambda path: path.name)


def _subjects(files: list[Path]) -> list[dict[str, Any]]:
    return [
        {"name": path.name, "digest": {"sha256": sha256(path)}}
        for path in files
    ]


def generate(
    root: Path,
    *,
    source_sha: str,
    tag: str,
    repository: str,
    workflow_run: str,
) -> dict[str, Path]:
    """Create release evidence for the artifacts already present in ``root``."""
    root = root.resolve()
    if not root.is_dir():
        raise ValueError(f"artifact directory does not exist: {root}")
    if not source_sha.strip() or not tag.startswith("v") or "/" not in repository:
        raise ValueError("source SHA, v-prefixed tag, and owner/repository are required")

    artifacts = _artifact_files(root)
    if not artifacts:
        raise ValueError("artifact directory contains no release artifacts")
    subjects = _subjects(artifacts)
    version = tag.removeprefix("v")
    identity = "\n".join(
        [repository, tag, source_sha, *[item["digest"]["sha256"] for item in subjects]]
    )

    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, identity)}",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "name": "loofi-fedora-tweaks",
                "version": version,
            }
        },
        "components": [
            {
                "type": "file",
                "name": item["name"],
                "hashes": [
                    {"alg": "SHA-256", "content": item["digest"]["sha256"]}
                ],
            }
            for item in subjects
        ],
    }
    sbom_path = root / SBOM_NAME
    sbom_path.write_text(json.dumps(sbom, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    provenance = {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": subjects,
        "predicateType": "https://slsa.dev/provenance/v1",
        "predicate": {
            "buildDefinition": {
                "buildType": "https://github.com/loofiboss-bit/loofi-fedora-tweaks/.github/workflows/auto-release.yml@v1",
                "externalParameters": {"tag": tag},
                "internalParameters": {},
                "resolvedDependencies": [
                    {
                        "uri": f"git+https://github.com/{repository}.git",
                        "digest": {"gitCommit": source_sha},
                    }
                ],
            },
            "runDetails": {
                "builder": {
                    "id": f"https://github.com/{repository}/.github/workflows/auto-release.yml@refs/tags/{tag}"
                },
                "metadata": {"invocationId": workflow_run},
            },
        },
    }
    provenance_path = root / PROVENANCE_NAME
    provenance_path.write_text(
        json.dumps(provenance, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    checksum_files = _artifact_files(root, include_evidence=True)
    checksum_path = root / CHECKSUMS_NAME
    checksum_path.write_text(
        "".join(
            f"{sha256(path)}  {path.name}\n"
            for path in checksum_files
            if path.name != CHECKSUMS_NAME
        ),
        encoding="utf-8",
    )
    return {
        "checksums": checksum_path,
        "sbom": sbom_path,
        "provenance": provenance_path,
    }


def verify(
    root: Path,
    *,
    expected_source_sha: str | None = None,
    expected_tag: str | None = None,
) -> list[str]:
    """Return evidence validation errors without modifying the directory."""
    root = root.resolve()
    errors: list[str] = []
    checksum_path = root / CHECKSUMS_NAME
    sbom_path = root / SBOM_NAME
    provenance_path = root / PROVENANCE_NAME
    for path in (checksum_path, sbom_path, provenance_path):
        if not path.is_file():
            errors.append(f"missing evidence file: {path.name}")
    if errors:
        return errors

    checksum_entries: dict[str, str] = {}
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        try:
            digest, name = line.split("  ", 1)
        except ValueError:
            errors.append(f"invalid checksum line: {line}")
            continue
        if Path(name).name != name or name == CHECKSUMS_NAME:
            errors.append(f"unsafe checksum path: {name}")
            continue
        checksum_entries[name] = digest
        path = root / name
        if not path.is_file():
            errors.append(f"checksum target missing: {name}")
        elif sha256(path) != digest:
            errors.append(f"checksum mismatch: {name}")

    expected_checksum_names = {
        path.name
        for path in _artifact_files(root, include_evidence=True)
        if path.name != CHECKSUMS_NAME
    }
    if set(checksum_entries) != expected_checksum_names:
        errors.append("checksum manifest does not cover the complete evidence directory")

    try:
        sbom = json.loads(sbom_path.read_text(encoding="utf-8"))
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"invalid evidence JSON: {exc}")
        return errors

    artifact_digests = {
        path.name: sha256(path) for path in _artifact_files(root)
    }
    sbom_digests = {
        item.get("name"): next(
            (
                value.get("content")
                for value in item.get("hashes", [])
                if value.get("alg") == "SHA-256"
            ),
            None,
        )
        for item in sbom.get("components", [])
    }
    provenance_digests = {
        item.get("name"): item.get("digest", {}).get("sha256")
        for item in provenance.get("subject", [])
    }
    if sbom.get("bomFormat") != "CycloneDX" or sbom_digests != artifact_digests:
        errors.append("SBOM subjects do not match release artifacts")
    if (
        provenance.get("_type") != "https://in-toto.io/Statement/v1"
        or provenance.get("predicateType") != "https://slsa.dev/provenance/v1"
        or provenance_digests != artifact_digests
    ):
        errors.append("provenance subjects do not match release artifacts")

    dependencies = provenance.get("predicate", {}).get("buildDefinition", {}).get(
        "resolvedDependencies", []
    )
    source_sha = (
        dependencies[0].get("digest", {}).get("gitCommit")
        if dependencies
        else None
    )
    tag = (
        provenance.get("predicate", {})
        .get("buildDefinition", {})
        .get("externalParameters", {})
        .get("tag")
    )
    if expected_source_sha and source_sha != expected_source_sha:
        errors.append("provenance source commit does not match expected commit")
    if expected_tag and tag != expected_tag:
        errors.append("provenance tag does not match expected tag")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact_dir", type=Path)
    parser.add_argument("--source-sha")
    parser.add_argument("--tag")
    parser.add_argument("--repository")
    parser.add_argument("--workflow-run", default="local")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    if args.verify:
        errors = verify(
            args.artifact_dir,
            expected_source_sha=args.source_sha,
            expected_tag=args.tag,
        )
        if errors:
            for error in errors:
                print(f"[release-evidence] ERROR: {error}")
            return 1
        print("[release-evidence] OK")
        return 0

    generate(
        args.artifact_dir,
        source_sha=args.source_sha or "",
        tag=args.tag or "",
        repository=args.repository or "",
        workflow_run=args.workflow_run,
    )
    print(f"[release-evidence] generated in {args.artifact_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
