"""One-hop entity navigation that promotes original supporting passages, never graph labels."""

from fedresearch.graph import resolve_entities


def expand_graph(query, ranked, graph, identity, lexical, config, paper_ids, allowed_chunks=None):
    """Resolve explicit query aliases, bound incident relations, and merge their source chunks under the cap."""

    matched = resolve_entities(query, graph, config.graph_entities)
    edges = [
        (source, target, key, data)
        for source, target, key, data in graph.edges(keys=True, data=True)
        if (source in matched or target in matched)
        and data["paper_id"] in paper_ids
        and (allowed_chunks is None or any(c in allowed_chunks for c in data["chunk_ids"]))
    ]
    edges.sort(key=lambda row: (-(int(row[0] in matched) + int(row[1] in matched)), row[2]))
    edges = edges[: config.graph_edges]
    supports = {}
    for _, _, identifier, data in edges:
        for chunk_id in data["chunk_ids"]:
            if allowed_chunks is None or chunk_id in allowed_chunks:
                supports.setdefault(chunk_id, []).append(identifier)
    matches = lexical.query(query, len(supports), paper_ids, list(supports)) if supports else []
    selection = "bm25" if matches else "relation_support_fallback"
    if not matches:
        matches = [(identifier, None) for identifier in sorted(supports)]
    original_ids = {identifier for identifier, _ in ranked}
    merged = list(ranked[:1])
    seen = {identifier for identifier, _ in merged}
    results = []
    for identifier, lexical_score in matches:
        if identifier in seen or len(results) == config.graph_limit:
            continue
        merged.append((identifier, ranked[0][1] if ranked else 0.0))
        seen.add(identifier)
        results.append(
            {
                "chunk_id": identifier,
                "relation_ids": supports[identifier],
                "action": "promoted" if identifier in original_ids else "added",
                "selection": selection,
                "lexical_score": lexical_score,
                "candidate_rank": len(merged),
            }
        )
    for identifier, score in ranked:
        if identifier not in seen and len(merged) < config.candidate_limit:
            merged.append((identifier, score))
            seen.add(identifier)
    return merged, {
        "enabled": True,
        "identity": identity,
        "hops": 1,
        "entity_limit": config.graph_entities,
        "edge_limit": config.graph_edges,
        "passage_limit": config.graph_limit,
        "matched_entities": matched,
        "ordering": "first_anchor_then_graph_then_remaining",
        "context_score": "inherited_first_anchor",
        "base_candidates": [
            {"chunk_id": identifier, "score": score} for identifier, score in ranked
        ],
        "relations": [{"relation_id": key, **data} for _, _, key, data in edges],
        "results": results,
        "dropped_base_ids": [identifier for identifier, _ in ranked if identifier not in seen],
    }
