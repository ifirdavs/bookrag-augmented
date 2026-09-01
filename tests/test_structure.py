"""Section-boundary provenance and bounded hierarchy navigation checks."""

from pathlib import Path

import pytest

from fedresearch.indexing.lexical_index import LexicalIndex, build_lexical_index
from fedresearch.preprocessing.chunking import section_chunks
from fedresearch.preprocessing.cleaning import clean_text
from fedresearch.preprocessing.validation import validate_document
from fedresearch.retrieval.hierarchy import expand_hierarchy
from fedresearch.schemas import Block, Paper, ParsedDocument, Section
from fedresearch.settings import Preprocessing, Retrieval, Settings
from fedresearch.storage.metadata_store import MetadataStore
from fedresearch.tokenization import load_tokenizer


@pytest.fixture
def tree_document():
    """Helper to structure tests: build canonical blocks with parent/child, fallback and reference sections."""
    paper = Paper(
        paper_id="paper",
        title="Fixture",
        year=2020,
        source_url="https://example.org",
        document_version="fixture:1",
        sha256="a" * 64,
    )
    config = Preprocessing(chunk_tokens=64, overlap_tokens=13)
    blocks, sections = [], []
    for index, (title, parent, kind, raw) in enumerate(
        [
            ("Front", None, "fallback", "Unclassified introductory content. " * 40),
            ("Method", None, "section", "Method overview and global aggregation. " * 40),
            (
                "Drift",
                1,
                "section",
                "Client drift correction with β gradients and 中文 data. " * 60,
            ),
            ("Privacy", 1, "section", "Privacy protection with clipping and noise. " * 30),
            ("Experiments", 1, "section", "Method privacy experiments and evaluation. " * 30),
            ("References", None, "references", "Reference-only content must be excluded. " * 10),
        ]
    ):
        section_id = f"paper:parse:s{index:03d}"
        text, mapping = clean_text(raw)
        block = Block(
            block_id=f"paper:parse:b{index:03d}",
            paper_id="paper",
            document_version=paper.document_version,
            page=1,
            bbox=(0, index * 20, 100, index * 20 + 10),
            order=index,
            raw_text=raw,
            text=text,
            text_map=mapping,
            font_size=10,
            section_id=section_id,
        )
        blocks.append(block)
        sections.append(
            Section(
                section_id=section_id,
                paper_id="paper",
                title=title,
                parent_id=f"paper:parse:s{parent:03d}" if parent is not None else None,
                path=["Method", title] if parent is not None else [title],
                block_ids=[block.block_id],
                confidence=0 if kind == "fallback" else 1,
                kind=kind,
            )
        )
    chunks = section_chunks(blocks, sections, "parse", config)
    document = ParsedDocument(
        paper=paper,
        parse_id="parse",
        parser_version=config.parser_version,
        page_count=1,
        blocks=blocks,
        sections=sections,
        chunks=chunks,
        diagnostics={"serious_warnings": []},
    )
    validate_document(document)
    return document, config


@pytest.fixture
def hierarchy_store(tree_document, tmp_path):
    """Helper to navigation tests: persist real source records and FTS5 statistics without model calls."""
    document, _ = tree_document
    store = MetadataStore(Path(":memory:"), create=True)
    store.add_document(document)
    path = tmp_path / "bm25.sqlite"
    build_lexical_index(path, "index", "fingerprint", document.chunks)
    lexical = LexicalIndex(path, "index", "fingerprint", len(document.chunks))
    try:
        yield store, lexical
    finally:
        lexical.close()
        store.close()


def test_section_chunks_preserve_all_usable_source_characters(tree_document):
    """Verify token caps, unique IDs, full Unicode/source coverage and no crossing of section boundaries."""
    document, config = tree_document
    tokenizer = load_tokenizer(config.tokenizer, config.tokenizer_revision)
    assert len({c.chunk_id for c in document.chunks}) == len(document.chunks)
    coverage = {b.block_id: set() for b in document.blocks}
    for chunk in document.chunks:
        assert chunk.policy == "section" and chunk.parse_id == "parse"
        assert len(chunk.section_ids) == 1
        assert chunk.token_count == len(tokenizer.encode(chunk.text, add_special_tokens=False))
        assert 0 < chunk.token_count <= 64
        for span in chunk.spans:
            block = next(b for b in document.blocks if b.block_id == span.block_id)
            assert block.section_id == chunk.section_id
            coverage[span.block_id].update(range(span.start, span.end))
    for block, section in zip(document.blocks, document.sections, strict=True):
        if section.kind == "references":
            assert not coverage[block.block_id]
        else:
            assert all(
                i in coverage[block.block_id]
                for i, char in enumerate(block.raw_text)
                if not char.isspace()
            )


def test_heading_only_sections_remain_tree_nodes_without_empty_evidence(tree_document):
    """Verify contentless section headings remain navigable metadata but are not indexed as passages."""
    document, config = tree_document
    block = document.blocks[3]
    block.kind = "heading"
    block.raw_text = "Appendix"
    block.text, block.text_map = clean_text(block.raw_text)
    chunks = section_chunks(document.blocks, document.sections, document.parse_id, config)
    assert not any(c.section_id == block.section_id for c in chunks)
    assert any(s.section_id == block.section_id for s in document.sections)


@pytest.mark.parametrize(
    "section_title,query,reason",
    [
        ("Method", "privacy", "child_section"),
        ("Drift", "method", "parent_section"),
        ("Drift", "drift", "adjacent_chunk"),
    ],
)
def test_navigation_uses_only_bounded_real_section_links(
    hierarchy_store, section_title, query, reason
):
    """Verify child, parent and adjacent navigation retain source identity and inherit the anchor score."""
    store, lexical = hierarchy_store
    section = next(s for s in store.sections() if s.title == section_title)
    seed = next(c for c in store.chunks() if c.section_id == section.section_id)
    config = Retrieval(
        candidate_limit=5, top_k=3, expansion_seeds=1, expansion_per_seed=1, expansion_limit=1
    )
    ranked, trace = expand_hierarchy(query, [(seed.chunk_id, 0.03)], store, lexical, config)
    assert len(ranked) == 2 and len(trace["results"]) == 1
    result = trace["results"][0]
    assert result["reason"] == reason and result["from_seed"] == seed.chunk_id
    context = store.chunk(result["chunk_id"])
    assert context.paper_id == seed.paper_id and ranked[1][1] == 0.03
    assert result["section_id"] == context.section_id
    assert all(store.block(span.block_id) for span in context.spans)


def test_expansion_respects_source_scope_and_does_not_expand_unclassified_hierarchy(
    hierarchy_store,
):
    """Verify explicit section scope wins over expansion and fallback sections use only adjacent chunks."""
    store, lexical = hierarchy_store
    seed = next(c for c in store.chunks() if store.section(c.section_id).kind == "fallback")
    config = Retrieval(
        candidate_limit=5, top_k=3, expansion_seeds=1, expansion_per_seed=2, expansion_limit=2
    )
    ranked, trace = expand_hierarchy("unknownword", [(seed.chunk_id, 0.03)], store, lexical, config)
    assert len(ranked) > 1
    assert all(
        r["reason"] == "adjacent_chunk" and r["selection"] == "adjacency_fallback"
        for r in trace["results"]
    )
    ranked, trace = expand_hierarchy(
        "unknownword", [(seed.chunk_id, 0.03)], store, lexical, config, [seed.chunk_id]
    )
    assert ranked == [(seed.chunk_id, 0.03)] and trace["results"] == []
    ranked, trace = expand_hierarchy("unknownword", [], store, lexical, config)
    assert ranked == [] and trace["seed_candidates"] == []


def test_expansion_promotes_existing_candidates_without_duplicates_or_exceeding_cap(
    hierarchy_store,
):
    """Verify context promotion, global/per-anchor budgets, final cap and deterministic ordering."""
    store, lexical = hierarchy_store
    chunks = store.chunks()
    parent = next(c for c in chunks if store.section(c.section_id).title == "Method")
    privacy = next(c for c in chunks if store.section(c.section_id).title == "Privacy")
    others = [c for c in chunks if c.chunk_id not in {parent.chunk_id, privacy.chunk_id}]
    ranked = [
        (parent.chunk_id, 0.03),
        (privacy.chunk_id, 0.02),
        *[(c.chunk_id, 0.01) for c in others[:3]],
    ]
    config = Retrieval(
        candidate_limit=5, top_k=3, expansion_seeds=1, expansion_per_seed=2, expansion_limit=2
    )
    merged, trace = expand_hierarchy("privacy", ranked, store, lexical, config)
    assert len(merged) <= 5 and len({identifier for identifier, _ in merged}) == len(merged)
    assert len(trace["results"]) <= 2
    assert any(
        r["chunk_id"] == privacy.chunk_id and r["action"] == "promoted" for r in trace["results"]
    )
    assert expand_hierarchy("privacy", ranked, store, lexical, config) == (merged, trace)


def test_structure_settings_reject_fixed_chunks_and_unbounded_expansion():
    """Verify hierarchy mode cannot target fixed chunks or consume the entire candidate budget."""
    with pytest.raises(ValueError, match="section chunks"):
        Settings.model_validate({"retrieval": {"mode": "structure"}})
    with pytest.raises(ValueError, match="smaller than candidate_limit"):
        Settings.model_validate(
            {
                "indexing": {"chunk_policy": "section"},
                "retrieval": {"mode": "structure", "candidate_limit": 6, "expansion_limit": 6},
            }
        )
