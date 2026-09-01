"""Fixed and section-bounded token windows with original source provenance."""

from fedresearch.schemas import Block, Chunk, Section
from fedresearch.settings import Preprocessing
from fedresearch.tokenization import load_tokenizer
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
    tokenizer = load_tokenizer(config.tokenizer, config.tokenizer_revision)
    offsets = tokenizer.encode(text, add_special_tokens=False).offsets
    chunks = []
    start_token = 0
    while start_token < len(offsets):
        end_token = min(start_token + config.chunk_tokens, len(offsets))
        start_char = offsets[start_token][0]
        while end_token > start_token:
            end_char = offsets[end_token - 1][1]
            window = text[start_char:end_char]
            value = window.strip()
            token_count = len(tokenizer.encode(value, add_special_tokens=False))
            # Preserve whole characters and recount text at its new BPE boundaries.
            splits_character = end_token < len(offsets) and offsets[end_token][0] < end_char
            if not splits_character and token_count <= config.chunk_tokens:
                break
            end_token -= 1
        start_char += len(window) - len(window.lstrip())
        end_char = start_char + len(value)
        spans, page_numbers, section_ids = [], set(), []
        for a, b, block in placements:
            lo, hi = max(start_char, a), min(end_char, b)
            if lo < hi:
                spans.append(block.raw_span(lo - a, hi - a))
                page_numbers.add(block.page)
                if block.section_id not in section_ids:
                    section_ids.append(block.section_id)
        if spans:
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
                    token_count=token_count,
                    pages=sorted(page_numbers),
                )
            )
        if end_token == len(offsets):
            break
        next_start = max(start_token + 1, end_token - config.overlap_tokens)
        while next_start < len(offsets) and offsets[next_start][0] < offsets[next_start - 1][1]:
            next_start += 1
        start_token = next_start
    return chunks


def section_chunks(
    blocks: list[Block], sections: list[Section], parse_id: str, config: Preprocessing
) -> list[Chunk]:
    """Split each section into bounded overlapping windows without changing canonical source IDs."""
    grouped = {section.section_id: [] for section in sections}
    headings = {block.block_id for block in blocks if block.kind == "heading"}
    for block in blocks:
        grouped[block.section_id].append(block)
    chunks = []
    for section in sections:
        for chunk in fixed_chunks(grouped[section.section_id], sections, parse_id, config):
            if all(span.block_id in headings for span in chunk.spans):
                continue
            chunk.policy = "section"
            chunk.chunk_id = (
                f"{chunk.paper_id}:{parse_id}:sc{len(chunks):05d}:{digest(chunk.text)[:8]}"
            )
            chunks.append(chunk)
    return chunks
