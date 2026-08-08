"""Text cleanup that preserves a reversible mapping to original source offsets."""

import re

from fedresearch.schemas import TextMapRun


def clean_text(raw: str) -> tuple[str, list[TextMapRun]]:
    """Normalize whitespace and line-break hyphenation while mapping every output character to its raw offset."""
    removed = set()
    for match in re.finditer(r"(?<=[A-Za-z])-\s*\n\s*(?=[a-z])", raw):
        removed.update(range(match.start(), match.end()))
    chars, offsets = [], []
    pending_space = None
    for index, char in enumerate(raw):
        if index in removed:
            continue
        if char.isspace():
            if chars and pending_space is None:
                pending_space = index
            continue
        if pending_space is not None:
            chars.append(" ")
            offsets.append(pending_space)
            pending_space = None
        chars.append(char)
        offsets.append(index)
    runs = []
    for index, offset in enumerate(offsets):
        if runs and offset == runs[-1].raw_start + index - runs[-1].clean_start:
            runs[-1].clean_end = index + 1
        else:
            runs.append(TextMapRun(clean_start=index, clean_end=index + 1, raw_start=offset))
    return "".join(chars), runs
