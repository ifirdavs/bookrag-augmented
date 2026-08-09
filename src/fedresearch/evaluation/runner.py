"""Benchmark execution that saves evidence, answers, scores, timing and failures."""

import json
import time
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path
from uuid import uuid4

from fedresearch.evaluation.dataset import load_dataset, require_frozen, verify_question
from fedresearch.evaluation.retrieval_metrics import score_retrieval
from fedresearch.llm.answering import answer_question
from fedresearch.retrieval.service import RetrievalService
from fedresearch.util import atomic_json, digest, file_sha256


def load_candidate_pools(service, path, split, questions, source_path, with_answers):
    """Helper to paired evaluation: verify a compatible B0 run and load its exact candidate pools."""
    source = json.loads(source_path.read_text())
    settings = service.settings.model_dump(mode="json")
    settings["reranking"]["enabled"] = False
    if (
        source["index_id"] != service.manifest["index_id"]
        or source["dataset_sha256"] != file_sha256(path)
        or source["split"] != split
        or source["settings"] != settings
        or source["failures"]
        or [r["question_id"] for r in source["records"]] != [q.question_id for q in questions]
    ):
        raise ValueError(
            "Candidate source must be a complete B0 run with the same index, labels and settings"
        )
    prompt_hash = digest(files("fedresearch").joinpath("llm/prompts/answer.md").read_text())
    pools = {}
    for question, record in zip(questions, source["records"], strict=True):
        answer = record.get("answer")
        trace = answer["trace"]["retrieval"] if answer else record["trace"]
        if (
            record["status"] != "ok"
            or trace["index_id"] != source["index_id"]
            or trace["mode"] != "dense"
            or trace["reranking"]["enabled"]
            or any(value is not None for value in trace["filters"].values())
            or (answer and answer["question"] != question.question)
            or (with_answers and (not answer or answer["trace"]["prompt_sha256"] != prompt_hash))
        ):
            raise ValueError(
                "Candidate source must contain matching, unfiltered B0 questions and prompt"
            )
        pools[question.question_id] = [(r["chunk_id"], r["score"]) for r in trace["candidates"]]
    return pools, {"run_id": source["run_id"], "sha256": file_sha256(source_path)}


def run_baseline(
    service: RetrievalService,
    path: Path,
    split: str,
    with_answers: bool = False,
    candidate_source: Path | None = None,
) -> dict:
    """Evaluate verified questions, optionally replay B0 candidates, and save evidence, answers and scores."""
    if split == "test":
        require_frozen(path)
    questions = load_dataset(path, split)
    for question in questions:
        if question.annotation_status == "draft":
            raise ValueError("Draft annotations cannot be used for reported evaluation")
        verify_question(question, service.store)
    pools, source = {}, None
    if candidate_source is not None:
        pools, source = load_candidate_pools(
            service, path, split, questions, candidate_source, with_answers
        )
    records = []
    for question in questions:
        started = time.perf_counter()
        try:
            replay = {"candidate_pool": pools[question.question_id]} if source else {}
            if with_answers:
                answer = answer_question(service, question.question, **replay)
                evidence = answer.evidence
                result = {"answer": answer.model_dump(mode="json")}
            else:
                evidence = service.retrieve(question.question, **replay)
                result = {
                    "evidence": [e.model_dump(mode="json") for e in evidence],
                    "trace": service.last_trace,
                }
            result.update(
                score_retrieval(
                    question,
                    evidence,
                    service.settings.evaluation.k,
                    service.settings.evaluation.minimum_span_overlap,
                )
            )
            records.append(
                {
                    "question_id": question.question_id,
                    "status": "ok",
                    "seconds": time.perf_counter() - started,
                    **result,
                }
            )
        except Exception as error:
            records.append(
                {
                    "question_id": question.question_id,
                    "status": "failed",
                    "error_type": type(error).__name__,
                    "seconds": time.perf_counter() - started,
                }
            )
    timestamp = datetime.now(UTC).isoformat()
    run_id = uuid4().hex
    result = {
        "run_id": run_id,
        "created_at": timestamp,
        "split": split,
        "dataset_sha256": file_sha256(path),
        "index_id": service.manifest["index_id"],
        "candidate_source": source,
        "timing_scope": "reranking/packing and optional generation; excludes replayed query embedding/search"
        if source
        else "query embedding/search, ranking/packing and optional generation",
        "settings": service.settings.model_dump(mode="json"),
        "records": records,
        "failures": sum(r["status"] == "failed" for r in records),
        "note": "Span-overlap retrieval diagnostics; answer correctness, groundedness, claim support, and abstention require human scoring.",
    }
    atomic_json(service.settings.paths.runs / run_id / "run.json", result)
    return result
