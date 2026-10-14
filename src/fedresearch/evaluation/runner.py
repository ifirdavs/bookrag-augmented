"""Benchmark execution that saves evidence, answers, scores, timing and failures."""

import json
import time
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path
from uuid import uuid4

from fedresearch.evaluation.dataset import load_dataset, require_frozen, verify_question
from fedresearch.evaluation.retrieval_metrics import score_retrieval
from fedresearch.indexing.lexical_index import lexical_identity
from fedresearch.llm.answering import answer_question
from fedresearch.retrieval.evidence import deduplicate_candidates, pack_evidence
from fedresearch.retrieval.service import RetrievalService
from fedresearch.settings import Settings
from fedresearch.util import atomic_json, digest, file_sha256


def load_candidate_pools(
    service, path, split, questions, source_path, with_answers, *, as_seeds=False
):
    """Helper to paired evaluation: verify a matching unreranked run and load its exact candidate pools."""
    source = json.loads(source_path.read_text())
    settings = service.settings.model_dump(mode="json")
    settings["reranking"]["enabled"] = False
    if as_seeds:
        if (
            service.settings.retrieval.mode not in {"structure", "graph"}
            or service.settings.reranking.enabled
        ):
            raise ValueError("Seed source requires unreranked structure or graph retrieval")
        settings["retrieval"]["mode"] = (
            "structure" if service.settings.retrieval.mode == "graph" else "hybrid"
        )
    if (
        source["index_id"] != service.manifest["index_id"]
        or source["dataset_sha256"] != file_sha256(path)
        or source["split"] != split
        or Settings.model_validate(source["settings"]).model_dump(mode="json") != settings
        or source["failures"]
        or [r["question_id"] for r in source["records"]] != [q.question_id for q in questions]
    ):
        raise ValueError(
            "Candidate source must be a complete unreranked run with the same index, labels and settings"
        )
    prompt_hash = digest(files("fedresearch").joinpath("llm/prompts/answer.md").read_text())
    pools = {}
    for question, record in zip(questions, source["records"], strict=True):
        answer = record.get("answer")
        trace = answer["trace"]["retrieval"] if answer else record["trace"]
        if (
            record["status"] != "ok"
            or trace["index_id"] != source["index_id"]
            or trace["mode"] != settings["retrieval"]["mode"]
            or trace["reranking"]["enabled"]
            or any(value is not None for value in trace["filters"].values())
            or (answer and answer["question"] != question.question)
            or (with_answers and (not answer or answer["trace"]["prompt_sha256"] != prompt_hash))
        ):
            raise ValueError(
                "Candidate source must contain matching, unfiltered questions and prompt"
            )
        if service.settings.retrieval.mode in {"hybrid", "structure", "graph"} and (
            trace.get("lexical_index")
            != lexical_identity(service.manifest["index_id"], service.manifest["chunk_fingerprint"])
            or trace.get("fusion")
            != {
                "constant": service.settings.retrieval.rrf_constant,
                "candidate_limit": service.settings.retrieval.candidate_limit,
            }
            or set(trace.get("rankings", {})) != {"dense", "bm25"}
        ):
            raise ValueError("Candidate source must use the same lexical index and fusion settings")
        if trace["mode"] in {"structure", "graph"}:
            expansion = trace.get("structural_expansion", {})
            expected = {
                "enabled": True,
                "seed_limit": service.settings.retrieval.expansion_seeds,
                "per_seed": service.settings.retrieval.expansion_per_seed,
                "limit": service.settings.retrieval.expansion_limit,
            }
            if not isinstance(expansion.get("seed_candidates"), list) or any(
                expansion.get(key) != value for key, value in expected.items()
            ):
                raise ValueError("Candidate source must preserve compatible structural expansion")
        pools[question.question_id] = {
            "seed_pool" if as_seeds else "candidate_pool": [
                (r["chunk_id"], r["score"]) for r in trace["candidates"]
            ],
            "candidate_rankings": {
                name: [(r["chunk_id"], r["score"]) for r in rows]
                for name, rows in trace.get("rankings", {}).items()
            },
        }
        if trace["mode"] in {"structure", "graph"}:
            pools[question.question_id]["candidate_expansion"] = trace["structural_expansion"]
        if trace["mode"] == "graph":
            graph_expansion = trace.get("graph_expansion", {})
            if (
                not graph_expansion.get("enabled")
                or graph_expansion.get("identity") != service.graph_identity
                or graph_expansion.get("entity_limit") != service.settings.retrieval.graph_entities
                or graph_expansion.get("edge_limit") != service.settings.retrieval.graph_edges
                or graph_expansion.get("passage_limit") != service.settings.retrieval.graph_limit
                or not isinstance(graph_expansion.get("base_candidates"), list)
            ):
                raise ValueError("Candidate source must preserve compatible graph expansion")
            pools[question.question_id]["candidate_graph"] = graph_expansion
    return pools, {"run_id": source["run_id"], "sha256": file_sha256(source_path)}


def score_candidate_pool(question, rows: list[dict], service: RetrievalService) -> dict:
    """Helper to evaluation: score a bounded pre-packing pool with the original source-span metric."""
    ranked, _ = deduplicate_candidates([(r["chunk_id"], r["score"]) for r in rows], service.store)
    evidence, _ = pack_evidence(
        ranked,
        service.store,
        service.settings.retrieval.candidate_limit,
        sum(service.store.chunk(identifier).token_count for identifier, _ in ranked),
        service.settings.retrieval.mode,
    )
    return score_retrieval(
        question,
        evidence,
        service.settings.retrieval.candidate_limit,
        service.settings.evaluation.minimum_span_overlap,
    )


def run_baseline(
    service: RetrievalService,
    path: Path,
    split: str,
    with_answers: bool = False,
    candidate_source: Path | None = None,
    seed_source: Path | None = None,
) -> dict:
    """Evaluate verified questions, optionally replay candidates, and save evidence, answers and scores."""
    if candidate_source is not None and seed_source is not None:
        raise ValueError("Choose either candidate_source or seed_source")
    if split == "test":
        require_frozen(path)
    questions = load_dataset(path, split)
    for question in questions:
        if question.annotation_status == "draft":
            raise ValueError("Draft annotations cannot be used for reported evaluation")
        verify_question(question, service.store)
    pools, source = {}, None
    if candidate_source is not None or seed_source is not None:
        pools, source = load_candidate_pools(
            service,
            path,
            split,
            questions,
            candidate_source or seed_source,
            with_answers,
            as_seeds=seed_source is not None,
        )
    records = []
    for question in questions:
        started = time.perf_counter()
        try:
            replay = pools[question.question_id] if source else {}
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
            result["candidate_metrics"] = score_candidate_pool(
                question, service.last_trace["deduplicated_candidates"], service
            )
            expansion = service.last_trace["structural_expansion"]
            if expansion["enabled"]:
                result["seed_candidate_metrics"] = score_candidate_pool(
                    question, expansion["seed_candidates"], service
                )
            graph_expansion = service.last_trace["graph_expansion"]
            if graph_expansion["enabled"]:
                result["graph_base_metrics"] = score_candidate_pool(
                    question, graph_expansion["base_candidates"], service
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
        "candidate_source": source if candidate_source is not None else None,
        "seed_source": source if seed_source is not None else None,
        "timing_scope": (
            "graph expansion/packing and optional generation; excludes replayed embedding/search/hierarchy"
            if service.settings.retrieval.mode == "graph"
            else "hierarchy expansion/packing and optional generation; excludes replayed seed embedding/dense/BM25 searches"
        )
        if seed_source is not None
        else (
            "reranking/packing and optional generation; excludes replayed retrieval/expansion"
            if source
            else "query embedding/search, optional expansion, ranking/packing and optional generation"
        ),
        "settings": service.settings.model_dump(mode="json"),
        "retrieval_protocol": {
            "mode": service.settings.retrieval.mode,
            "chunk_policy": service.settings.indexing.chunk_policy,
            "embedding_model": service.settings.embedding.model,
            "candidate_limit_per_search": service.settings.retrieval.candidate_limit,
            "merged_candidate_limit": service.settings.retrieval.candidate_limit,
            "rrf_constant": service.settings.retrieval.rrf_constant
            if service.settings.retrieval.mode in {"hybrid", "structure", "graph"}
            else None,
            "reranking_model": service.settings.reranking.model
            if service.settings.reranking.enabled
            else None,
            "top_k": service.settings.retrieval.top_k,
            "evidence_tokens": service.settings.retrieval.evidence_tokens,
            "hierarchy_expansion": {
                "seeds": service.settings.retrieval.expansion_seeds,
                "per_seed": service.settings.retrieval.expansion_per_seed,
                "limit": service.settings.retrieval.expansion_limit,
            }
            if service.settings.retrieval.mode in {"structure", "graph"}
            else None,
            "graph_expansion": {
                "identity": service.graph_identity,
                "hops": 1,
                "entities": service.settings.retrieval.graph_entities,
                "edges": service.settings.retrieval.graph_edges,
                "passages": service.settings.retrieval.graph_limit,
            }
            if service.settings.retrieval.mode == "graph"
            else None,
            "candidate_metrics_scope": "after fusion/optional expansion/cap and source deduplication, before reranking/packing",
        },
        "records": records,
        "summary": summarize_retrieval(records),
        "failures": sum(r["status"] == "failed" for r in records),
        "note": "Span-overlap retrieval diagnostics; answer correctness, groundedness, claim support, and abstention require human scoring.",
    }
    atomic_json(service.settings.paths.runs / run_id / "run.json", result)
    return result


def summarize_retrieval(records: list[dict]) -> dict:
    """Helper to evaluation reports: macro-average successful answerable retrieval diagnostics."""
    scored = [r for r in records if r["status"] == "ok" and r["precision_at_k"] is not None]
    metrics = ("precision_at_k", "evidence_group_recall_at_k", "complete_coverage_at_k")
    return {
        "scored_answerable_questions": len(scored),
        **{key: sum(r[key] for r in scored) / len(scored) if scored else None for key in metrics},
        "candidate_group_recall": sum(
            r["candidate_metrics"]["evidence_group_recall_at_k"] for r in scored
        )
        / len(scored)
        if scored
        else None,
        "candidate_complete_coverage": sum(
            r["candidate_metrics"]["complete_coverage_at_k"] for r in scored
        )
        / len(scored)
        if scored
        else None,
    }
