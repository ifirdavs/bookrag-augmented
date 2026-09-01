"""Typed contracts for original-source provenance, parsed documents, evidence and cited answers."""

from typing import Literal

from pydantic import Field, model_validator

from fedresearch.settings import StrictModel


class Paper(StrictModel):
    paper_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    title: str
    year: int = Field(ge=1990, le=2100)
    source_url: str
    document_version: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    methods: list[str] = Field(default_factory=list)


class SourceSpan(StrictModel):
    """Half-open Unicode character offsets into Block.raw_text, never tokenizer offsets."""

    block_id: str
    start: int = Field(ge=0)
    end: int = Field(gt=0)

    @model_validator(mode="after")
    def ordered(self):
        """Helper to SourceSpan validation: require a nonempty forward character range."""
        if self.end <= self.start:
            raise ValueError("Source span must be nonempty")
        return self


class TextMapRun(StrictModel):
    clean_start: int
    clean_end: int
    raw_start: int


class Block(StrictModel):
    block_id: str
    paper_id: str
    document_version: str
    page: int = Field(ge=1)
    printed_page_label: str | None = None
    bbox: tuple[float, float, float, float]
    order: int
    kind: Literal["text", "heading", "caption", "table", "margin", "equation"] = "text"
    raw_text: str
    text: str
    text_map: list[TextMapRun]
    font_size: float
    bold: bool = False
    heading_confidence: float | None = Field(default=None, ge=0, le=1)
    section_id: str = ""
    warnings: list[str] = Field(default_factory=list)

    def raw_span(self, start: int, end: int) -> SourceSpan:
        """Helper to fixed_chunks: map a cleaned-text range back to original block character offsets."""
        if not 0 <= start < end <= len(self.text):
            raise ValueError("Invalid clean-text range")

        def offset(i: int) -> int:
            """Helper to raw_span: resolve one cleaned character through the compact offset map."""
            for run in self.text_map:
                if run.clean_start <= i < run.clean_end:
                    return run.raw_start + i - run.clean_start
            raise ValueError("Incomplete cleaning map")

        return SourceSpan(block_id=self.block_id, start=offset(start), end=offset(end - 1) + 1)


class Section(StrictModel):
    section_id: str
    paper_id: str
    title: str
    parent_id: str | None
    path: list[str]
    block_ids: list[str]
    confidence: float = Field(ge=0, le=1)
    kind: Literal["section", "fallback", "references"] = "section"


class Chunk(StrictModel):
    chunk_id: str
    paper_id: str
    document_version: str
    parse_id: str
    policy: Literal["fixed", "section"] = "fixed"
    text: str
    section_id: str
    section_path: list[str]
    section_ids: list[str]
    spans: list[SourceSpan]
    token_count: int
    pages: list[int]


class ParsedDocument(StrictModel):
    paper: Paper
    parse_id: str
    parser_version: str
    page_count: int
    blocks: list[Block]
    sections: list[Section]
    chunks: list[Chunk]
    diagnostics: dict


class Evidence(StrictModel):
    evidence_id: str
    chunk_id: str
    paper_id: str
    title: str
    source_url: str
    document_version: str
    parse_id: str
    section_path: list[str]
    section_paths: list[list[str]]
    pages: list[int]
    spans: list[SourceSpan]
    text: str
    token_count: int
    origin: Literal["dense", "hybrid", "structure"] = "dense"
    score: float


class Claim(StrictModel):
    text: str
    citations: list[str]


class GeneratedAnswer(StrictModel):
    sufficiency: Literal["sufficient", "partial", "insufficient"]
    claims: list[Claim]
    limitations: str


class Answer(StrictModel):
    question: str
    answer_text: str
    sufficiency: Literal["sufficient", "partial", "insufficient"]
    claims: list[Claim]
    citations: dict[str, Evidence]
    evidence: list[Evidence]
    usage: dict
    trace: dict
