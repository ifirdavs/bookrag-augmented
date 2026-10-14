"""A small curated NetworkX graph whose assertions resolve to original PDF spans."""

import json
import re
from pathlib import Path
from typing import Literal

import networkx as nx
from pydantic import Field

from fedresearch.indexing.pipeline import current_index
from fedresearch.schemas import SourceSpan
from fedresearch.settings import Settings, StrictModel
from fedresearch.storage.metadata_store import MetadataStore
from fedresearch.util import atomic_json, digest


class Entity(StrictModel):
    """A canonical name with explicit reviewed aliases, without fuzzy name merging."""

    entity_id: str = Field(pattern=r"^[a-z][a-z0-9_:-]*$")
    kind: Literal["method", "technique", "problem", "dataset"]
    label: str = Field(min_length=1)
    aliases: list[str] = Field(min_length=1)


class Relation(StrictModel):
    """One paper-specific assertion with an exact quote and original character span."""

    subject: str
    predicate: Literal["uses", "addresses", "evaluated_on"]
    object: str
    paper_id: str
    document_version: str
    span: SourceSpan
    quote: str = Field(min_length=1)


class Curation(StrictModel):
    """The assertion set reviewed by the assistant; co-occurrence alone does not establish support."""

    schema_version: Literal[1]
    review: Literal["assistant_source_review"]
    entities: list[Entity] = Field(min_length=1)
    relations: list[Relation] = Field(min_length=1)


def normalize_alias(text: str) -> str:
    """Helper to entity resolution: normalize case and punctuation without fuzzy name merging."""
    return re.sub(r"[\W_]+", " ", text.casefold()).strip()


def resolve_entities(query: str, graph: nx.MultiDiGraph, limit: int) -> list[str]:
    """Helper to graph navigation: match whole aliases longest-first so extended MNIST does not also mean MNIST."""
    remaining, matched = normalize_alias(query), []
    aliases = sorted(
        {
            (normalize_alias(alias), identifier)
            for identifier, entity in graph.nodes(data=True)
            for alias in [entity["label"], *entity["aliases"]]
        },
        key=lambda row: (-len(row[0]), row[0], row[1]),
    )
    for alias, identifier in aliases:
        pattern = r"(?<!\w)" + re.escape(alias) + r"(?!\w)"
        if re.search(pattern, remaining):
            if identifier not in matched:
                matched.append(identifier)
            remaining = re.sub(pattern, lambda match: " " * len(match.group()), remaining)
            if len(matched) == limit:
                break
    return matched


def graph_inputs(settings: Settings) -> Curation:
    """Helper to graph persistence: read the reviewed source assertions kept with the corpus."""
    return Curation.model_validate_json(
        (settings.paths.manifest.parent / "graph_curated.json").read_text()
    )


def compile_graph(curation: Curation, store: MetadataStore) -> nx.MultiDiGraph:
    """Validate aliases, relation types, exact quotes and complete supporting chunks before building edges."""
    graph = nx.MultiDiGraph()
    aliases = {}
    for entity in curation.entities:
        if entity.entity_id in graph:
            raise ValueError("Duplicate graph entity ID")
        for alias in [entity.label, *entity.aliases]:
            normalized = normalize_alias(alias)
            if not normalized or aliases.get(normalized, entity.entity_id) != entity.entity_id:
                raise ValueError(f"Empty or ambiguous graph alias: {alias}")
            aliases[normalized] = entity.entity_id
        graph.add_node(entity.entity_id, **entity.model_dump(exclude={"entity_id"}))
    for relation in curation.relations:
        if relation.subject not in graph or relation.object not in graph:
            raise ValueError("Graph relation references an unknown entity")
        target_type = {"uses": "technique", "addresses": "problem", "evaluated_on": "dataset"}
        if (
            graph.nodes[relation.subject]["kind"] != "method"
            or graph.nodes[relation.object]["kind"] != target_type[relation.predicate]
        ):
            raise ValueError("Graph relation has incompatible entity types")
        block = store.block(relation.span.block_id)
        section = store.section(block.section_id)
        if (
            block.paper_id != relation.paper_id
            or block.document_version != relation.document_version
            or relation.span.end > len(block.raw_text)
            or block.raw_text[relation.span.start : relation.span.end] != relation.quote
            or block.kind not in {"text", "caption"}
            or section.kind == "references"
        ):
            raise ValueError("Graph relation quote/version/source is invalid")
        chunk_ids = store.supporting_chunks(relation.span)
        if not chunk_ids:
            raise ValueError("Graph quote has no complete supporting chunk in this index")
        for chunk_id in chunk_ids:
            chunk = store.chunk(chunk_id)
            if (
                chunk.paper_id != relation.paper_id
                or chunk.document_version != relation.document_version
                or not any(
                    span.block_id == relation.span.block_id
                    and span.start <= relation.span.start
                    and span.end >= relation.span.end
                    for span in chunk.spans
                )
            ):
                raise ValueError(
                    "Graph supporting chunk payload does not contain the quoted source"
                )
        payload = relation.model_dump(mode="json")
        identifier = digest(payload)[:24]
        if graph.has_edge(relation.subject, relation.object, identifier):
            raise ValueError("Duplicate graph assertion")
        graph.add_edge(
            relation.subject,
            relation.object,
            key=identifier,
            **payload,
            chunk_ids=chunk_ids,
            section_id=block.section_id,
            page=block.page,
        )
    return graph


def graph_identity(curation: Curation, manifest: dict) -> dict:
    """Helper to graph compatibility: bind curated assertions to the exact source/chunk index."""
    return {
        "schema_version": 1,
        "index_id": manifest["index_id"],
        "chunk_fingerprint": manifest["chunk_fingerprint"],
        "curation_hash": digest(curation.model_dump(mode="json")),
        "extraction": "curated; no model calls",
    }


def build_graph(settings: Settings) -> dict:
    """Persist a validated evidence graph beside an existing index, without re-embedding or reparsing."""
    folder, manifest = current_index(settings)
    curation = graph_inputs(settings)
    identity = graph_identity(curation, manifest)
    with MetadataStore(folder / "metadata.sqlite") as store:
        graph = compile_graph(curation, store)
    snapshot = {
        **identity,
        "graph_id": digest(identity)[:24],
        "networkx_version": nx.__version__,
        "data": nx.node_link_data(graph, edges="edges"),
    }
    atomic_json(folder / "graph.json", snapshot)
    return {
        **identity,
        "graph_id": snapshot["graph_id"],
        "entities": graph.number_of_nodes(),
        "relations": graph.number_of_edges(),
        "papers": len({edge["paper_id"] for _, _, edge in graph.edges(data=True)}),
        "path": str(folder / "graph.json"),
        "supporting_spans": "valid",
    }


def load_graph(settings: Settings, folder: Path, manifest: dict, store: MetadataStore):
    """Load a versioned graph and revalidate every assertion against current inputs and SQLite sources."""
    path = folder / "graph.json"
    if not path.is_file():
        raise ValueError("Graph is missing; run fedresearch graph-build with the same config")
    snapshot = json.loads(path.read_text())
    curation = graph_inputs(settings)
    identity = graph_identity(curation, manifest)
    if (
        any(snapshot.get(key) != value for key, value in identity.items())
        or snapshot.get("graph_id") != digest(identity)[:24]
    ):
        raise ValueError("Graph inputs/index changed; run fedresearch graph-build again")
    expected = compile_graph(curation, store)
    if snapshot["data"] != nx.node_link_data(expected, edges="edges"):
        raise ValueError("Persisted graph differs from verified source assertions")
    graph = nx.node_link_graph(snapshot["data"], edges="edges")
    return graph, {**identity, "graph_id": snapshot["graph_id"]}
