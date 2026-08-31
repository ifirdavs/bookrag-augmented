"""Lexical matching, safe query handling and deterministic rank-fusion checks."""

import sqlite3
from types import SimpleNamespace

import pytest

from fedresearch.indexing.lexical_index import LexicalIndex, build_lexical_index
from fedresearch.retrieval.fusion import reciprocal_rank_fusion


def test_bm25_matches_terms_filters_and_survives_reload(tmp_path):
    """Verify case-insensitive method matching, stable ties, safe punctuation and persisted filters."""
    chunks = [
        SimpleNamespace(chunk_id="c2", paper_id="p2", text="SCAFFOLD control variates"),
        SimpleNamespace(chunk_id="c1", paper_id="p1", text="SCAFFOLD control variates"),
        SimpleNamespace(chunk_id="c3", paper_id="p1", text="q-FFL fairness"),
    ]
    path = tmp_path / "bm25.sqlite"
    result = build_lexical_index(path, "index", "fingerprint", chunks)
    assert result["chunks"] == 3
    index = LexicalIndex(path, "index", "fingerprint", 3)
    try:
        rows = index.query("scaffold", 3, ["p1", "p2"])
        assert [identifier for identifier, _ in rows] == ["c1", "c2"]
        assert rows[0][1] == rows[1][1] > 0
        assert index.query("SCAFFOLD", 1, ["p2"])[0][0] == "c2"
        assert index.query("control", 3, ["p1", "p2"], ["c2"])[0][0] == "c2"
        assert index.query("q-FFL", 3, ["p1"])[0][0] == "c3"
        assert index.query('" : * ( )', 3, ["p1"]) == []
        assert index.query("unknownword", 3, ["p1"]) == []
        assert index.query("control", 3, []) == []
        assert index.query("control", 3, ["p1"], []) == []
        assert index.query('text:scaffold OR "q-FFL"', 3, ["p1"])
    finally:
        index.close()
    reloaded = LexicalIndex(path, "index", "fingerprint", 3)
    assert reloaded.query("scaffold", 3, ["p1", "p2"]) == rows
    reloaded.close()
    with pytest.raises(ValueError, match="incompatible"):
        LexicalIndex(path, "other-index", "fingerprint", 3)
    with pytest.raises(ValueError, match="incompatible"):
        LexicalIndex(path, "index", "fingerprint", 4)
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE metadata SET payload = '{}' ")
    with pytest.raises(ValueError, match="incompatible"):
        LexicalIndex(path, "index", "fingerprint", 3)


def test_rrf_uses_ranks_not_scores_and_handles_empty_lists():
    """Verify the RRF arithmetic, candidate cap, duplicate IDs and deterministic tie ordering."""
    dense = [("a", 0.9), ("b", 0.8)]
    lexical = [("b", 100.0), ("c", 80.0)]
    rows = reciprocal_rank_fusion([dense, lexical], 3)
    assert [identifier for identifier, _ in rows] == ["b", "a", "c"]
    assert rows[0][1] == pytest.approx(1 / 62 + 1 / 61)
    assert rows[1][1] == pytest.approx(1 / 61)
    assert reciprocal_rank_fusion([[], dense], 1) == [("a", 1 / 61)]
    assert reciprocal_rank_fusion([[], []], 5) == []
    assert reciprocal_rank_fusion([[("b", 9)], [("a", 1)]], 2)[0][0] == "a"
    assert reciprocal_rank_fusion([[("a", 9), ("a", 8)]], 2) == [("a", 1 / 61)]
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([], 0)
