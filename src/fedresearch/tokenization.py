"""Shared local Voyage tokenizer for chunk boundaries, evidence counts and query limits."""

from functools import cache

from tokenizers import Tokenizer


@cache
def load_tokenizer(name: str, revision: str) -> Tokenizer:
    """Helper to chunking and retrieval: cache the pinned Voyage tokenizer without padding or truncation."""
    tokenizer = Tokenizer.from_pretrained(name, revision=revision)
    tokenizer.no_truncation()
    tokenizer.no_padding()
    return tokenizer
