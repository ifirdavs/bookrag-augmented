"""Integrity checks that keep malformed or seriously warned parses out of the index."""

from fedresearch.schemas import ParsedDocument


def validate_document(doc: ParsedDocument) -> None:
    """Validate source IDs, cleaning maps, page ranges, section links and chunk provenance."""
    blocks = {b.block_id: b for b in doc.blocks}
    sections = {s.section_id: s for s in doc.sections}
    if len(blocks) != len(doc.blocks) or len(sections) != len(doc.sections):
        raise ValueError("Duplicate source identities")
    for block in doc.blocks:
        if block.section_id not in sections or not 1 <= block.page <= doc.page_count:
            raise ValueError("Invalid block provenance")
        offsets = []
        for run in block.text_map:
            offsets.extend(range(run.raw_start, run.raw_start + run.clean_end - run.clean_start))
        if (
            len(offsets) != len(block.text)
            or offsets != sorted(offsets)
            or (offsets and offsets[-1] >= len(block.raw_text))
        ):
            raise ValueError("Invalid cleaning map")
    for section in doc.sections:
        if section.parent_id and section.parent_id not in sections:
            raise ValueError("Missing section parent")
        if any(blocks[b].section_id != section.section_id for b in section.block_ids):
            raise ValueError("Section/block membership mismatch")
    for chunk in doc.chunks:
        pages = set()
        for span in chunk.spans:
            block = blocks[span.block_id]
            if span.end > len(block.raw_text):
                raise ValueError("Chunk span outside original block")
            pages.add(block.page)
        if sorted(pages) != chunk.pages or chunk.parse_id != doc.parse_id:
            raise ValueError("Chunk provenance mismatch")
        if chunk.policy == "section" and (
            chunk.section_ids != [chunk.section_id]
            or any(blocks[span.block_id].section_id != chunk.section_id for span in chunk.spans)
        ):
            raise ValueError("Section chunk crosses a section boundary")


def require_reviewed(doc: ParsedDocument) -> None:
    """Helper to load_processed: reject documents with unresolved serious parsing warnings."""
    if doc.diagnostics["serious_warnings"]:
        raise ValueError(
            f"{doc.paper.paper_id}: serious parse warnings require review: {doc.diagnostics['serious_warnings']}"
        )
