"""Integrity checks for the standalone pinned-corpus downloader."""

import importlib.util
import io
from pathlib import Path

import pymupdf
import pytest

from fedresearch.schemas import Paper
from fedresearch.util import file_sha256


@pytest.fixture
def download_module():
    """Helper to delivery tests: load the standalone script without executing its CLI."""
    path = Path(__file__).resolve().parents[1] / "scripts/download_corpus.py"
    spec = importlib.util.spec_from_file_location("download_corpus", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def pinned_pdf(tmp_path):
    """Helper to delivery tests: create a real PDF with a fixed expected byte checksum."""
    path = tmp_path / "original.pdf"
    with pymupdf.open() as document:
        page = document.new_page()
        page.insert_text((60, 60), "A pinned paper")
        document.save(path)
    return path, Paper(
        paper_id="sample",
        title="A pinned paper",
        year=2020,
        source_url="https://example.org/sample.pdf",
        document_version="fixture:1",
        sha256=file_sha256(path),
        methods=[],
    )


def test_download_preserves_exact_bytes_and_reuses_file(
    download_module, pinned_pdf, tmp_path, monkeypatch
):
    """Download the pinned bytes once, then reuse them without another request."""
    path, paper = pinned_pdf
    monkeypatch.setattr(download_module, "urlopen", lambda *a, **k: io.BytesIO(path.read_bytes()))
    assert download_module.download(paper, tmp_path) == "downloaded"
    monkeypatch.setattr(
        download_module, "urlopen", lambda *a, **k: pytest.fail("Unexpected request")
    )
    assert download_module.download(paper, tmp_path) == "reused"
    assert file_sha256(tmp_path / "sample.pdf") == paper.sha256


def test_download_keeps_changed_existing_file(download_module, pinned_pdf, tmp_path):
    """Reject a changed local PDF without overwriting it."""
    _, paper = pinned_pdf
    path = tmp_path / "sample.pdf"
    path.write_bytes(b"changed")
    with pytest.raises(ValueError, match="Existing PDF checksum differs"):
        download_module.download(paper, tmp_path)
    assert path.read_bytes() == b"changed"


def test_download_rejects_changed_remote_bytes(download_module, pinned_pdf, tmp_path, monkeypatch):
    """Reject a different server response and remove the incomplete temporary file."""
    _, paper = pinned_pdf
    monkeypatch.setattr(download_module, "urlopen", lambda *a, **k: io.BytesIO(b"different PDF"))
    with pytest.raises(ValueError, match="Downloaded checksum differs"):
        download_module.download(paper, tmp_path)
    assert not (tmp_path / "sample.pdf").exists()
    assert not (tmp_path / "sample.pdf.part").exists()
