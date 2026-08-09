"""PDF layout extraction with source coordinates, diagnostic warnings and stable parse identities."""

import re
from collections import Counter
from pathlib import Path
from statistics import median

import pymupdf

from fedresearch.preprocessing.chunking import fixed_chunks
from fedresearch.preprocessing.cleaning import clean_text
from fedresearch.preprocessing.sections import NAMED, assign_sections, heading
from fedresearch.schemas import Block, Paper, ParsedDocument
from fedresearch.settings import Preprocessing
from fedresearch.util import digest, file_sha256


def ordered_blocks(items: list[dict], width: float) -> tuple[list[dict], bool]:
    """Helper to parse_pdf: order two columns independently, using wide blocks as vertical barriers."""
    midpoint = width / 2
    left = [b for b in items if b["bbox"][2] <= midpoint + 12 and b["bbox"][0] < midpoint - 30]
    right = [b for b in items if b["bbox"][0] >= midpoint - 12]
    columns = len(left) >= 3 and len(right) >= 3
    if not columns:
        return sorted(items, key=lambda b: (b["bbox"][1], b["bbox"][0])), False
    wide = sorted(
        [b for b in items if b not in left and b not in right], key=lambda b: b["bbox"][1]
    )
    remaining = left + right
    result = []

    def region(region_items):
        """Helper to ordered_blocks: sort one region by column and vertical position."""
        return sorted(
            region_items, key=lambda b: (b["bbox"][0] >= midpoint - 12, b["bbox"][1], b["bbox"][0])
        )

    for barrier in wide:
        before = [b for b in remaining if b["bbox"][1] < barrier["bbox"][1]]
        result.extend(region(before))
        remaining = [b for b in remaining if b not in before]
        result.append(barrier)
    result.extend(region(remaining))
    return result, True


def extract_items(page) -> list[dict]:
    """Helper to parse_pdf: extract text, bounding boxes and font cues, splitting disjoint column lines."""
    items = []
    for block in page.get_text(
        "dict", flags=pymupdf.TEXTFLAGS_DICT & ~pymupdf.TEXT_PRESERVE_IMAGES
    )["blocks"]:
        if block.get("type") != 0:
            continue
        groups: list[list[dict]] = []
        for line in block["lines"]:
            previous = groups[-1][-1] if groups else None
            text = "".join(span["text"] for span in line["spans"]).strip()
            # Separate disjoint columns and named heading lines merged with prose.
            if previous and (
                abs(line["bbox"][0] - previous["bbox"][0]) > page.rect.width * 0.25
                or (
                    abs(line["bbox"][1] - previous["bbox"][1]) > 2
                    and (
                        NAMED.fullmatch(text)
                        or NAMED.fullmatch("".join(s["text"] for s in previous["spans"]).strip())
                    )
                )
            ):
                groups.append([])
            if not groups:
                groups.append([])
            groups[-1].append(line)
        for lines in groups:
            spans = [span for line in lines for span in line["spans"] if span["text"].strip()]
            if not spans:
                continue
            raw = "\n".join("".join(span["text"] for span in line["spans"]) for line in lines)
            boxes = [line["bbox"] for line in lines]
            box = (
                min(b[0] for b in boxes),
                min(b[1] for b in boxes),
                max(b[2] for b in boxes),
                max(b[3] for b in boxes),
            )
            sizes = [(round(s["size"], 1), len(s["text"])) for s in spans]
            size = max(
                {s for s, _ in sizes}, key=lambda value: sum(n for s, n in sizes if s == value)
            )
            bold_chars = sum(len(s["text"]) for s in spans if s["flags"] & 16)
            items.append(
                {
                    "raw_text": raw,
                    "bbox": box,
                    "font_size": size,
                    "bold": bold_chars > sum(n for _, n in sizes) / 2,
                    "vertical": any(abs(line.get("dir", (1, 0))[1]) > 0.5 for line in lines),
                }
            )
    return items


def caption_table_regions(page, items: list[dict]) -> list[list[float]]:
    """Helper to parse_pdf: detect captioned table regions bounded by horizontal rules."""
    rules = []
    for drawing in page.get_drawings():
        for item in drawing["items"]:
            if item[0] == "l":
                a, b = item[1], item[2]
                width = abs(a.x - b.x)
                if abs(a.y - b.y) < 1 and 120 < width < page.rect.width * 0.7:
                    rules.append((min(a.x, b.x), a.y, max(a.x, b.x)))
    regions = []
    for item in items:
        if not re.match(r"^Table\s+\d", item["raw_text"]):
            continue
        box = item["bbox"]
        center = (box[0] + box[2]) / 2
        below = [r for r in rules if box[3] - 2 <= r[1] <= box[3] + 220 and r[0] <= center <= r[2]]
        if len(below) >= 2:
            regions.append(
                [
                    min(r[0] for r in below) - 8,
                    min(r[1] for r in below),
                    max(r[2] for r in below) + 8,
                    max(r[1] for r in below) + 2,
                ]
            )
    return regions


def parse_id_for(paper: Paper, config: Preprocessing) -> str:
    """Helper to parse_pdf and index validation: hash the PDF and parser settings into a stable parse ID."""
    return digest(
        {
            "sha256": paper.sha256,
            "parser": config.parser_version,
            "pymupdf": pymupdf.VersionBind,
            "config": config.model_dump(),
        }
    )[:16]


def parse_pdf(path: Path, paper: Paper, config: Preprocessing) -> ParsedDocument:
    """Parse a pinned PDF into source blocks, section hierarchy, fixed chunks and layout diagnostics."""
    if paper.sha256 != file_sha256(path):
        raise ValueError(f"{paper.paper_id}: PDF checksum differs from the manifest")
    parse_id = parse_id_for(paper, config)
    all_items, page_info, margins = [], [], Counter()
    with pymupdf.open(path) as doc:
        if doc.needs_pass or not doc.page_count:
            raise ValueError("Encrypted or empty PDF")
        for page in doc:
            items, columns = ordered_blocks(extract_items(page), page.rect.width)
            tables, table_error = [], False
            try:
                tables = [list(table.bbox) for table in page.find_tables().tables]
                tables.extend(caption_table_regions(page, items))
            except Exception:
                table_error = True
            page_info.append(
                {
                    "page": page.number + 1,
                    "characters": sum(len(b["raw_text"]) for b in items),
                    "two_columns": columns,
                    "table_regions": tables,
                    "table_detection_failed": table_error,
                    "images": len(page.get_images()),
                    "width": page.rect.width,
                    "height": page.rect.height,
                }
            )
            for item in items:
                text, mapping = clean_text(item["raw_text"])
                item.update(
                    {
                        "page": page.number + 1,
                        "label": page.get_label() or None,
                        "text": text,
                        "text_map": mapping,
                        "height": page.rect.height,
                        "tables": tables,
                    }
                )
                if (
                    item["bbox"][3] < page.rect.height * 0.12
                    or item["bbox"][1] > page.rect.height * 0.88
                ):
                    margins[
                        (
                            text.casefold(),
                            "top" if item["bbox"][3] < page.rect.height * 0.12 else "bottom",
                        )
                    ] += 1
            all_items.extend(items)
        page_count = doc.page_count
    body_sizes = [item["font_size"] for item in all_items if len(item["text"]) > 120]
    body_size = (
        median(body_sizes)
        if body_sizes
        else median([item["font_size"] for item in all_items] or [10])
    )
    blocks = []
    for item in all_items:
        text = item["text"]
        if not text:
            continue
        box = item["bbox"]
        warnings, kind = [], "text"
        detected_heading = heading(text, item["font_size"], item["bold"], body_size, item["page"])
        position = (
            "top"
            if box[3] < item["height"] * 0.12
            else "bottom"
            if box[1] > item["height"] * 0.88
            else None
        )
        if item["vertical"]:
            kind = "margin"
            warnings.append("excluded_rotated_margin")
        elif position and (
            margins[(text.casefold(), position)] >= max(3, page_count * 0.3)
            or (position == "bottom" and re.fullmatch(r"\d+", text))
        ):
            kind = "margin"
            warnings.append("excluded_margin")
        elif re.match(r"^(Figure|Fig\.|Table)\s+\d", text):
            kind = "caption"
            if text.startswith("Table"):
                warnings.append("table_values_not_interpreted")
        else:
            area = max(1, (box[2] - box[0]) * (box[3] - box[1]))
            for table in item["tables"]:
                intersection = max(0, min(box[2], table[2]) - max(box[0], table[0])) * max(
                    0, min(box[3], table[3]) - max(box[1], table[1])
                )
                if intersection / area >= 0.5:
                    kind = "table"
                    warnings.append("table_not_validated")
                    break
            if kind == "text" and detected_heading:
                kind = "heading"
            letters = sum(c.isalpha() for c in text)
            if kind == "text" and (
                (len(text) > 15 and letters / len(text) < 0.35)
                or (len(text) < 60 and not re.search(r"[A-Za-z]{3,}", text))
            ):
                kind = "equation"
                warnings.append("nonprose_not_interpreted")
        if "\ufffd" in text:
            warnings.append("replacement_characters")
        blocks.append(
            Block(
                block_id=f"{paper.paper_id}:{parse_id}:p{item['page']:03d}:b{len(blocks):05d}",
                paper_id=paper.paper_id,
                document_version=paper.document_version,
                page=item["page"],
                printed_page_label=item["label"],
                bbox=box,
                order=len(blocks),
                kind=kind,
                raw_text=item["raw_text"],
                text=text,
                text_map=item["text_map"],
                font_size=item["font_size"],
                bold=item["bold"],
                heading_confidence=detected_heading[1] if kind == "heading" else None,
                warnings=warnings,
            )
        )
    sections = assign_sections(blocks, paper.paper_id, parse_id)
    chunks = fixed_chunks(blocks, sections, parse_id, config)
    empty = [p["page"] for p in page_info if p["characters"] < 30]
    serious = []
    if empty:
        serious.append("empty_or_image_only_pages")
    if any("replacement_characters" in b.warnings for b in blocks):
        serious.append("replacement_characters")
    if not chunks:
        serious.append("no_usable_chunks")
    diagnostics = {
        "pages": page_info,
        "body_font_size": body_size,
        "empty_pages": empty,
        "serious_warnings": serious,
        "blocks": len(blocks),
        "sections": len(sections),
        "chunks": len(chunks),
        "excluded_table_blocks": sum(b.kind == "table" for b in blocks),
        "excluded_margin_blocks": sum(b.kind == "margin" for b in blocks),
        "structure_warnings": ["few_detected_headings"]
        if len(sections) < 5 and page_count > 5
        else [],
        "limitations": [
            "Column and heading detection are heuristics; inspect representative pages.",
            "Detected table cells and equation-like blocks are excluded; charts and undetected tables are not interpreted.",
        ],
    }
    return ParsedDocument(
        paper=paper,
        parse_id=parse_id,
        parser_version=config.parser_version,
        page_count=page_count,
        blocks=blocks,
        sections=sections,
        chunks=chunks,
        diagnostics=diagnostics,
    )
