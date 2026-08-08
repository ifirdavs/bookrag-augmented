"""Span-overlap retrieval diagnostics with explicit denominators and evidence groups."""

from fedresearch.evaluation.dataset import BenchmarkQuestion
from fedresearch.schemas import Evidence, SourceSpan


def covered(span: SourceSpan, evidence: Evidence, minimum: float) -> bool:
    """Helper to score_retrieval: measure gold-span coverage without counting overlapping ranges twice."""
    ranges = sorted(
        (max(span.start, s.start), min(span.end, s.end))
        for s in evidence.spans
        if s.block_id == span.block_id and s.start < span.end and s.end > span.start
    )
    total, end = 0, span.start
    for a, b in ranges:
        total += max(0, b - max(a, end))
        end = max(end, b)
    return total / (span.end - span.start) >= minimum


def score_retrieval(
    question: BenchmarkQuestion, evidence: list[Evidence], k: int = 5, minimum_overlap: float = 0.5
) -> dict:
    """Compute span-based precision, evidence-group recall and complete coverage at k."""
    if not question.answerable:
        return {
            "precision_at_k": None,
            "evidence_group_recall_at_k": None,
            "complete_coverage_at_k": None,
            "covered_groups": [],
            "requires_abstention_review": True,
        }
    relevant = set()
    groups = []
    for group in question.evidence_groups:
        matches = [
            i
            for i, item in enumerate(evidence[:k])
            if any(covered(p.span, item, minimum_overlap) for p in group.alternatives)
        ]
        if matches:
            groups.append(group.group_id)
            relevant.update(matches)
    return {
        "precision_at_k": len(relevant) / k,
        "evidence_group_recall_at_k": len(groups) / len(question.evidence_groups),
        "complete_coverage_at_k": int(len(groups) == len(question.evidence_groups)),
        "covered_groups": groups,
        "relevance_rule": f"at least {minimum_overlap:.0%} gold character-span coverage; required-fact support still needs manual adjudication",
    }
