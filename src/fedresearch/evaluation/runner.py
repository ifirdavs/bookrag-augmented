"""Benchmark execution that saves evidence, answers, scores, timing and failures."""

import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fedresearch.evaluation.dataset import load_dataset, require_frozen, verify_question
from fedresearch.evaluation.retrieval_metrics import score_retrieval
from fedresearch.llm.answering import answer_question
from fedresearch.retrieval.service import RetrievalService
from fedresearch.util import atomic_json, file_sha256


def run_baseline(
    service: RetrievalService, path: Path, split: str, with_answers: bool = False
) -> dict:
    """Evaluate source-verified questions and save retrieval scores, optional answers and errors."""
    if split == "test":
        require_frozen(path)
    questions = load_dataset(path, split)
    for question in questions:
        if question.annotation_status == "draft":
            raise ValueError("Draft annotations cannot be used for reported evaluation")
        verify_question(question, service.store)
    records = []
    for question in questions:
        started = time.perf_counter()
        try:
            if with_answers:
                answer = answer_question(service, question.question)
                evidence = answer.evidence
                result = {"answer": answer.model_dump(mode="json")}
            else:
                evidence = service.retrieve(question.question)
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
        "settings": service.settings.model_dump(mode="json"),
        "records": records,
        "failures": sum(r["status"] == "failed" for r in records),
        "note": "Span-overlap retrieval diagnostics; answer correctness, groundedness, claim support, and abstention require human scoring.",
    }
    atomic_json(service.settings.paths.runs / run_id / "run.json", result)
    return result
