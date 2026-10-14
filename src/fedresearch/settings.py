"""Validated YAML/environment settings shared by the pipeline and experiments."""

import os
from pathlib import Path
from typing import Literal

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Paths(StrictModel):
    manifest: Path = Path("data/corpus_manifest.jsonl")
    raw: Path = Path("data/raw")
    processed: Path = Path("data/processed")
    indexes: Path = Path("artifacts/indexes")
    runs: Path = Path("artifacts/runs")


class Preprocessing(StrictModel):
    parser_version: str = "pymupdf-columns-v4"
    tokenizer: str = "voyageai/voyage-4-large"
    tokenizer_revision: str = "bb931c2635a93efe400c24741363d8ff61d7bb32"
    chunk_tokens: int = Field(default=600, ge=64, le=4000)
    overlap_tokens: int = Field(default=100, ge=0)
    exclude_references: bool = True
    exclude_tables: bool = True

    @model_validator(mode="after")
    def valid_overlap(self):
        """Helper to configuration validation: keep chunk overlap smaller than the chunk window."""
        if self.overlap_tokens >= self.chunk_tokens:
            raise ValueError("overlap_tokens must be smaller than chunk_tokens")
        return self


class Embedding(StrictModel):
    model: str = "voyage-4-large"
    dimensions: int = Field(default=2048, gt=0)
    batch_size: int = Field(default=32, ge=1, le=128)
    timeout_seconds: float = Field(default=60, gt=0)
    max_retries: int = Field(default=2, ge=0, le=5)


class Indexing(StrictModel):
    chunk_policy: Literal["fixed", "section"] = "fixed"


class Generation(StrictModel):
    model: str = "claude-haiku-5-5"
    max_output_tokens: int = Field(default=2500, gt=0)
    timeout_seconds: float = Field(default=90, gt=0)
    max_retries: int = Field(default=2, ge=0, le=5)


class Retrieval(StrictModel):
    mode: Literal["dense", "hybrid", "structure", "graph"] = "dense"
    candidate_limit: int = Field(default=20, ge=1, le=100)
    rrf_constant: int = Field(default=60, ge=1)
    top_k: int = Field(default=5, ge=1, le=20)
    evidence_tokens: int = Field(default=4000, ge=1, le=32000)
    max_query_tokens: int = Field(default=1024, ge=1, le=8191)
    routing: Literal["disabled"] = "disabled"
    expansion_seeds: int = Field(default=3, ge=1, le=10)
    expansion_per_seed: int = Field(default=2, ge=1, le=3)
    expansion_limit: int = Field(default=6, ge=1, le=20)
    graph_entities: int = Field(default=4, ge=1, le=10)
    graph_edges: int = Field(default=12, ge=1, le=40)
    graph_limit: int = Field(default=6, ge=1, le=20)


class Reranking(StrictModel):
    enabled: bool = False
    model: str = "rerank-3"
    timeout_seconds: float = Field(default=60, gt=0)
    max_retries: int = Field(default=2, ge=0, le=5)


class Evaluation(StrictModel):
    k: int = Field(default=5, ge=1, le=20)
    minimum_span_overlap: float = Field(default=0.5, gt=0, le=1)


class Settings(StrictModel):
    paths: Paths = Field(default_factory=Paths)
    preprocessing: Preprocessing = Field(default_factory=Preprocessing)
    embedding: Embedding = Field(default_factory=Embedding)
    indexing: Indexing = Field(default_factory=Indexing)
    generation: Generation = Field(default_factory=Generation)
    retrieval: Retrieval = Field(default_factory=Retrieval)
    reranking: Reranking = Field(default_factory=Reranking)
    evaluation: Evaluation = Field(default_factory=Evaluation)

    @model_validator(mode="after")
    def budgets(self):
        """Helper to configuration validation: enforce final-evidence, hierarchy and graph budgets."""
        if self.retrieval.top_k > self.retrieval.candidate_limit:
            raise ValueError("top_k must not exceed candidate_limit")
        if self.retrieval.mode in {"structure", "graph"}:
            if self.indexing.chunk_policy != "section":
                raise ValueError("Structure retrieval requires section chunks")
            if self.retrieval.expansion_limit >= self.retrieval.candidate_limit:
                raise ValueError("expansion_limit must be smaller than candidate_limit")
        if (
            self.retrieval.mode == "graph"
            and self.retrieval.graph_limit >= self.retrieval.candidate_limit
        ):
            raise ValueError("graph_limit must be smaller than candidate_limit")
        return self


def load_settings(path: Path = Path("configs/default.yaml")) -> Settings:
    """Load default YAML, merge experiment overrides, apply model environment overrides and resolve paths."""
    path = path.resolve()
    config_dir = path.parent.parent if path.parent.name == "experiments" else path.parent
    default = config_dir / "default.yaml"
    data = yaml.safe_load(default.read_text()) or {}
    if path != default:
        for section, fields in (yaml.safe_load(path.read_text()) or {}).items():
            if not isinstance(fields, dict):
                raise ValueError(f"Config section '{section}' must contain named fields")
            data[section] = {**data.get(section, {}), **fields}

    root = config_dir.parent
    load_dotenv(root / ".env", override=False)
    for group, field, env in [
        ("generation", "model", "FEDRESEARCH_GENERATION_MODEL"),
        ("embedding", "model", "FEDRESEARCH_EMBEDDING_MODEL"),
    ]:
        if os.getenv(env):
            data.setdefault(group, {})[field] = os.environ[env]
    settings = Settings.model_validate(data)
    for field in Paths.model_fields:
        value = getattr(settings.paths, field)
        setattr(settings.paths, field, (root / value).resolve())
    return settings
