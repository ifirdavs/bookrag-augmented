"""Bounded one-hop navigation from section chunks to nearby original source passages."""

from fedresearch.indexing.lexical_index import LexicalIndex
from fedresearch.settings import Retrieval
from fedresearch.storage.metadata_store import MetadataStore


def expand_hierarchy(
    query: str,
    ranked: list[tuple[str, float]],
    store: MetadataStore,
    lexical: LexicalIndex,
    config: Retrieval,
    allowed_chunks: list[str] | None = None,
) -> tuple[list[tuple[str, float]], dict]:
    """Interleave seeds with a few BM25-selected adjacent/parent/child chunks within the shared cap."""
    sections = {section.section_id: section for section in store.sections()}
    by_section, children = {}, {}
    for chunk in store.chunks():
        by_section.setdefault(chunk.section_id, []).append(chunk.chunk_id)
    for section in sections.values():
        if section.parent_id:
            children.setdefault(section.parent_id, []).append(section.section_id)
    anchors = {identifier for identifier, _ in ranked[: config.expansion_seeds]}
    permitted = set(allowed_chunks) if allowed_chunks is not None else None
    seed_ids = {identifier for identifier, _ in ranked}
    merged, seen, results = [], set(), []
    for identifier, score in ranked:
        if identifier in seen:
            continue
        merged.append((identifier, score))
        seen.add(identifier)
        if len(merged) == config.candidate_limit:
            break
        if identifier not in anchors or len(results) >= config.expansion_limit:
            continue
        seed = store.chunk(identifier)
        section = sections[seed.section_id]
        peers = by_section[seed.section_id]
        position = peers.index(identifier)
        neighbors = {}
        for offset in (-1, 1):
            if 0 <= position + offset < len(peers):
                neighbors[peers[position + offset]] = "adjacent_chunk"
        # Unclassified content has no reliable hierarchy: use same-section adjacency only.
        if section.kind == "section":
            if (
                section.parent_id
                and sections[section.parent_id].kind == "section"
                and by_section.get(section.parent_id)
            ):
                neighbors[by_section[section.parent_id][0]] = "parent_section"
            for child in children.get(section.section_id, [])[:2]:
                if sections[child].kind == "section" and by_section.get(child):
                    neighbors[by_section[child][0]] = "child_section"
        neighbors = {
            chunk_id: reason
            for chunk_id, reason in neighbors.items()
            if chunk_id not in seen | anchors and (permitted is None or chunk_id in permitted)
        }
        matches = lexical.query(query, len(neighbors), [seed.paper_id], list(neighbors))
        selection = "bm25"
        if not matches:
            selection = "adjacency_fallback"
            matches = [
                (chunk_id, None)
                for chunk_id, reason in neighbors.items()
                if reason == "adjacent_chunk"
            ]
        count = min(
            config.expansion_per_seed,
            config.expansion_limit - len(results),
            config.candidate_limit - len(merged),
        )
        for chunk_id, lexical_score in matches[:count]:
            # Context inherits its anchor's RRF score; BM25 only chooses among bounded neighbors.
            merged.append((chunk_id, score))
            seen.add(chunk_id)
            results.append(
                {
                    "chunk_id": chunk_id,
                    "from_seed": identifier,
                    "from_section": seed.section_id,
                    "section_id": store.chunk(chunk_id).section_id,
                    "reason": neighbors[chunk_id],
                    "selection": selection,
                    "lexical_score": lexical_score,
                    "action": "promoted" if chunk_id in seed_ids else "added",
                    "candidate_rank": len(merged),
                }
            )
        if len(merged) == config.candidate_limit:
            break
    return merged, {
        "enabled": True,
        "seed_limit": config.expansion_seeds,
        "per_seed": config.expansion_per_seed,
        "limit": config.expansion_limit,
        "ordering": "anchor_then_context",
        "context_score": "inherited_anchor_rrf",
        "seed_candidates": [
            {"chunk_id": identifier, "score": score} for identifier, score in ranked
        ],
        "results": results,
        "dropped_seed_ids": [identifier for identifier, _ in ranked if identifier not in seen],
    }
