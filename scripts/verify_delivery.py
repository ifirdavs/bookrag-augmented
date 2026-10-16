"""Verify the delivered run archive, frozen inputs, retrieval scores and assistant-audit counts locally."""

import hashlib
import json
import zipfile
from collections import Counter
from pathlib import Path
from statistics import mean

from fedresearch.evaluation.dataset import load_dataset, require_frozen
from fedresearch.evaluation.retrieval_metrics import score_retrieval
from fedresearch.schemas import Answer
from fedresearch.util import file_sha256

ROOT = Path(__file__).resolve().parents[1]


def verify():
    """Check original result bytes and recompute final span metrics and recorded audit arithmetic."""
    reports = ROOT / "reports"
    summary = json.loads((reports / "final_evaluation_summary.json").read_text())
    audit = json.loads((reports / "final_answer_audit.json").read_text())
    protocol_path = reports / "final_evaluation_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    assert file_sha256(protocol_path) == summary["protocol_sha256"] == audit["protocol_sha256"]
    assert file_sha256(reports / "final_answer_audit.json") == summary["answer_audit"]["sha256"]
    for filename, checksum in protocol["input_files_sha256"].items():
        assert file_sha256(ROOT / filename) == checksum, filename
    archive_path = reports / "final_runs.zip"
    assert file_sha256(archive_path) == (reports / "final_runs.sha256").read_text().split()[0]
    labels = ROOT / "data/benchmarks/test.jsonl"
    require_frozen(labels)
    assert file_sha256(labels) == protocol["test_set"]["label_sha256"]
    questions = load_dataset(labels, "test")
    counts = Counter()
    with zipfile.ZipFile(archive_path) as archive:
        expected = {f"{r['run_id']}/run.json" for r in summary["runs"].values()}
        assert set(archive.namelist()) == expected
        for arm, saved in summary["runs"].items():
            content = archive.read(f"{saved['run_id']}/run.json")
            assert hashlib.sha256(content).hexdigest() == saved["sha256"], arm
            run = json.loads(content)
            assert run["failures"] == 0 and run["split"] == "test"
            assert run["dataset_sha256"] == file_sha256(labels)
            rows = [r for r in audit["records"] if r["arm"] == arm]
            assert len(rows) == len(run["records"]) == len(questions) == 15
            positive_scores = []
            for question, record, review in zip(questions, run["records"], rows, strict=True):
                assert question.question_id == record["question_id"] == review["question_id"]
                assert record["status"] == "ok" and review["run_sha256"] == saved["sha256"]
                answer = Answer.model_validate(record["answer"])
                assert (
                    answer.question == question.question
                    and answer.answer_text == review["answer_text"]
                )
                assert answer.trace["prompt_sha256"] == protocol["shared"]["answer_prompt_sha256"]
                assert (
                    len(answer.evidence) <= 5
                    and sum(e.token_count for e in answer.evidence) <= 4000
                )
                evidence = {e.evidence_id: e for e in answer.evidence}
                assert set(answer.citations) == {i for c in answer.claims for i in c.citations}
                assert all(answer.citations[i] == evidence[i] for i in answer.citations)
                scores = score_retrieval(question, answer.evidence, 5, 0.5)
                assert all(record[key] == value for key, value in scores.items())
                if question.answerable:
                    positive_scores.append(scores)
                else:
                    assert answer.sufficiency == "insufficient" and not answer.claims
                    counts["correct_negative_abstentions"] += 1
                assert len(answer.claims) == len(review["claims"])
                for claim, checked in zip(answer.claims, review["claims"], strict=True):
                    assert claim.text == checked["text"]
                    assert claim.citations == [link["evidence_id"] for link in checked["citations"]]
                    counts["claims"] += 1
                    counts["citation_pairs"] += len(claim.citations)
                for identifier, source_id in review["provided_context"].items():
                    original = audit["sources"][source_id]
                    item = evidence[identifier]
                    assert item.chunk_id == original["chunk_id"]
                    assert [s.model_dump() for s in item.spans] == original["spans"]
                    assert hashlib.sha256(item.text.encode()).hexdigest() == original["text_sha256"]
                counts["answers"] += 1
            for key in ("precision_at_k", "evidence_group_recall_at_k", "complete_coverage_at_k"):
                assert (
                    abs(mean(row[key] for row in positive_scores) - saved["summary"][key]) < 1e-12
                )
            claims = [c for row in rows for c in row["claims"]]
            links = [link for claim in claims for link in claim["citations"]]
            aggregate = audit["aggregates"][arm]
            assert Counter(c["support"] for c in claims) == aggregate["claim_support_counts"]
            assert (
                Counter(link["support"] for link in links) == aggregate["citation_support_counts"]
            )
            assert aggregate["micro_groundedness"] == sum(
                c["support"] == "supported" for c in claims
            ) / len(claims)
            assert aggregate["micro_strict_citation_support"] == sum(
                link["support"] == "supported" for link in links
            ) / len(links)
            for field, target in [
                ("correctness_0_to_2", "mean_correctness_0_to_2"),
                ("relevance_0_to_2", "mean_relevance_0_to_2"),
            ]:
                assert (
                    abs(mean(row[field] for row in rows if row["answerable"]) - aggregate[target])
                    < 1e-12
                )
    assert counts == {
        "answers": 135,
        "claims": 279,
        "citation_pairs": 517,
        "correct_negative_abstentions": 18,
    }
    return {
        "status": "valid",
        "runs": len(summary["runs"]),
        **counts,
        "frozen_inputs": len(protocol["input_files_sha256"]),
        "hosted_calls": 0,
    }


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))
