"""Metadata and integrity checks for the PDFs already present in the local corpus."""

from pathlib import Path

from fedresearch.schemas import Paper
from fedresearch.settings import Settings
from fedresearch.util import file_sha256, read_jsonl


def load_manifest(path: Path) -> list[Paper]:
    """Read local corpus metadata and reject duplicate IDs, versions or file hashes."""
    papers = [Paper.model_validate(row) for row in read_jsonl(path)]
    if not papers:
        raise ValueError("Corpus manifest is empty")
    for name, values in [
        ("paper IDs", [p.paper_id for p in papers]),
        ("source versions", [p.document_version for p in papers]),
        ("PDF checksums", [p.sha256 for p in papers]),
    ]:
        if len(set(values)) != len(values):
            raise ValueError(f"Duplicate {name} in manifest")
    return papers


def pdf_path(settings: Settings, paper: Paper) -> Path:
    """Helper to preprocess: locate the existing PDF using its manifest paper ID."""
    return settings.paths.raw / f"{paper.paper_id}.pdf"


def validate_corpus(settings: Settings) -> dict:
    """Check that every manifest entry has a local PDF matching its pinned checksum."""
    papers = load_manifest(settings.paths.manifest)
    failures = []
    for paper in papers:
        path = pdf_path(settings, paper)
        if not path.exists():
            failures.append(f"{paper.paper_id}: missing PDF")
            continue
        if file_sha256(path) != paper.sha256:
            failures.append(f"{paper.paper_id}: mismatched checksum")
        if not path.read_bytes().startswith(b"%PDF-"):
            failures.append(f"{paper.paper_id}: not a PDF")
    return {
        "papers": len(papers),
        "failures": failures,
    }


def matching_papers(papers: list[Paper], ids: list[str] | None = None) -> list[Paper]:
    """Helper to corpus filters: select requested paper IDs and reject unknown IDs."""
    if ids is None:
        return papers
    unknown = set(ids) - {p.paper_id for p in papers}
    if unknown:
        raise ValueError(f"Unknown paper IDs: {sorted(unknown)}")
    return [p for p in papers if p.paper_id in ids]
