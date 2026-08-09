"""Checks for Voyage chunk sizes, Unicode coverage and original-source citations."""

import pytest

from fedresearch.preprocessing.chunking import fixed_chunks
from fedresearch.preprocessing.cleaning import clean_text
from fedresearch.schemas import Block, Section
from fedresearch.settings import Preprocessing
from fedresearch.tokenization import load_tokenizer


@pytest.mark.parametrize("overlap", [0, 13, 63])
def test_voyage_windows_preserve_unicode_and_source_spans(overlap):
    """Verify bounded windows preserve scientific Unicode and cite every original nonspace character."""
    config = Preprocessing(chunk_tokens=64, overlap_tokens=overlap)
    raw = "∇𝛼 β 中文 🙂 federated hetero-\ngeneity <|endoftext|> " * 80
    text, text_map = clean_text(raw)
    block = Block(
        block_id="paper:parse:p001:b00000",
        paper_id="paper",
        document_version="v1",
        page=1,
        bbox=(0, 0, 100, 100),
        order=0,
        raw_text=raw,
        text=text,
        text_map=text_map,
        font_size=10,
        section_id="intro",
    )
    section = Section(
        section_id="intro",
        paper_id="paper",
        title="Introduction",
        parent_id=None,
        path=["Introduction"],
        block_ids=[block.block_id],
        confidence=1,
    )
    chunks = fixed_chunks([block], [section], "parse", config)
    tokenizer = load_tokenizer(config.tokenizer, config.tokenizer_revision)
    covered = set()
    assert len(chunks) > 1
    for chunk in chunks:
        assert "\ufffd" not in chunk.text
        assert chunk.text in text
        assert chunk.token_count == len(tokenizer.encode(chunk.text, add_special_tokens=False))
        assert 0 < chunk.token_count <= config.chunk_tokens
        assert chunk.pages == [1]
        for span in chunk.spans:
            assert span.block_id == block.block_id
            assert clean_text(raw[span.start : span.end])[0] == chunk.text
            covered.update(range(span.start, span.end))
    assert all(i in covered for i, char in enumerate(raw) if not char.isspace())


def test_voyage_tokenizer_does_not_truncate_or_pad():
    """Verify local counting keeps long inputs intact and does not pad short queries."""
    config = Preprocessing()
    tokenizer = load_tokenizer(config.tokenizer, config.tokenizer_revision)
    assert len(tokenizer.encode("privacy " * 35000, add_special_tokens=False)) > 32768
    assert tokenizer.truncation is None
    assert tokenizer.padding is None
