"""Heading detection and section hierarchy assignment for canonical source blocks."""

import re

from fedresearch.schemas import Block, Section

NUMBERED = re.compile(
    r"^(\d+(?:\.\d+)*|[IVX]+|[A-Z](?:\.\d+)*)\.?\s+([A-Z](?:[A-Za-z]|-[A-Za-z]).{1,100})$"
)
NAMED = re.compile(
    r"^(abstract|references|bibliography|acknowledg(?:e)?ments?|appendix(?:\s+[A-Z])?|conclusions?|introduction|related work|discussion|methods|results|experiments|experimental results)$",
    re.I,
)


def heading(
    text: str, size: float, bold: bool, body_size: float, page: int
) -> tuple[str, float] | None:
    """Helper to parse_pdf: identify likely section headings from text, numbering and font cues."""
    if len(text) > 115 or len(text.split()) > 16 or text.endswith(":"):
        return None
    named = NAMED.fullmatch(text.strip())
    if named:
        return text, 0.9
    numbered = NUMBERED.fullmatch(text.strip())
    if (
        numbered
        and re.fullmatch(r"[IVX]+", numbered.group(1))
        and numbered.group(2).isupper()
        and size >= body_size * 0.75
    ):
        return text, 0.8
    if numbered and (numbered.group(1)[0].isdigit() or page > 1):
        if bold or size > body_size * 1.06:
            return text, 0.85
        if numbered.group(2).isupper() and size >= body_size * 0.75:
            return text, 0.75
    if page > 1 and size > body_size * 1.18 and bold and not text.endswith((".", ":", ";")):
        return text, 0.65
    return None


def assign_sections(blocks: list[Block], paper_id: str, parse_id: str) -> list[Section]:
    """Build section records and parent links, assigning every block to a section or fallback."""
    root = Section(
        section_id=f"{paper_id}:{parse_id}:root",
        paper_id=paper_id,
        title="Unclassified front matter",
        parent_id=None,
        path=["Unclassified front matter"],
        block_ids=[],
        confidence=0,
        kind="fallback",
    )
    sections = [root]
    current = root
    number_map: dict[str, Section] = {}
    reference_region = False
    for block in blocks:
        if block.kind == "heading":
            title = block.text
            match = NUMBERED.fullmatch(title)
            number = match.group(1) if match else None
            parent_number = number.rsplit(".", 1)[0] if number and "." in number else None
            parent = number_map.get(parent_number)
            if title.casefold() in {"references", "bibliography"}:
                reference_region = True
            elif number or title.casefold().startswith("appendix"):
                reference_region = False
            current = Section(
                section_id=f"{paper_id}:{parse_id}:s{len(sections):03d}",
                paper_id=paper_id,
                title=title,
                parent_id=parent.section_id if parent else None,
                path=([*parent.path, title] if parent else [title]),
                block_ids=[],
                confidence=block.heading_confidence or 0.65,
                kind="references" if reference_region else "section",
            )
            if number:
                number_map[number] = current
            sections.append(current)
        block.section_id = current.section_id
        current.block_ids.append(block.block_id)
    return sections
