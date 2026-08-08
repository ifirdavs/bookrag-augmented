"""Small shared helpers for stable hashes and JSON persistence."""

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel


def digest(value: object) -> str:
    """Helper to artifact identities: hash a deterministic JSON representation of a value."""
    data = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path) -> str:
    """Helper to source/version checks: stream a file into a SHA-256 checksum."""
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def atomic_json(path: Path, value: object) -> None:
    """Helper to artifact writers: save JSON through a temporary file before replacing the target."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_jsonl(path: Path) -> list[dict]:
    """Helper to manifests and benchmarks: load nonblank JSON-lines records."""
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    """Helper to manifest writers: replace a JSON-lines file after all records have been written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
    temporary.replace(path)
