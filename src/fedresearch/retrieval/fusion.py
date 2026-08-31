"""Rank-based fusion without comparing cosine similarity with BM25 scores."""


def reciprocal_rank_fusion(
    rankings: list[list[tuple[str, float]]], limit: int, constant: int = 60
) -> list[tuple[str, float]]:
    """Merge ranked lists using sum(1 / (constant + rank)); break tied scores by chunk ID."""
    if limit < 1 or constant < 1:
        raise ValueError("RRF limit and constant must be positive")
    scores = {}
    for ranking in rankings:
        seen = set()
        for rank, (identifier, _) in enumerate(ranking, start=1):
            if identifier not in seen:
                scores[identifier] = scores.get(identifier, 0.0) + 1 / (constant + rank)
                seen.add(identifier)
    return sorted(scores.items(), key=lambda row: (-row[1], row[0]))[:limit]
