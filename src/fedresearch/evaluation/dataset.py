"""Source-based benchmark contracts, annotation checks and held-out freeze enforcement."""

import json
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from fedresearch.schemas import SourceSpan
from fedresearch.settings import StrictModel
from fedresearch.storage.metadata_store import MetadataStore
from fedresearch.util import file_sha256, read_jsonl


class GoldPassage(StrictModel):
    paper_id: str
    document_version: str
    parse_id: str
    page: int = Field(ge=1)
    span: SourceSpan
    quote: str


class EvidenceGroup(StrictModel):
    group_id: str
    required_fact: str
    alternatives: list[GoldPassage] = Field(min_length=1)


class BenchmarkQuestion(StrictModel):
    question_id: str
    split: Literal["dev", "test"]
    kind: Literal["paper_specific", "cross_section", "comparison", "synthesis", "unanswerable"]
    question: str
    answerable: bool
    expected_points: list[str]
    evidence_groups: list[EvidenceGroup]
    comparison_constraints: list[str] = Field(default_factory=list)
    annotation_status: Literal["draft", "source_verified", "human_reviewed"]

    @model_validator(mode="after")
    def answerability(self):
        """Helper to benchmark validation: require consistent answerability and unique evidence groups."""
        if self.answerable != bool(self.evidence_groups) or self.answerable != bool(
            self.expected_points
        ):
            raise ValueError(
                "Answerable questions require expected points and evidence groups; unanswerable questions require neither"
            )
        group_ids = [g.group_id for g in self.evidence_groups]
        if len(set(group_ids)) != len(group_ids):
            raise ValueError("Duplicate evidence groups")
        return self


def load_dataset(path: Path, split: str) -> list[BenchmarkQuestion]:
    """Load a benchmark split and validate its questions, IDs and split membership."""
    questions = [BenchmarkQuestion.model_validate(row) for row in read_jsonl(path)]
    if not questions or len({q.question_id for q in questions}) != len(questions):
        raise ValueError("Empty benchmark or duplicate question IDs")
    if any(q.split != split for q in questions):
        raise ValueError("Dataset contains the wrong split")
    return questions


def verify_question(question: BenchmarkQuestion, store: MetadataStore):
    """Helper to benchmark validation: resolve every gold quote and span to its original source."""
    for group in question.evidence_groups:
        for passage in group.alternatives:
            block = store.block(passage.span.block_id)
            if (
                block.paper_id != passage.paper_id
                or block.document_version != passage.document_version
                or block.page != passage.page
            ):
                raise ValueError(f"{question.question_id}: gold passage provenance mismatch")
            if f":{passage.parse_id}:" not in block.block_id:
                raise ValueError(f"{question.question_id}: gold parse version mismatch")
            if block.raw_text[passage.span.start : passage.span.end] != passage.quote:
                raise ValueError(f"{question.question_id}: gold quote/span mismatch")


def require_frozen(path: Path):
    """Helper to held-out evaluation: reject test labels whose recorded freeze hash is missing or stale."""
    freeze = path.parent / "frozen.json"
    if not freeze.exists() or json.loads(freeze.read_text()).get(path.name) != file_sha256(path):
        raise ValueError(
            "Held-out labels are not frozen. Review the annotations, then run benchmark freeze."
        )
