"""Tests for pipeline behavior and regression boundaries."""

import json
import re
import subprocess
import sys
from unittest.mock import Mock

import pymupdf
import pytest
from typer.testing import CliRunner

from fedresearch.cli import app
from fedresearch.corpus.manifest import load_manifest
from fedresearch.evaluation.dataset import (
    BenchmarkQuestion,
    EvidenceGroup,
    GoldPassage,
    require_frozen,
    verify_question,
)
from fedresearch.evaluation.retrieval_metrics import score_retrieval
from fedresearch.evaluation.runner import run_baseline
from fedresearch.indexing.embeddings import EmbeddingCache
from fedresearch.indexing.lexical_index import LexicalIndex
from fedresearch.indexing.pipeline import build_index, index_documents, preprocess
from fedresearch.llm.answering import answer_question, validate_citations
from fedresearch.llm.client import ProviderError, validate_vectors
from fedresearch.preprocessing.cleaning import clean_text
from fedresearch.preprocessing.pdf_parser import (
    caption_table_regions,
    extract_items,
    ordered_blocks,
    parse_pdf,
)
from fedresearch.preprocessing.sections import heading
from fedresearch.retrieval.fusion import reciprocal_rank_fusion
from fedresearch.retrieval.service import RetrievalService
from fedresearch.schemas import Block, Claim, GeneratedAnswer, Paper
from fedresearch.settings import Preprocessing, Settings
from fedresearch.tokenization import load_tokenizer
from fedresearch.util import atomic_json, file_sha256, write_jsonl


class TestEmbedder:
    """A controlled test double, never a production retrieval option or benchmark model."""

    __test__ = False
    identity = {"provider": "test-only", "model": "controlled-vectors", "dimensions": 4}

    def __init__(self):
        """Helper to pipeline tests: initialize controlled vector usage tracking."""
        self.calls = 0
        self.input_types = []
        self.usage = {"input_tokens": 0, "requests": 0}

    def embed(self, texts, *, input_type="document"):
        """Helper to pipeline tests: return controlled word-count vectors and record input roles."""
        self.calls += 1
        self.input_types.append(input_type)
        self.usage["requests"] += 1
        self.usage["input_tokens"] += sum(len(t.split()) for t in texts)
        return [
            [
                1 + len(re.findall(word, text.casefold()))
                for word in ("proximal", "control", "averaging", "privacy")
            ]
            for text in texts
        ]


@pytest.fixture
def corpus(tmp_path):
    """Helper to pipeline tests: create two local PDF fixtures and their canonical parses."""
    settings = Settings()
    for name, value in {
        "manifest": "data/manifest.jsonl",
        "raw": "data/raw",
        "processed": "data/processed",
        "indexes": "artifacts/indexes",
        "runs": "artifacts/runs",
    }.items():
        setattr(settings.paths, name, tmp_path / value)
    settings.paths.raw.mkdir(parents=True)
    settings.preprocessing.chunk_tokens = 100
    settings.preprocessing.overlap_tokens = 20
    settings.embedding.dimensions = 4
    papers = []
    for identifier, word, year in [("alpha", "proximal", 2019), ("beta", "control", 2020)]:
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((60, 65), "1 Introduction", fontsize=15, fontname="hebo")
        text = f"This method uses {word} updates to address client heterogeneity. " * 18
        result = page.insert_textbox((60, 100, 520, 680), text, fontsize=11)
        assert result > 0
        path = settings.paths.raw / f"{identifier}.pdf"
        doc.save(path)
        doc.close()
        papers.append(
            Paper(
                paper_id=identifier,
                title=identifier,
                year=year,
                source_url=f"https://example.org/{identifier}",
                document_version=f"fixture:{identifier}:1",
                sha256=file_sha256(path),
                methods=[word],
            )
        )
    write_jsonl(settings.paths.manifest, [p.model_dump(mode="json") for p in papers])
    result = preprocess(settings)
    assert result["processed"] == 2 and not result["failures"]
    return settings


def test_cleaning_maps_to_original_text():
    """Verify cleaning maps to original text."""
    raw = "  hetero-\ngeneity  with\n β updates  "
    text, runs = clean_text(raw)
    assert text == "heterogeneity with β updates"
    block = Block(
        block_id="b",
        paper_id="p",
        document_version="v",
        page=1,
        bbox=(0, 0, 1, 1),
        order=0,
        raw_text=raw,
        text=text,
        text_map=runs,
        font_size=10,
    )
    span = block.raw_span(0, len("heterogeneity"))
    assert raw[span.start : span.end] == "hetero-\ngeneity"
    beta = block.raw_span(text.index("β"), text.index("β") + 1)
    assert raw[beta.start : beta.end] == "β"


def test_two_columns_do_not_interleave():
    """Verify two columns do not interleave."""
    blocks = [
        {"bbox": (x, y, x + 180, y + 20), "name": f"{side}{y}"}
        for y in (100, 200, 300)
        for side, x in [("L", 60), ("R", 320)]
    ]
    ordered, detected = ordered_blocks(blocks, 600)
    assert detected
    assert [b["name"] for b in ordered] == ["L100", "L200", "L300", "R100", "R200", "R300"]


def test_author_initial_is_not_a_heading():
    """Verify author initial is not a heading."""
    assert heading("H. Brendan McMahan", 12, True, 10, 1) is None
    assert heading("A. Additional Results", 12, True, 10, 8)
    assert heading("2 FEDERATED LEARNING AND FEDAVG", 9.6, False, 10, 2)
    assert heading("C.3 EXPERIMENTAL DETAILS", 8, False, 10, 12)
    assert heading("1 Server executes:", 10, True, 10, 4) is None


def test_roman_small_caps_headings_are_recognized():
    """Verify IEEE Roman-numbered headings, including page-one Introduction, without treating initials as headings."""
    assert heading("I. INTRODUCTION", 8, False, 10, 1)
    assert heading("II. PRELIMINARIES", 8, False, 10, 2)
    assert heading("IV. EXPERIMENTS", 8, False, 10, 5)
    assert heading("V. K-CLIENT RANDOM SCHEDULING POLICY", 8, False, 10, 8)
    assert heading("I. Goodfellow", 11, False, 10, 1) is None
    assert heading("U I).", 10, False, 10, 16) is None
    assert heading("P T Θ +", 8, False, 10, 7) is None


def test_named_headings_merged_with_prose_preserve_reference_boundary(tmp_path):
    """Verify merged journal headings become sections and bibliography text stays out of chunks."""
    path = tmp_path / "journal.pdf"
    with pymupdf.open() as document:
        page = document.new_page()
        for y, text, size, font in [
            (60, "Methods", 11, "hebo"),
            (72, "Clients train locally and share updates with a server.", 9, "helv"),
            (160, "References", 11, "hebo"),
            (172, "1. Bibliography-only material should not be embedded.", 9, "helv"),
        ]:
            page.insert_text((60, y), text, fontsize=size, fontname=font)
        document.save(path)
    paper = Paper(
        paper_id="journal",
        title="Example journal",
        year=2020,
        source_url="https://example.org/journal",
        document_version="fixture:journal:1",
        sha256=file_sha256(path),
    )
    document = parse_pdf(path, paper, Preprocessing())
    assert any(section.title == "Methods" for section in document.sections)
    assert any(section.kind == "references" for section in document.sections)
    assert "Clients train locally" in " ".join(chunk.text for chunk in document.chunks)
    assert "Bibliography-only" not in " ".join(chunk.text for chunk in document.chunks)


def test_heading_number_and_title_on_same_line_stay_together():
    """Verify separate PDF text runs for a section number and title remain one heading block."""
    with pymupdf.open() as document:
        page = document.new_page()
        page.insert_text((60, 100), "3", fontsize=12, fontname="hebo")
        page.insert_text((85, 100), "Experimental Results", fontsize=12, fontname="hebo")
        items = extract_items(page)
    assert any(clean_text(item["raw_text"])[0] == "3 Experimental Results" for item in items)


def test_invalid_settings_and_vectors():
    """Verify invalid settings and vectors."""
    with pytest.raises(ValueError, match="overlap"):
        Preprocessing(chunk_tokens=100, overlap_tokens=100)
    for vector in ([float("nan"), 1], [0, 0], [1]):
        with pytest.raises(ProviderError):
            validate_vectors([vector], 1, 2)


def test_duplicate_corpus_id_rejected(corpus):
    """Verify duplicate corpus id rejected."""
    rows = [json.loads(line) for line in corpus.paths.manifest.read_text().splitlines()]
    write_jsonl(corpus.paths.manifest, [rows[0], rows[0]])
    with pytest.raises(ValueError, match="Duplicate"):
        load_manifest(corpus.paths.manifest)


def test_query_budget_uses_voyage_tokens(corpus):
    """Verify an over-budget Unicode query is rejected before any query embedding request."""
    build_index(corpus, TestEmbedder())
    config = corpus.preprocessing
    tokenizer = load_tokenizer(config.tokenizer, config.tokenizer_revision)
    query = "∇𝛼 中文 personalized learning " * 20
    count = len(tokenizer.encode(query, add_special_tokens=False))
    corpus.retrieval.max_query_tokens = count - 1
    provider = TestEmbedder()
    with RetrievalService(corpus, provider) as service:
        with pytest.raises(ValueError, match="token budget"):
            service.retrieve(query)
        assert provider.calls == 0
        corpus.retrieval.max_query_tokens = count
        assert service.retrieve(query)
        assert provider.calls == 1


def test_index_reload_filters_budgets_and_empty_scope(corpus):
    """Verify index reload filters budgets and empty scope."""
    provider = TestEmbedder()
    result = build_index(corpus, provider)
    assert result["papers"] == 2 and result["chunks"] > 2
    assert set(provider.input_types) == {"document"}
    reused = build_index(corpus, provider)
    assert reused["reused"] and reused["index_id"] == result["index_id"]
    with RetrievalService(corpus, TestEmbedder()) as service:
        evidence = service.retrieve("proximal updates", paper_ids=["alpha"])
        assert service.provider.input_types == ["query"]
        assert evidence and all(e.paper_id == "alpha" for e in evidence)
        assert sum(e.token_count for e in evidence) <= corpus.retrieval.evidence_tokens
        assert service.retrieve("updates", year_from=2020, method="control")[0].paper_id == "beta"
        calls = service.provider.calls
        assert service.retrieve("updates", paper_ids=[]) == []
        assert service.retrieve("updates", section_hint="nonexistent") == []
        assert service.provider.calls == calls
        with pytest.raises(ValueError, match="Unknown paper"):
            service.retrieve("updates", paper_ids=["missing"])
        with pytest.raises(ValueError, match="Supported retrieval modes"):
            service.retrieve("updates", mode="unknown")
        with pytest.raises(ValueError, match="top_k"):
            service.retrieve("updates", top_k=0)
        with pytest.raises(ValueError, match="empty"):
            service.retrieve(" ")


def test_changed_model_and_parser_refuse_stale_index(corpus):
    """Verify changed model and parser refuse stale index."""
    build_index(corpus, TestEmbedder())
    changed = TestEmbedder()
    changed.identity = {**changed.identity, "model": "different"}
    with pytest.raises(ValueError, match="Embedding configuration"):
        RetrievalService(corpus, changed)
    corpus.preprocessing.overlap_tokens = 15
    with pytest.raises(ValueError, match="Corpus or parser"):
        RetrievalService(corpus, TestEmbedder())
    with pytest.raises(ValueError, match="stale parser"):
        build_index(corpus, TestEmbedder())


def test_hybrid_config_filters_fusion_and_dense_index_reuse(corpus):
    """Verify hybrid uses existing vectors, shared filters, capped fusion and original source evidence."""
    result = build_index(corpus, TestEmbedder())
    sidecar = corpus.paths.indexes / result["index_id"] / "bm25.sqlite"
    sidecar.unlink()
    provider = TestEmbedder()
    reused = build_index(corpus, provider)
    assert reused["reused"] and reused["index_id"] == result["index_id"]
    assert provider.calls == 0 and sidecar.exists()
    corpus.retrieval.mode = "hybrid"
    corpus.retrieval.candidate_limit = 6
    with RetrievalService(corpus, TestEmbedder()) as service:
        evidence = service.retrieve("control updates", year_from=2020, method="control")
        trace = service.last_trace
        assert trace["mode"] == "hybrid" and trace["ranking_score"] == "rrf"
        assert set(trace["rankings"]) == {"dense", "bm25"}
        expected = reciprocal_rank_fusion(
            [
                [(row["chunk_id"], row["score"]) for row in rows]
                for rows in trace["rankings"].values()
            ],
            6,
        )
        assert trace["candidates"] == [{"chunk_id": i, "score": s} for i, s in expected]
        assert evidence and all(e.paper_id == "beta" and e.origin == "hybrid" for e in evidence)
        assert all(service.store.block(s.block_id) for e in evidence for s in e.spans)
        assert len(evidence) <= corpus.retrieval.top_k
        assert sum(e.token_count for e in evidence) <= corpus.retrieval.evidence_tokens
        assert service.retrieve("proximal", paper_ids=["alpha"], section_hint="Introduction")
        calls = service.provider.calls
        assert service.retrieve("control", paper_ids=[]) == []
        assert service.retrieve("control", section_hint="nonexistent") == []
        assert service.provider.calls == calls
    sidecar.unlink()
    with RetrievalService(corpus, TestEmbedder()) as service:
        with pytest.raises(ValueError, match="BM25 index is missing"):
            service.retrieve("control")
        assert service.provider.calls == 0


def test_hybrid_empty_channel_still_returns_the_other_channel(corpus, monkeypatch):
    """Verify an empty dense or lexical result list can still produce source-backed hybrid evidence."""
    build_index(corpus, TestEmbedder())
    corpus.retrieval.mode = "hybrid"
    with RetrievalService(corpus, TestEmbedder()) as service:
        monkeypatch.setattr(service.vectors, "query", lambda *args: [])
        assert service.retrieve("proximal")
        assert service.last_trace["rankings"]["dense"] == []
        assert service.last_trace["rankings"]["bm25"]
    monkeypatch.setattr(LexicalIndex, "query", lambda *args: [])
    with RetrievalService(corpus, TestEmbedder()) as service:
        assert service.retrieve("proximal")
        assert service.last_trace["rankings"]["bm25"] == []
        assert service.last_trace["rankings"]["dense"]


def test_section_and_fixed_indexes_preserve_independent_pointers_and_source_ids(corpus):
    """Verify a section index preserves the fixed index, canonical files and original block identities."""
    fixed = build_index(corpus, TestEmbedder())
    pointer = (corpus.paths.indexes / "CURRENT.json").read_bytes()
    originals = {p: file_sha256(p) for p in corpus.paths.processed.rglob("*.json")}
    documents = index_documents(corpus)
    original_blocks = {b.block_id: b.raw_text for d in documents for b in d.blocks}
    corpus.indexing.chunk_policy = "section"
    section = build_index(corpus, TestEmbedder())
    assert section["index_id"] != fixed["index_id"]
    assert (corpus.paths.indexes / "CURRENT.json").read_bytes() == pointer
    assert (
        json.loads((corpus.paths.indexes / "CURRENT_section.json").read_text())["index_id"]
        == section["index_id"]
    )
    assert originals == {p: file_sha256(p) for p in corpus.paths.processed.rglob("*.json")}
    corpus.retrieval.mode = "hybrid"
    with RetrievalService(corpus, TestEmbedder()) as service:
        assert service.manifest["index_id"] == section["index_id"]
        assert all(
            c.policy == "section" and len(c.section_ids) == 1 for c in service.store.chunks()
        )
        assert all(
            service.store.block(identifier).raw_text == text
            for identifier, text in original_blocks.items()
        )
    corpus.indexing.chunk_policy = "fixed"
    provider = TestEmbedder()
    assert build_index(corpus, provider)["index_id"] == fixed["index_id"]
    assert provider.calls == 0
    with RetrievalService(corpus, provider) as service:
        assert service.retrieve("proximal updates")
        with pytest.raises(ValueError, match="section chunks"):
            service.retrieve("proximal", mode="structure")


def test_structure_service_enforces_filters_budgets_and_empty_scopes(corpus):
    """Verify expansion obeys section/paper/year/method scope and final provenance/token limits."""
    corpus.indexing.chunk_policy = "section"
    corpus.retrieval.mode = "structure"
    build_index(corpus, TestEmbedder())
    with RetrievalService(corpus, TestEmbedder()) as service:
        evidence = service.retrieve(
            "control updates", year_from=2020, method="control", section_hint="Introduction"
        )
        assert evidence and all(e.paper_id == "beta" and e.origin == "structure" for e in evidence)
        assert all("Introduction" in " / ".join(e.section_path) for e in evidence)
        assert len(evidence) <= corpus.retrieval.top_k
        assert sum(e.token_count for e in evidence) <= corpus.retrieval.evidence_tokens
        assert all(service.store.block(span.block_id) for e in evidence for span in e.spans)
        trace = service.last_trace
        assert len(trace["candidates"]) <= corpus.retrieval.candidate_limit
        assert trace["structural_expansion"]["enabled"]
        assert len(trace["structural_expansion"]["results"]) <= corpus.retrieval.expansion_limit
        calls = service.provider.calls
        assert service.retrieve("control", paper_ids=[]) == []
        assert service.retrieve("control", section_hint="missing") == []
        assert service.provider.calls == calls


def test_embedding_cache_survives_partial_rebuild(corpus):
    """Verify embedding cache survives partial rebuild."""
    build_index(corpus, TestEmbedder())
    with RetrievalService(corpus, TestEmbedder()) as service:
        chunks = service.store.chunks()
    provider = TestEmbedder()
    cache = EmbeddingCache(corpus.paths.indexes / "embedding_cache.sqlite")
    try:
        vectors, hits = cache.embed_chunks(chunks, provider, 2)
        assert hits == len(chunks) and provider.calls == 0 and len(vectors) == len(chunks)
    finally:
        cache.close()


def test_reranking_reuses_index_candidates_and_preserves_sources(corpus):
    """Verify reranking reuses index candidates and preserves sources."""
    build_index(corpus, TestEmbedder())
    with RetrievalService(corpus, TestEmbedder()) as service:
        baseline = service.retrieve("proximal updates")
        candidate_ids = [row["chunk_id"] for row in service.last_trace["candidates"]]

    class ReverseReranker:
        def rerank(self, query, texts):
            """Helper to reranking integration tests: reverse candidate order with controlled scores."""
            return [(i, float(i)) for i in reversed(range(len(texts)))], {"enabled": True}

    corpus.reranking.enabled = True
    with RetrievalService(corpus, TestEmbedder(), ReverseReranker()) as service:
        reranked = service.retrieve("proximal updates")
        assert [row["chunk_id"] for row in service.last_trace["candidates"]] == candidate_ids
        assert service.last_trace["reranking"]["results"]
        assert service.last_trace["ranking_score"] == "reranker_relevance"
        assert set(e.chunk_id for e in reranked) <= set(candidate_ids)
        assert all(service.store.block(span.block_id) for e in reranked for span in e.spans)
        assert (
            baseline
            and reranked
            and sum(e.token_count for e in reranked) <= corpus.retrieval.evidence_tokens
        )


def test_cited_answers_and_absent_evidence(corpus):
    """Verify cited answers and absent evidence."""
    build_index(corpus, TestEmbedder())

    class GoodGenerator:
        usage = {"input_tokens": 10, "output_tokens": 10}

        def generate(self, instructions, input_text):
            """Helper to cited-answer tests: return a controlled claim citing supplied evidence."""
            assert "untrusted" in instructions
            assert json.loads(input_text)["evidence"]
            return GeneratedAnswer(
                sufficiency="sufficient",
                claims=[Claim(text="The method uses proximal updates.", citations=["E1"])],
                limitations="",
            )

    with RetrievalService(corpus, TestEmbedder()) as service:
        answer = answer_question(service, "proximal updates", GoodGenerator(), paper_ids=["alpha"])
        assert "[E1]" in answer.answer_text
        assert answer.citations["E1"].paper_id == "alpha"
        absent = answer_question(service, "no evidence", paper_ids=[])
        assert absent.sufficiency == "insufficient" and not absent.citations


@pytest.fixture
def baseline_run(corpus, monkeypatch):
    """Helper to replay tests: save a synthetic B0 answer run without hosted model calls."""
    build_index(corpus, TestEmbedder())
    question = BenchmarkQuestion(
        question_id="dev1",
        split="dev",
        kind="unanswerable",
        question="What quantum processor is used?",
        answerable=False,
        expected_points=[],
        evidence_groups=[],
        annotation_status="source_verified",
    )
    path = corpus.paths.manifest.parent / "benchmarks/dev.jsonl"
    write_jsonl(path, [question.model_dump(mode="json")])

    class AbstainingGenerator:
        usage = {"input_tokens": 10, "output_tokens": 10}

        def generate(self, instructions, input_text):
            """Helper to replay tests: return a controlled abstention with nonempty retrieved evidence."""
            assert json.loads(input_text)["evidence"]
            return GeneratedAnswer(
                sufficiency="insufficient", claims=[], limitations="No processor is described."
            )

    def controlled_answer(service, query, **filters):
        """Helper to replay tests: inject a local generator into the real answer workflow."""
        return answer_question(service, query, AbstainingGenerator(), **filters)

    monkeypatch.setattr("fedresearch.evaluation.runner.answer_question", controlled_answer)
    with RetrievalService(corpus, TestEmbedder()) as service:
        result = run_baseline(service, path, "dev", with_answers=True)
    assert result["failures"] == 0
    source = corpus.paths.runs / result["run_id"] / "run.json"
    return path, source, result


def test_evaluation_replays_exact_candidates_without_embedding_or_search(corpus, baseline_run):
    """Verify paired answers reuse exact dense candidates and omit query embedding/search calls."""
    path, source, baseline = baseline_run
    # Historical B0 settings predate hybrid's RRF field; its default must preserve replay.
    baseline["settings"]["retrieval"].pop("rrf_constant")
    atomic_json(source, baseline)
    corpus.reranking.enabled = True
    reranker = Mock()

    def reverse(query, texts):
        """Helper to replay tests: reverse candidates with controlled reranker scores."""
        return [(i, float(i)) for i in reversed(range(len(texts)))], {"enabled": True}

    reranker.rerank.side_effect = reverse
    with RetrievalService(corpus, TestEmbedder(), reranker) as service:
        service.provider.embed = Mock(side_effect=AssertionError("Query embedding must be skipped"))
        service.vectors.query = Mock(side_effect=AssertionError("Dense search must be skipped"))
        result = run_baseline(service, path, "dev", with_answers=True, candidate_source=source)
        service.provider.embed.assert_not_called()
        service.vectors.query.assert_not_called()
    assert result["failures"] == 0
    assert result["candidate_source"] == {
        "run_id": baseline["run_id"],
        "sha256": file_sha256(source),
    }
    answer = result["records"][0]["answer"]
    trace = answer["trace"]["retrieval"]
    original = baseline["records"][0]["answer"]["trace"]["retrieval"]
    assert trace["candidates"] == original["candidates"]
    assert trace["candidate_source"] == "saved_pool" and trace["reranking"]["enabled"]
    assert answer["usage"]["embedding"]["requests"] == 0
    assert answer["usage"]["generation"]["output_tokens"] == 10
    reranker.rerank.assert_called_once()


def test_hybrid_evaluation_replays_fused_pool_and_component_rankings(
    corpus, baseline_run, monkeypatch
):
    """Verify B1-R reuses B1's exact fused pool, component ranks and candidate metrics without searching."""
    path, _, _ = baseline_run
    question = json.loads(path.read_text())
    question["question"] = "Which quantum processor supports proximal updates?"
    write_jsonl(path, [question])
    corpus.retrieval.mode = "hybrid"
    with RetrievalService(corpus, TestEmbedder()) as service:
        baseline = run_baseline(service, path, "dev", with_answers=True)
    assert baseline["failures"] == 0
    source = corpus.paths.runs / baseline["run_id"] / "run.json"
    original = baseline["records"][0]["answer"]["trace"]["retrieval"]
    assert original["rankings"]["dense"] and original["rankings"]["bm25"]
    reranker = Mock()
    reranker.rerank.side_effect = lambda query, texts: (
        [(i, float(i)) for i in reversed(range(len(texts)))],
        {"enabled": True},
    )
    corpus.reranking.enabled = True
    monkeypatch.setattr(LexicalIndex, "query", Mock(side_effect=AssertionError("No BM25 search")))
    with RetrievalService(corpus, TestEmbedder(), reranker) as service:
        service.provider.embed = Mock(side_effect=AssertionError("No query embedding"))
        service.vectors.query = Mock(side_effect=AssertionError("No dense search"))
        result = run_baseline(service, path, "dev", with_answers=True, candidate_source=source)
        assert result["failures"] == 0
        assert (
            result["records"][0]["candidate_metrics"] == baseline["records"][0]["candidate_metrics"]
        )
        trace = result["records"][0]["answer"]["trace"]["retrieval"]
        assert trace["candidates"] == original["candidates"]
        assert trace["rankings"] == original["rankings"]
        assert trace["ranking_score"] == "reranker_relevance"
        assert trace["embedding_usage"]["requests"] == 0
        service.provider.embed.assert_not_called()
        service.vectors.query.assert_not_called()
    assert result["summary"]["scored_answerable_questions"] == 0
    original["lexical_index"]["sqlite_version"] = "different"
    atomic_json(source, baseline)
    with RetrievalService(corpus, TestEmbedder(), reranker) as service:
        with pytest.raises(ValueError, match="same lexical index"):
            run_baseline(service, path, "dev", candidate_source=source)
        assert service.provider.calls == 0


def test_structure_evaluation_reuses_b2a_seeds_then_replays_final_pool(
    corpus, baseline_run, monkeypatch
):
    """Verify seed replay still expands locally, while reranking replay skips every search and expansion."""
    path, _, _ = baseline_run
    question = json.loads(path.read_text())
    question["question"] = "Which processor supports proximal updates?"
    write_jsonl(path, [question])
    corpus.indexing.chunk_policy = "section"
    corpus.retrieval.mode = "hybrid"
    build_index(corpus, TestEmbedder())
    with RetrievalService(corpus, TestEmbedder()) as service:
        b2a = run_baseline(service, path, "dev", with_answers=True)
    assert b2a["failures"] == 0
    seed_source = corpus.paths.runs / b2a["run_id"] / "run.json"
    original = b2a["records"][0]["answer"]["trace"]["retrieval"]
    corpus.retrieval.mode = "structure"
    original_query = LexicalIndex.query

    def local_neighbors_only(index, query, limit, paper_ids, chunk_ids=None):
        """Helper to seed-replay tests: reject an initial corpus-wide lexical search."""
        assert chunk_ids is not None and len(chunk_ids) <= 5
        return original_query(index, query, limit, paper_ids, chunk_ids)

    monkeypatch.setattr(LexicalIndex, "query", local_neighbors_only)
    with RetrievalService(corpus, TestEmbedder()) as service:
        service.provider.embed = Mock(side_effect=AssertionError("No query embedding"))
        service.vectors.query = Mock(side_effect=AssertionError("No dense search"))
        b2 = run_baseline(service, path, "dev", with_answers=True, seed_source=seed_source)
        assert b2["failures"] == 0
        trace = b2["records"][0]["answer"]["trace"]["retrieval"]
        assert trace["structural_expansion"]["seed_candidates"] == original["candidates"]
        assert trace["candidate_source"] == "saved_seeds"
        assert b2["records"][0]["seed_candidate_metrics"] == b2a["records"][0]["candidate_metrics"]
        assert trace["embedding_usage"]["requests"] == 0
        assert b2["seed_source"] == {"run_id": b2a["run_id"], "sha256": file_sha256(seed_source)}
        assert b2["candidate_source"] is None
        assert b2["retrieval_protocol"]["rrf_constant"] == 60
        service.provider.embed.assert_not_called()
        service.vectors.query.assert_not_called()
    final_source = corpus.paths.runs / b2["run_id"] / "run.json"
    with monkeypatch.context() as empty:
        empty.setattr(LexicalIndex, "query", Mock(return_value=[]))
        with RetrievalService(corpus, TestEmbedder()) as service:
            service.vectors.query = Mock(return_value=[])
            no_evidence = run_baseline(service, path, "dev", with_answers=True)
            assert no_evidence["failures"] == 0
            assert no_evidence["records"][0]["answer"]["evidence"] == []
    empty_source = corpus.paths.runs / no_evidence["run_id"] / "run.json"
    reranker = Mock()
    reranker.rerank.side_effect = lambda query, texts: (
        [(i, float(i)) for i in reversed(range(len(texts)))],
        {"enabled": True},
    )
    corpus.reranking.enabled = True
    monkeypatch.setattr(LexicalIndex, "query", Mock(side_effect=AssertionError("No BM25 search")))
    monkeypatch.setattr(
        "fedresearch.retrieval.service.expand_hierarchy",
        Mock(side_effect=AssertionError("No expansion")),
    )
    with RetrievalService(corpus, TestEmbedder(), reranker) as service:
        service.provider.embed = Mock(side_effect=AssertionError("No embedding"))
        service.vectors.query = Mock(side_effect=AssertionError("No dense search"))
        replay = run_baseline(
            service, path, "dev", with_answers=True, candidate_source=final_source
        )
        assert replay["failures"] == 0
        after = replay["records"][0]["answer"]["trace"]["retrieval"]
        assert after["candidates"] == trace["candidates"]
        assert after["structural_expansion"] == trace["structural_expansion"]
        assert (
            replay["records"][0]["seed_candidate_metrics"]
            == b2["records"][0]["seed_candidate_metrics"]
        )
        assert after["ranking_score"] == "reranker_relevance"
        assert after["embedding_usage"]["requests"] == 0
        with pytest.raises(ValueError, match="either candidate_source or seed_source"):
            run_baseline(
                service, path, "dev", candidate_source=final_source, seed_source=seed_source
            )
        with pytest.raises(ValueError, match="Seed source requires"):
            run_baseline(service, path, "dev", seed_source=seed_source)
        empty_replay = run_baseline(
            service, path, "dev", with_answers=True, candidate_source=empty_source
        )
        assert empty_replay["failures"] == 0
        assert empty_replay["records"][0]["answer"]["evidence"] == []


def test_seed_replay_rejects_a_fixed_index_source_before_search(corpus, baseline_run):
    """Verify B2a/B2 replay cannot mix chunk policies or silently fall back to a different index."""
    path, source, _ = baseline_run
    corpus.indexing.chunk_policy = "section"
    corpus.retrieval.mode = "structure"
    with pytest.raises(ValueError, match="No active index for this chunk policy"):
        RetrievalService(corpus, TestEmbedder())
    build_index(corpus, TestEmbedder())
    with RetrievalService(corpus, TestEmbedder()) as service:
        with pytest.raises(ValueError, match="Candidate source"):
            run_baseline(service, path, "dev", seed_source=source)
        assert service.provider.calls == 0


@pytest.mark.parametrize(
    "mismatch", ["index", "labels", "settings", "prompt", "questions", "missing_answer"]
)
def test_evaluation_rejects_incompatible_candidate_sources(corpus, baseline_run, mismatch):
    """Reject stale or incomparable replay inputs before any reranking/generation calls."""
    path, source, baseline = baseline_run
    if mismatch == "index":
        baseline["index_id"] = "different"
    elif mismatch == "labels":
        baseline["dataset_sha256"] = "different"
    elif mismatch == "settings":
        baseline["settings"]["retrieval"]["candidate_limit"] += 1
    elif mismatch == "prompt":
        baseline["records"][0]["answer"]["trace"]["prompt_sha256"] = "different"
    elif mismatch == "missing_answer":
        answer = baseline["records"][0].pop("answer")
        baseline["records"][0]["trace"] = answer["trace"]["retrieval"]
    else:
        baseline["records"][0]["question_id"] = "different"
    atomic_json(source, baseline)
    corpus.reranking.enabled = True
    reranker = Mock()
    with RetrievalService(corpus, TestEmbedder(), reranker) as service:
        with pytest.raises(ValueError, match="Candidate source"):
            run_baseline(service, path, "dev", with_answers=True, candidate_source=source)
        assert service.provider.calls == 0
        reranker.rerank.assert_not_called()


@pytest.mark.parametrize(
    "generated",
    [
        GeneratedAnswer(
            sufficiency="sufficient",
            claims=[Claim(text="Unsupported", citations=["E999"])],
            limitations="",
        ),
        GeneratedAnswer(sufficiency="sufficient", claims=[], limitations=""),
        GeneratedAnswer(sufficiency="insufficient", claims=[], limitations=""),
    ],
)
def test_bad_citations_and_sufficiency_are_rejected(generated):
    """Verify bad citations and sufficiency are rejected."""
    with pytest.raises(ValueError):
        validate_citations(generated, [])


def test_benchmark_source_spans_and_metric_denominators(corpus):
    """Verify benchmark source spans and metric denominators."""
    build_index(corpus, TestEmbedder())
    with RetrievalService(corpus, TestEmbedder()) as service:
        evidence = service.retrieve("proximal", paper_ids=["alpha"], top_k=1)
        item = evidence[0]
        span = item.spans[0]
        block = service.store.block(span.block_id)
        passage = GoldPassage(
            paper_id=item.paper_id,
            document_version=item.document_version,
            parse_id=item.parse_id,
            page=block.page,
            span=span,
            quote=block.raw_text[span.start : span.end],
        )
        question = BenchmarkQuestion(
            question_id="dev1",
            split="dev",
            kind="paper_specific",
            question="What does the method use?",
            answerable=True,
            expected_points=["Proximal updates"],
            evidence_groups=[
                EvidenceGroup(
                    group_id="mechanism", required_fact="Proximal updates", alternatives=[passage]
                )
            ],
            annotation_status="source_verified",
        )
        verify_question(question, service.store)
        metrics = score_retrieval(question, evidence, k=5)
        assert metrics["precision_at_k"] == 0.2
        assert metrics["evidence_group_recall_at_k"] == 1
        path = corpus.paths.manifest.parent / "benchmarks/dev.jsonl"
        write_jsonl(path, [question.model_dump(mode="json")])
        corpus.retrieval.mode = "hybrid"
        result = run_baseline(service, path, "dev")
        assert result["failures"] == 0
        assert result["summary"]["scored_answerable_questions"] == 1
        assert result["summary"]["candidate_group_recall"] == 1
        assert result["records"][0]["candidate_metrics"]["covered_groups"] == ["mechanism"]
        bad = question.model_copy(deep=True)
        bad.evidence_groups[0].alternatives[0].quote = "wrong"
        with pytest.raises(ValueError, match="quote/span"):
            verify_question(bad, service.store)
        negative = BenchmarkQuestion(
            question_id="dev2",
            split="dev",
            kind="unanswerable",
            question="Unknown?",
            answerable=False,
            expected_points=[],
            evidence_groups=[],
            annotation_status="source_verified",
        )
        assert score_retrieval(negative, evidence)["precision_at_k"] is None


def test_test_labels_require_freeze(tmp_path):
    """Verify test labels require freeze."""
    with pytest.raises(ValueError, match="not frozen"):
        require_frozen(tmp_path / "test.jsonl")


def test_cli_help_and_missing_credentials(monkeypatch):
    """Verify cli help and missing credentials."""
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0 and "preprocess" in result.output
    removed = CliRunner().invoke(app, ["corpus", "--help"])
    assert removed.exit_code == 2 and "No such command" in removed.output
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("VOYAGE_API_KEY", "")
    result = subprocess.run(
        [sys.executable, "-m", "fedresearch.cli", "doctor", "--live"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1 and "VOYAGE_API_KEY" in result.stderr
    assert "Traceback" not in result.stderr


def test_borderless_table_is_excluded_by_caption_rules():
    """Verify borderless table is excluded by caption rules."""
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((80, 100), "Table 1. Dataset statistics", fontsize=10)
    page.draw_line((60, 115), (290, 115))
    page.draw_line((60, 170), (290, 170))
    page.insert_text((80, 140), "MNIST 1000 69035", fontsize=10)
    regions = caption_table_regions(page, extract_items(page))
    assert len(regions) == 1 and regions[0][1] == 115 and regions[0][3] == 172
    doc.close()
