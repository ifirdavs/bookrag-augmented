"""Graph provenance, persistence, alias/scope boundaries and controlled replay checks."""

import json
from unittest.mock import Mock

import pytest
from test_pipeline import TestEmbedder
from test_pipeline import baseline_run as baseline_run
from test_pipeline import corpus as corpus

from fedresearch.evaluation.runner import run_baseline
from fedresearch.graph import Curation, build_graph, compile_graph, load_graph, resolve_entities
from fedresearch.indexing.lexical_index import LexicalIndex
from fedresearch.indexing.pipeline import build_index, current_index
from fedresearch.retrieval.graph import expand_graph
from fedresearch.retrieval.service import RetrievalService
from fedresearch.storage.metadata_store import MetadataStore
from fedresearch.util import atomic_json, write_jsonl


def example_curation(store, paper="alpha"):
    """Helper to graph tests: label a short real fixture sentence with an explicit reviewed assertion."""
    block = next(
        store.block(row[0])
        for row in store.db.execute(
            "SELECT block_id FROM blocks WHERE paper_id=? ORDER BY block_id", (paper,)
        )
        if store.block(row[0]).text.startswith("This method")
    )
    end = block.text.index(".") + 1
    span = block.raw_span(0, end)
    return {
        "schema_version": 1,
        "review": "assistant_source_review",
        "entities": [
            {
                "entity_id": f"method:{paper}",
                "kind": "method",
                "label": paper.title(),
                "aliases": [f"{paper} method"],
            },
            {
                "entity_id": "technique:updates",
                "kind": "technique",
                "label": "Local updates",
                "aliases": ["local update"],
            },
        ],
        "relations": [
            {
                "subject": f"method:{paper}",
                "predicate": "uses",
                "object": "technique:updates",
                "paper_id": paper,
                "document_version": block.document_version,
                "span": span.model_dump(),
                "quote": block.raw_text[span.start : span.end],
            }
        ],
    }


@pytest.fixture
def graph_corpus(corpus):
    """Helper to graph integration tests: build the real section/FTS5 stores with local controlled vectors."""
    corpus.indexing.chunk_policy = "section"
    build_index(corpus, TestEmbedder())
    folder, _ = current_index(corpus)
    with MetadataStore(folder / "metadata.sqlite") as store:
        payload = example_curation(store)
    atomic_json(corpus.paths.manifest.parent / "graph_curated.json", payload)
    return corpus


@pytest.mark.parametrize(
    "damage",
    ["quote", "version", "paper", "entity", "type", "alias", "bounds", "review", "uncovered"],
)
def test_graph_rejects_unusable_assertions(graph_corpus, damage):
    """Reject stale/unknown sources, invented quotes, invalid entity types and ambiguous aliases before traversal."""
    folder, _ = current_index(graph_corpus)
    with MetadataStore(folder / "metadata.sqlite") as store:
        payload = example_curation(store)
        relation = payload["relations"][0]
        if damage == "quote":
            relation["quote"] = "A fabricated statement."
        elif damage == "version":
            relation["document_version"] = "stale:version"
        elif damage == "paper":
            relation["paper_id"] = "beta"
        elif damage == "entity":
            relation["subject"] = "method:missing"
        elif damage == "type":
            relation["predicate"] = "evaluated_on"
        elif damage == "alias":
            payload["entities"][1]["aliases"] = ["ALPHA-method"]
        elif damage == "bounds":
            relation["span"]["end"] = 999999
        elif damage == "review":
            payload["review"] = "unreviewed"
        elif damage == "uncovered":
            block = store.block(relation["span"]["block_id"])
            relation["span"] = block.raw_span(0, len(block.text)).model_dump()
            relation["quote"] = block.raw_text[relation["span"]["start"] : relation["span"]["end"]]
        with pytest.raises(ValueError):
            compile_graph(Curation.model_validate(payload), store)


def test_graph_persistence_parallel_sources_and_tamper_detection(graph_corpus):
    """Preserve parallel assertions and reject altered snapshots or changed curated source inputs."""
    folder, manifest = current_index(graph_corpus)
    path = graph_corpus.paths.manifest.parent / "graph_curated.json"
    payload = json.loads(path.read_text())
    with MetadataStore(folder / "metadata.sqlite") as store:
        block = store.block(payload["relations"][0]["span"]["block_id"])
        start = block.text.index("This method", 1)
        span = block.raw_span(start, block.text.index(".", start) + 1)
        payload["relations"].append(
            {
                **payload["relations"][0],
                "span": span.model_dump(),
                "quote": block.raw_text[span.start : span.end],
            }
        )
        atomic_json(path, payload)
        summary = build_graph(graph_corpus)
        graph, identity = load_graph(graph_corpus, folder, manifest, store)
        assert graph.is_directed() and graph.is_multigraph() and graph.number_of_edges() == 2
        assert summary["graph_id"] == identity["graph_id"]
        snapshot_path = folder / "graph.json"
        snapshot = json.loads(snapshot_path.read_text())
        snapshot["data"]["edges"][0]["quote"] = "altered"
        atomic_json(snapshot_path, snapshot)
        with pytest.raises(ValueError, match="Persisted graph"):
            load_graph(graph_corpus, folder, manifest, store)
        build_graph(graph_corpus)
        payload["entities"][0]["aliases"].append("new alias")
        atomic_json(path, payload)
        with pytest.raises(ValueError, match="inputs/index changed"):
            load_graph(graph_corpus, folder, manifest, store)


def test_graph_aliases_one_hop_caps_and_scope(graph_corpus):
    """Verify exact token aliases, incoming/outgoing one-hop edges, filtering before limits and bounded source promotion."""
    folder, manifest = current_index(graph_corpus)
    with MetadataStore(folder / "metadata.sqlite") as store:
        payload = example_curation(store)
        second = example_curation(store, "beta")
        payload["entities"].append(second["entities"][0])
        payload["relations"].extend(second["relations"])
        graph = compile_graph(Curation.model_validate(payload), store)
        lexical = LexicalIndex(
            folder / "bm25.sqlite",
            manifest["index_id"],
            manifest["chunk_fingerprint"],
            manifest["chunks"],
        )
        config = graph_corpus.retrieval.model_copy(
            update={"candidate_limit": 4, "graph_limit": 1, "graph_edges": 1}
        )
        beta_chunk = next(c.chunk_id for c in store.chunks() if c.paper_id == "beta")
        ranked = [(beta_chunk, 0.03)]
        try:
            merged, trace = expand_graph(
                "ALPHA-METHOD", ranked, graph, {}, lexical, config, ["alpha", "beta"]
            )
            assert trace["matched_entities"] == ["method:alpha"]
            assert len(trace["relations"]) == len(trace["results"]) == 1
            assert trace["relations"][0]["subject"] == "method:alpha"
            assert len(merged) <= 4 and len({identifier for identifier, _ in merged}) == len(merged)
            assert trace["results"][0]["selection"] == "bm25"
            _, fallback = expand_graph("alpha", ranked, graph, {}, lexical, config, ["alpha"])
            assert fallback["results"][0]["selection"] == "relation_support_fallback"
            assert store.chunk(trace["results"][0]["chunk_id"]).paper_id == "alpha"
            assert (
                expand_graph("alphabet", ranked, graph, {}, lexical, config, ["alpha"])[1][
                    "matched_entities"
                ]
                == []
            )
            for papers, scope in [([], None), (["beta"], None), (["alpha", "beta"], [beta_chunk])]:
                _, filtered = expand_graph(
                    "alpha method", ranked, graph, {}, lexical, config, papers, scope
                )
                assert not filtered["relations"] and not filtered["results"]
            _, incoming = expand_graph(
                "local updates", ranked, graph, {}, lexical, config, ["beta"]
            )
            assert incoming["relations"][0]["subject"] == "method:beta"
        finally:
            lexical.close()


def test_overlapping_dataset_names_remain_distinct(graph_corpus):
    """Keep extended MNIST/EMNIST distinct from MNIST while allowing both explicit query mentions."""
    folder, _ = current_index(graph_corpus)
    with MetadataStore(folder / "metadata.sqlite") as store:
        graph = compile_graph(Curation.model_validate(example_curation(store)), store)
    graph.add_node("dataset:emnist", label="EMNIST", aliases=["extended MNIST"])
    graph.add_node("dataset:mnist", label="MNIST", aliases=["MNIST"])
    assert resolve_entities("extended MNIST", graph, 4) == ["dataset:emnist"]
    assert resolve_entities("EMNIST versus MNIST", graph, 4) == ["dataset:emnist", "dataset:mnist"]
    assert resolve_entities("notMNIST", graph, 4) == []


def test_fresh_graph_service_respects_filters_and_empty_scope(graph_corpus):
    """Exercise fresh dense/BM25/hierarchy/graph retrieval, and keep paper/year/section filters hard."""
    build_graph(graph_corpus)
    graph_corpus.retrieval.mode = "graph"
    with RetrievalService(graph_corpus, TestEmbedder()) as service:
        evidence = service.retrieve("alpha method local updates")
        assert evidence and all(e.origin == "graph" for e in evidence)
        assert service.last_trace["graph_expansion"]["matched_entities"]
        assert service.last_trace["structural_expansion"]["enabled"]
        assert len(evidence) <= 5 and sum(e.token_count for e in evidence) <= 4000
        for filters in ({"paper_ids": ["beta"]}, {"year_from": 2020}, {"method": "control"}):
            evidence = service.retrieve("alpha method local updates", **filters)
            assert evidence and all(e.paper_id == "beta" for e in evidence)
            assert not service.last_trace["graph_expansion"]["relations"]
        calls = service.provider.calls
        assert service.retrieve("alpha method", paper_ids=[]) == []
        assert service.retrieve("alpha method", section_hint="missing section") == []
        assert service.provider.calls == calls


def test_graph_evaluation_replays_b2_then_reranks_exact_final_pool(
    corpus, baseline_run, monkeypatch
):
    """Exercise B2→B3 and B3→B3-R with real persistence and bounded searches, blocking all replayed work."""
    path, _, _ = baseline_run
    question = json.loads(path.read_text())
    question["question"] = "How does alpha method use local updates?"
    write_jsonl(path, [question])
    corpus.indexing.chunk_policy = "section"
    corpus.retrieval.mode = "structure"
    build_index(corpus, TestEmbedder())
    with RetrievalService(corpus, TestEmbedder()) as service:
        b2 = run_baseline(service, path, "dev", with_answers=True)
        payload = example_curation(service.store)
    atomic_json(corpus.paths.manifest.parent / "graph_curated.json", payload)
    build_graph(corpus)
    corpus.retrieval.mode = "graph"
    b2_path = corpus.paths.runs / b2["run_id"] / "run.json"
    monkeypatch.setattr(
        "fedresearch.retrieval.service.expand_hierarchy",
        Mock(side_effect=AssertionError("Hierarchy already replayed")),
    )
    with RetrievalService(corpus, TestEmbedder()) as service:
        service.provider.embed = Mock(side_effect=AssertionError("No embedding"))
        service.vectors.query = Mock(side_effect=AssertionError("No dense search"))
        b3 = run_baseline(service, path, "dev", with_answers=True, seed_source=b2_path)
        assert b3["failures"] == 0
        trace = b3["records"][0]["answer"]["trace"]["retrieval"]
        b2_trace = b2["records"][0]["answer"]["trace"]["retrieval"]
        assert trace["graph_expansion"]["base_candidates"] == b2_trace["candidates"]
        assert trace["structural_expansion"] == b2_trace["structural_expansion"]
        assert trace["embedding_usage"]["requests"] == 0
        assert trace["graph_expansion"]["matched_entities"]
        assert b3["records"][0]["graph_base_metrics"] == b2["records"][0]["candidate_metrics"]
        assert all(e["origin"] == "graph" for e in b3["records"][0]["answer"]["evidence"])
    corpus.reranking.enabled = True
    reranker = Mock()
    reranker.rerank.side_effect = lambda query, texts: (
        [(i, float(i)) for i in reversed(range(len(texts)))],
        {"enabled": True},
    )
    monkeypatch.setattr(LexicalIndex, "query", Mock(side_effect=AssertionError("No BM25")))
    monkeypatch.setattr(
        "fedresearch.retrieval.service.expand_graph",
        Mock(side_effect=AssertionError("No graph re-expansion")),
    )
    with RetrievalService(corpus, TestEmbedder(), reranker) as service:
        service.provider.embed = Mock(side_effect=AssertionError("No embedding"))
        service.vectors.query = Mock(side_effect=AssertionError("No dense search"))
        replay = run_baseline(
            service,
            path,
            "dev",
            with_answers=True,
            candidate_source=corpus.paths.runs / b3["run_id"] / "run.json",
        )
        assert replay["failures"] == 0
        after = replay["records"][0]["answer"]["trace"]["retrieval"]
        assert after["candidates"] == trace["candidates"]
        assert after["graph_expansion"] == trace["graph_expansion"]
        assert after["structural_expansion"] == trace["structural_expansion"]
        reranker.rerank.assert_called_once()
        assert reranker.rerank.call_args.args[1] == [
            service.store.chunk(row["chunk_id"]).text for row in trace["deduplicated_candidates"]
        ]
