"""Tests for pipeline behavior and regression boundaries."""

import json
import re
import subprocess
import sys

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
from fedresearch.indexing.embeddings import EmbeddingCache
from fedresearch.indexing.pipeline import build_index, preprocess
from fedresearch.llm.answering import answer_question, validate_citations
from fedresearch.llm.client import ProviderError, validate_vectors
from fedresearch.preprocessing.cleaning import clean_text
from fedresearch.preprocessing.pdf_parser import (
    caption_table_regions,
    extract_items,
    ordered_blocks,
)
from fedresearch.preprocessing.sections import heading
from fedresearch.retrieval.service import RetrievalService
from fedresearch.schemas import Block, Claim, GeneratedAnswer, Paper
from fedresearch.settings import Preprocessing, Settings
from fedresearch.util import file_sha256, write_jsonl


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
        with pytest.raises(ValueError, match="Only dense"):
            service.retrieve("updates", mode="graph")
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
