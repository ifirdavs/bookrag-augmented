"""Source-overlap deduplication and citation-ready evidence packing."""

from fedresearch.schemas import Evidence, SourceSpan
from fedresearch.storage.metadata_store import MetadataStore


def overlap_fraction(left: list[SourceSpan], right: list[SourceSpan]) -> float:
    """Helper to deduplicate_candidates: calculate shared source coverage relative to the smaller passage."""
    overlap = sum(
        max(0, min(a.end, b.end) - max(a.start, b.start))
        for a in left
        for b in right
        if a.block_id == b.block_id
    )
    denominator = min(sum(s.end - s.start for s in left), sum(s.end - s.start for s in right))
    return overlap / denominator if denominator else 0


def deduplicate_candidates(
    ranked: list[tuple[str, float]], store: MetadataStore
) -> tuple[list, list]:
    """Helper to retrieve: remove substantially overlapping passages before optional reranking."""
    unique, spans, skipped = [], [], []
    for chunk_id, score in ranked:
        chunk = store.chunk(chunk_id)
        if any(overlap_fraction(chunk.spans, previous) >= 0.5 for previous in spans):
            skipped.append({"chunk_id": chunk_id, "reason": "overlapping_source_spans"})
        else:
            unique.append((chunk_id, score))
            spans.append(chunk.spans)
    return unique, skipped


def pack_evidence(
    ranked: list[tuple[str, float]], store: MetadataStore, top_k: int, token_budget: int
) -> tuple[list[Evidence], dict]:
    """Pack deduplicated candidates into citation-ready evidence within the item and token budgets."""
    selected, skipped, tokens = [], [], 0
    for chunk_id, score in ranked:
        chunk = store.chunk(chunk_id)
        if tokens + chunk.token_count > token_budget:
            skipped.append({"chunk_id": chunk_id, "reason": "evidence_token_budget"})
            continue
        paper = store.paper(chunk.paper_id)
        blocks = [store.block(span.block_id) for span in chunk.spans]
        if any(
            block.paper_id != chunk.paper_id
            or block.document_version != chunk.document_version
            or span.end > len(block.raw_text)
            for span, block in zip(chunk.spans, blocks, strict=True)
        ):
            raise ValueError("Evidence does not resolve to the indexed source version")
        paths = [store.section(identifier).path for identifier in chunk.section_ids]
        selected.append(
            Evidence(
                evidence_id=f"E{len(selected) + 1}",
                chunk_id=chunk.chunk_id,
                paper_id=chunk.paper_id,
                title=paper.title,
                source_url=paper.source_url,
                document_version=chunk.document_version,
                parse_id=chunk.parse_id,
                section_path=chunk.section_path,
                section_paths=paths,
                pages=chunk.pages,
                spans=chunk.spans,
                text=chunk.text,
                token_count=chunk.token_count,
                score=score,
            )
        )
        tokens += chunk.token_count
        if len(selected) == top_k:
            break
    return selected, {
        "evidence_text_tokens": tokens,
        "evidence_token_budget": token_budget,
        "skipped": skipped,
    }
