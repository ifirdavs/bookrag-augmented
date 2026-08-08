"""Fixed token windows with original block, section and page provenance."""

from bisect import bisect_left

import tiktoken

from fedresearch.schemas import Block, Chunk, Section
from fedresearch.settings import Preprocessing
from fedresearch.util import digest


def fixed_chunks(
    blocks: list[Block], sections: list[Section], parse_id: str, config: Preprocessing
) -> list[Chunk]:
    """Create overlapping token windows with Unicode-safe boundaries and original block/page spans."""
    if not blocks:
        return []
    section_map = {s.section_id: s for s in sections}
    selected = [
        b
        for b in blocks
        if b.text
        and b.kind not in {"margin", "equation"}
        and not (config.exclude_tables and b.kind == "table")
        and not (config.exclude_references and section_map[b.section_id].kind == "references")
    ]
    text, placements = "", []
    for block in selected:
        if text:
            text += "\n\n"
        start = len(text)
        text += block.text
        placements.append((start, len(text), block))
    encoding = tiktoken.get_encoding(config.tokenizer)
    tokens = encoding.encode(text, disallowed_special=())
    byte_offsets = [0]
    for char in text:
        byte_offsets.append(byte_offsets[-1] + len(char.encode("utf-8")))
    byte_boundaries = set(byte_offsets)
    token_offsets = [0]
    for token in tokens:
        token_offsets.append(token_offsets[-1] + len(encoding.decode_single_token_bytes(token)))
    chunks = []
    start_token = 0
    while start_token < len(tokens):
        end_token = min(start_token + config.chunk_tokens, len(tokens))
        # End a window only on a Unicode boundary, avoiding U+FFFD or lost characters.
        while end_token > start_token and token_offsets[end_token] not in byte_boundaries:
            end_token -= 1
        start_char = bisect_left(byte_offsets, token_offsets[start_token])
        end_char = bisect_left(byte_offsets, token_offsets[end_token])
        window = text[start_char:end_char]
        left = len(window) - len(window.lstrip())
        right = len(window.rstrip())
        start_char += left
        end_char = start_char + right - left
        spans, page_numbers, section_ids = [], set(), []
        for a, b, block in placements:
            lo, hi = max(start_char, a), min(end_char, b)
            if lo < hi:
                spans.append(block.raw_span(lo - a, hi - a))
                page_numbers.add(block.page)
                if block.section_id not in section_ids:
                    section_ids.append(block.section_id)
        if spans:
            value = text[start_char:end_char]
            first = selected[0]
            chunks.append(
                Chunk(
                    chunk_id=f"{first.paper_id}:{parse_id}:c{len(chunks):05d}:{digest(value)[:8]}",
                    paper_id=first.paper_id,
                    document_version=first.document_version,
                    parse_id=parse_id,
                    text=value,
                    section_id=section_ids[0],
                    section_path=section_map[section_ids[0]].path,
                    section_ids=section_ids,
                    spans=spans,
                    token_count=len(encoding.encode(value, disallowed_special=())),
                    pages=sorted(page_numbers),
                )
            )
        if end_token == len(tokens):
            break
        next_start = max(start_token + 1, end_token - config.overlap_tokens)
        # Move backward to a valid character boundary when overlap is available.
        while next_start > start_token + 1 and token_offsets[next_start] not in byte_boundaries:
            next_start -= 1
        start_token = next_start
    return chunks
