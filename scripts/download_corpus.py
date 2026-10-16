"""Download the pinned PDFs without changing the corpus manifest or calling model APIs."""

import argparse
import json
import time
from pathlib import Path
from urllib.request import Request, urlopen

import pymupdf

from fedresearch.corpus.manifest import load_manifest, matching_papers
from fedresearch.util import file_sha256

ROOT = Path(__file__).resolve().parents[1]


def pdf_url(paper):
    """Helper to download: resolve a pinned arXiv version or published PDF URL."""
    if paper.document_version.startswith("arxiv:"):
        return f"https://arxiv.org/pdf/{paper.document_version.removeprefix('arxiv:')}"
    if paper.paper_id == "federated_medicine":
        return "https://www.nature.com/articles/s41598-020-69250-1.pdf"
    return paper.source_url


def download(paper, folder, check_only=False):
    """Verify an existing PDF or download and verify its exact bytes before saving it."""
    path = folder / f"{paper.paper_id}.pdf"
    if path.exists():
        if file_sha256(path) != paper.sha256:
            raise ValueError("Existing PDF checksum differs; inspect it before replacing it")
        return "reused"
    if check_only:
        raise FileNotFoundError(f"Place the pinned PDF at {path}")
    temporary = path.with_suffix(".pdf.part")
    try:
        request = Request(pdf_url(paper), headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=90) as response:
            temporary.write_bytes(response.read())
        if file_sha256(temporary) != paper.sha256:
            raise ValueError("Downloaded checksum differs from the pinned manifest")
        with pymupdf.open(temporary) as document:
            if document.needs_pass or not document.page_count:
                raise ValueError("Encrypted or empty PDF")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return "downloaded"


def main():
    """Acquire or check selected corpus PDFs and report failures without changing source identities."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--paper-id", action="append", help="Limit to a manifest paper ID; repeatable"
    )
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data/raw")
    parser.add_argument(
        "--check-only", action="store_true", help="Check local files without downloads"
    )
    args = parser.parse_args()
    papers = matching_papers(load_manifest(ROOT / "data/corpus_manifest.jsonl"), args.paper_id)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    result = {"papers": len(papers), "downloaded": 0, "reused": 0, "failures": []}
    for paper in papers:
        try:
            status = download(paper, args.output_dir, args.check_only)
            result[status] += 1
            print(f"{status.upper()} {paper.paper_id}", flush=True)
            if status == "downloaded":
                time.sleep(3.1)
        except Exception as error:
            result["failures"].append({"paper_id": paper.paper_id, "error": str(error)})
            print(f"FAILED {paper.paper_id}; manually download {pdf_url(paper)}", flush=True)
    print(json.dumps(result, indent=2))
    if result["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
