"""CLI entry points for configuration checks, preprocessing, indexing, retrieval, answers and evaluation."""

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from uuid import uuid4

import typer

from fedresearch import __version__
from fedresearch.evaluation.dataset import load_dataset, verify_question
from fedresearch.evaluation.runner import run_baseline
from fedresearch.indexing.pipeline import build_index, canonical_store, preprocess
from fedresearch.llm.answering import answer_question, validate_citations
from fedresearch.llm.client import ClaudeGenerator, ProviderError, VoyageEmbedder
from fedresearch.retrieval.reranking import VoyageReranker
from fedresearch.retrieval.service import RetrievalService
from fedresearch.settings import load_settings
from fedresearch.util import atomic_json, file_sha256

app = typer.Typer(
    no_args_is_help=True,
    help="FedResearch: parse local PDFs, retrieve evidence, optionally rerank and answer with citations.",
)
benchmark_app = typer.Typer(no_args_is_help=True)
app.add_typer(benchmark_app, name="benchmark")
Config = Annotated[Path, typer.Option("--config", "-c")]
CONFIG = Path("configs/default.yaml")


def emit(value):
    """Helper to CLI commands: print readable JSON while converting paths to strings."""
    typer.echo(json.dumps(value, ensure_ascii=False, indent=2, default=str))


@app.command()
def doctor(config: Config = CONFIG, live: bool = False):
    """Check configuration; --live verifies Atlas embeddings/reranking and Claude generation."""
    settings = load_settings(config)
    result = {
        "version": __version__,
        "configuration": "valid",
        "generation_model": settings.generation.model,
        "embedding_model": settings.embedding.model,
        "embedding_dimensions": settings.embedding.dimensions,
        "tokenizer": settings.preprocessing.tokenizer,
        "tokenizer_revision": settings.preprocessing.tokenizer_revision,
        "generation_provider": "anthropic",
        "generation_credential_present": bool(os.getenv("ANTHROPIC_API_KEY")),
        "embedding_provider": "voyageai",
        "embedding_credential_present": bool(os.getenv("VOYAGE_API_KEY")),
        "generation_access": "not_tested",
        "embedding_access": "not_tested",
        "reranking_model": settings.reranking.model,
        "reranking_enabled": settings.reranking.enabled,
        "reranking_access": "not_tested",
    }
    if live:
        embedder = VoyageEmbedder(settings)
        vector = embedder.embed(["Federated learning aggregates client updates."])[0]
        reranker = VoyageReranker(settings)
        _, reranking_usage = reranker.rerank(
            "How does federated learning train models?",
            ["Clients train locally and aggregate updates.", "A recipe for vegetable soup."],
        )
        generator = ClaudeGenerator(settings)
        generated = generator.generate(
            "Return an insufficient answer with no claims and explain that no evidence was supplied.",
            "No evidence was supplied.",
        )
        validate_citations(generated, [])
        result.update(
            {
                "generation_access": "verified",
                "embedding_access": "verified",
                "embedding_dimensions": len(vector),
                "embedding_usage": embedder.usage,
                "generation_usage": generator.usage,
                "reranking_access": "verified",
                "reranking_usage": reranking_usage,
            }
        )
    emit(result)


@app.command("preprocess")
def preprocess_command(
    config: Config = CONFIG, paper_id: Annotated[list[str] | None, typer.Option()] = None
):
    """Parse existing local PDFs and report chunk counts and parsing warnings."""
    result = preprocess(load_settings(config), paper_id)
    fields = (
        "paper_id",
        "parse_id",
        "blocks",
        "sections",
        "chunks",
        "serious_warnings",
        "structure_warnings",
    )
    result["documents"] = [{key: doc[key] for key in fields} for doc in result["documents"]]
    emit(result)
    if result["failures"] or any(d["serious_warnings"] for d in result["documents"]):
        raise typer.Exit(1)


@app.command("index")
def index_command(config: Config = CONFIG):
    """Build or reuse the dense index from the processed corpus."""
    emit(build_index(load_settings(config)))


@app.command("retrieve")
def retrieve_command(
    question: str,
    config: Config = CONFIG,
    paper_id: Annotated[list[str] | None, typer.Option()] = None,
    section_hint: str | None = None,
    top_k: int | None = None,
):
    """Retrieve source passages with optional paper, section and result-count filters."""
    with RetrievalService(load_settings(config)) as service:
        evidence = service.retrieve(
            question, paper_ids=paper_id, section_hint=section_hint, top_k=top_k
        )
        emit(
            {
                "evidence": [e.model_dump(mode="json") for e in evidence],
                "trace": service.last_trace,
            }
        )


@app.command("ask")
def ask_command(
    question: str,
    config: Config = CONFIG,
    paper_id: Annotated[list[str] | None, typer.Option()] = None,
    mode: str = "dense",
    json_output: Annotated[bool, typer.Option("--json")] = False,
):
    """Answer from retrieved evidence, print citations and save the answer trace."""
    settings = load_settings(config)
    with RetrievalService(settings) as service:
        answer = answer_question(service, question, paper_ids=paper_id, mode=mode)
    run_id = uuid4().hex
    atomic_json(settings.paths.runs / run_id / "answer.json", answer)
    if json_output:
        emit({"run_id": run_id, **answer.model_dump(mode="json")})
    else:
        typer.echo(answer.answer_text)
        for identifier, evidence in answer.citations.items():
            paths = "; ".join(" / ".join(p) for p in evidence.section_paths)
            pages = ", ".join(map(str, evidence.pages))
            typer.echo(
                f"\n[{identifier}] {evidence.title}; {paths}; PDF page(s) {pages}; {evidence.source_url}"
            )
        typer.echo(f"\nSufficiency: {answer.sufficiency}. Saved run: {run_id}")


@benchmark_app.command("validate")
def benchmark_validate(config: Config = CONFIG):
    """Check dev and test annotations against canonical PDF source spans."""
    settings = load_settings(config)
    with canonical_store(settings) as store:
        counts = {}
        for split in ("dev", "test"):
            questions = load_dataset(
                settings.paths.manifest.parent / "benchmarks" / f"{split}.jsonl", split
            )
            for question in questions:
                verify_question(question, store)
            counts[split] = len(questions)
        emit({"questions": counts, "source_spans": "valid"})


@benchmark_app.command("freeze")
def benchmark_freeze(config: Config = CONFIG):
    """Freeze source-verified held-out labels and record whether human review occurred."""
    settings = load_settings(config)
    path = settings.paths.manifest.parent / "benchmarks" / "test.jsonl"
    questions = load_dataset(path, "test")
    if any(q.annotation_status == "draft" for q in questions):
        raise ValueError("Verify draft source annotations before freezing")
    with canonical_store(settings) as store:
        for question in questions:
            verify_question(question, store)
    atomic_json(
        path.parent / "frozen.json",
        {
            path.name: file_sha256(path),
            "frozen_at": datetime.now(UTC).isoformat(),
            "annotation_statuses": sorted({q.annotation_status for q in questions}),
            "human_review_complete": all(
                q.annotation_status == "human_reviewed" for q in questions
            ),
        },
    )
    emit({"held_out_labels": "frozen", "questions": len(questions)})


@app.command("evaluate")
def evaluate_command(
    config: Config = CONFIG,
    split: str = "dev",
    with_answers: bool = False,
    candidate_source: Annotated[
        Path | None, typer.Option(help="Replay a saved B0 run.json for a paired comparison.")
    ] = None,
):
    """Score benchmark retrieval and optional answers; optionally replay a saved dense candidate pool."""
    if split not in {"dev", "test"}:
        raise ValueError("split must be dev or test")
    settings = load_settings(config)
    with RetrievalService(settings) as service:
        result = run_baseline(
            service,
            settings.paths.manifest.parent / "benchmarks" / f"{split}.jsonl",
            split,
            with_answers,
            candidate_source,
        )
    emit(
        {
            "run_id": result["run_id"],
            "questions": len(result["records"]),
            "failures": result["failures"],
            "records": [{k: r[k] for k in ("question_id", "status")} for r in result["records"]],
        }
    )
    if result["failures"]:
        raise typer.Exit(1)


def main():
    """Run the CLI and report configuration, provider or file errors without a traceback."""
    try:
        app()
    except (ValueError, ProviderError, OSError) as error:
        typer.echo(f"Error: {error}", err=True)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
