# FedResearch

**A structure-aware RAG assistant for federated-learning research papers.**

Status: **Phases 0–5 complete; final evaluation and delivery remain** (2026-10-26). The 40-paper corpus has 1,158 fixed chunks and a separate index of 1,514 section chunks with unchanged canonical source IDs. B3 improves the five-question dev diagnostics over B2, but optional reranking reduces its final coverage (5/5 → 3/5). Experimental modes stay explicit; defaults remain dense-20 with reranking off. All 81 offline tests pass. See [graph results](reports/graph.md), [baseline results](reports/evaluation.md), [hybrid results](reports/hybrid_development.md), [structure report](reports/structure.md) and [phase status](reports/phase_status.md).

FedResearch will answer technical questions using a curated PDF corpus, retrieve supporting passages, and cite the paper, section, and PDF page. It will combine corpus-level search with document hierarchy and a small evidence-linked knowledge graph inspired by BookRAG.

## 1. Project goal

Build and evaluate a research assistant that can:

- Explain a method using passages from its original paper.
- Connect a method's description, assumptions, and experimental evaluation across sections.
- Compare methods across papers, with evidence from each paper.
- Summarize approaches represented in the indexed corpus.
- State when the corpus does not contain sufficient evidence.

Example questions:

1. How does SCAFFOLD address client drift, and where is its effectiveness evaluated?
2. How do FedProx and SCAFFOLD differ in their treatment of statistical heterogeneity?
3. Which approaches in this corpus address non-IID client data, and what limitations do their authors describe?

These examples become benchmark questions only after their answerability and source passages have been checked against the selected PDFs.

**Research question:** Does preserving document structure improve evidence retrieval and grounded question answering over federated-learning papers, compared with conventional chunk-based RAG?

**Secondary question:** Does a small knowledge graph improve cross-section and cross-paper evidence coverage beyond hybrid, structure-aware retrieval?

Improvement is a hypothesis to test. An honest negative result is a valid project outcome.

## 2. Agreed project scope

Build a simple, grounded federated-learning research assistant and measure whether hybrid and BookRAG-inspired structure improve evidence retrieval and answer relevance. The user's agreed scope replaces the earlier course checklist. There is no assignment-rubric gate, video deliverable, mandatory deadline, MCP implementation, or quota of failure cases.

| Area | Deliverable |
| --- | --- |
| Corpus | 40 papers: preserve the existing 20 and add 20 selected papers covering surveys, privacy, systems and applications |
| Baseline | Fixed-size chunks, dense retrieval, original-source cited answers |
| Enhanced retrieval | BM25 plus dense search with RRF; section-aware chunks and bounded hierarchy expansion |
| Graph | A small evidence-linked graph where entity navigation demonstrably helps |
| Models | Claude Haiku 5.5 generation; Voyage 4 Large embeddings at 2048 dimensions |
| Evaluation | 20 annotated questions: 5 development / 15 held-out; at least 10 useful comparison questions |
| Documentation | Actual setup, architecture, measured results, limitations and any observed failures |

Initial scope: English, text-based research PDFs; reliable prose and source citations. Tables enter only when their headers, cells, and context can be extracted faithfully. Unreliable tables are flagged. Equation interpretation, chart-image reasoning, OCR-heavy documents, exhaustive literature reviews, and a complete BookRAG reproduction remain extensions.

Keep the same corpus, parser, embedding model, generator, test questions and evidence budget for controlled comparisons. Use graph navigation only when its measured benefit justifies its complexity. Document failures that occur in real runs; never introduce failures to satisfy a reporting count. Negative questions evaluate successful abstention when the corpus lacks evidence.

The original 20 papers cover methods, optimization/heterogeneity, personalization and fairness. The selected additions broaden communication efficiency, secure aggregation, privacy attacks, systems, surveys and applications. The 40-paper corpus must be fixed before comparing retrieval modes; historical 20-paper results are a separate corpus version.

## 3. Relationship to BookRAG

BookRAG introduces a BookIndex containing a document hierarchy, an entity graph, and mappings from entities to hierarchy nodes. FedResearch adapts these ideas to a collection of independent research papers, adding a corpus-level search layer.

This is a **BookRAG-inspired implementation**, not a reproduction or a claim to reproduce its benchmark results. We will implement our own pipeline and cite the paper and any code consulted.

At the architectural level, BookRAG’s central index contains:

- A document tree.
- An entity–relation graph.
- Links connecting graph entities to document nodes.

Our **section trees**, **knowledge graph**, and **evidence links** adapt that central idea. However, the original also specifies **query classification**, **retrieval operators**, **graph-based scoring**, **Skyline selection**, and **gradient-based entity resolution**. We are simplifying those algorithms and adding BM25/vector search across papers.

The original BookRAG also uses reranking: its text-ranking operator scores retrieved blocks for query relevance, while Skyline selection combines text relevance with graph importance. Appendix A.2 specifies Qwen3-Reranker-4B for its experiments. Reranking also supports entity resolution during indexing. Our initial adaptation uses a configurable query-time relevance reranker; reproducing Skyline selection or model-based entity resolution is outside the minimum scope.

References: [BookRAG paper](https://arxiv.org/abs/2512.03413), [author repository linked in our earlier discussion](https://github.com/sam234990/BookRAG). Repository availability and implementation details should be checked before relying on its code.

## 4. Architecture

### Offline: prepare documents and build indexes

```mermaid
flowchart TD
    A["PDFs and corpus manifest"] --> B["Parse and validate layout"]
    B --> C["Canonical blocks with provenance"]
    C --> D["Fixed and section-aware chunks"]
    C --> E["Paper and section hierarchy"]
    C --> F["Entity and relation extraction"]
    D --> G["Vector and BM25 indexes"]
    E --> H["Metadata and hierarchy store"]
    F --> I["Evidence-linked graph"]
    E --> I
```

### Online: collect evidence and answer

```mermaid
flowchart TD
    A["Question and optional paper/section filters"] --> B["Shared RetrievalService"]
    B --> C["Dense search"]
    B --> D["BM25 in enhanced modes"]
    C --> E["Dense ranking or RRF fusion"]
    D --> E
    E --> F["Optional bounded hierarchy and graph expansion"]
    F --> G["Source deduplication and optional reranking"]
    G --> H["Pack evidence within item/token budgets"]
    H --> I["Claude generates cited claims"]
    I --> J["Validate citation IDs and source provenance"]
    J --> K["Answer, partial answer or insufficient evidence"]
```

The answer and evaluation workflows use the same retrieval service. Configuration selects dense, hybrid, structural or graph retrieval, and Claude answers from the packed original source passages.

## 5. Python file guide

This describes the files that exist now. Each Python module and function has a docstring. Small supporting functions start with `Helper to ...:`; the main pipeline functions describe the operation they perform. Paths in this table are relative to `src/fedresearch/`.

| Python file | What it does | Why it is needed |
| --- | --- | --- |
| [`cli.py`](src/fedresearch/cli.py) | Defines commands and prints their results | Provides one entry point while keeping the actual work in services |
| [`settings.py`](src/fedresearch/settings.py) | Loads YAML, experiment overrides and environment settings | Keeps model choices and budgets consistent across runs |
| [`tokenization.py`](src/fedresearch/tokenization.py) | Loads and caches the pinned official Voyage tokenizer locally | Gives chunking, evidence counts and query limits one consistent token definition |
| [`graph.py`](src/fedresearch/graph.py) | Defines curated entities/relations, validates source quotes and saves/loads NetworkX JSON | Keeps graph assertions versioned and tied to complete original evidence |
| [`schemas.py`](src/fedresearch/schemas.py) | Defines papers, blocks, chunks, evidence and answers | Preserves typed source identities and citation contracts |
| [`util.py`](src/fedresearch/util.py) | Hashes identities/files and reads/writes JSON | Shares the few persistence helpers used by several stages |
| [`corpus/manifest.py`](src/fedresearch/corpus/manifest.py) | Reads metadata and checks the existing local PDFs | Pins the exact papers/versions being processed |
| [`preprocessing/pdf_parser.py`](src/fedresearch/preprocessing/pdf_parser.py) | Extracts text/layout, fixes column order and records diagnostics | Turns PDFs into canonical evidence with page coordinates |
| [`preprocessing/cleaning.py`](src/fedresearch/preprocessing/cleaning.py) | Cleans whitespace/hyphenation with a raw-offset map | Lets cleaned chunks still cite the original extracted text |
| [`preprocessing/sections.py`](src/fedresearch/preprocessing/sections.py) | Detects headings and assigns section/parent links | Provides section citations and the hierarchy used in later retrieval |
| [`preprocessing/chunking.py`](src/fedresearch/preprocessing/chunking.py) | Creates fixed or section-bounded windows using the same tokenizer/source spans | Compares chunk policies while preserving canonical source IDs |
| [`preprocessing/validation.py`](src/fedresearch/preprocessing/validation.py) | Checks source mappings, page ranges and serious warnings | Prevents invalid parses from silently entering an index |
| [`indexing/pipeline.py`](src/fedresearch/indexing/pipeline.py) | Runs preprocessing/index builds and validates saved versions | Coordinates stages and activates only complete compatible indexes |
| [`indexing/embeddings.py`](src/fedresearch/indexing/embeddings.py) | Caches vectors and embeds missing chunks in batches | Avoids repeating successful API calls after a rebuild/interruption |
| [`indexing/vector_index.py`](src/fedresearch/indexing/vector_index.py) | Stores/searches vectors in persistent Chroma | Supplies dense candidate retrieval and metadata filters |
| [`indexing/lexical_index.py`](src/fedresearch/indexing/lexical_index.py) | Builds/searches a persistent SQLite FTS5 BM25 index over the same chunks | Adds word matching without another dependency or model call |
| [`storage/metadata_store.py`](src/fedresearch/storage/metadata_store.py) | Stores paper/section/block/chunk records in SQLite | Resolves vector hits and citations back to original sources |
| [`retrieval/service.py`](src/fedresearch/retrieval/service.py) | Applies filters, retrieves, deduplicates, optionally reranks and packs evidence | Gives answers and evaluation one retrieval implementation |
| [`retrieval/evidence.py`](src/fedresearch/retrieval/evidence.py) | Removes source overlap and constructs evidence under the final budget | Prevents duplicate passages and retains citation-ready provenance |
| [`retrieval/fusion.py`](src/fedresearch/retrieval/fusion.py) | Combines dense/BM25 ranks with RRF and stable ties | Merges searches without mixing their different score scales |
| [`retrieval/hierarchy.py`](src/fedresearch/retrieval/hierarchy.py) | Selects bounded adjacent/parent/child context and records its source/reason | Tests section navigation independently of chunking and reranking |
| [`retrieval/graph.py`](src/fedresearch/retrieval/graph.py) | Resolves query aliases, follows one-hop relations and merges bounded support chunks | Tests graph navigation while sending original source text to the answer model |
| [`retrieval/reranking.py`](src/fedresearch/retrieval/reranking.py) | Calls Atlas `rerank-3` and returns validated indices/scores/usage | Adds optional query-passage ranking without changing source text |
| [`llm/client.py`](src/fedresearch/llm/client.py) | Wraps the official Claude/Voyage SDKs and records usage | Isolates provider requests, vector checks and sanitized errors |
| [`llm/answering.py`](src/fedresearch/llm/answering.py) | Retrieves evidence, generates structured claims and validates citations | Produces grounded answers through one fixed pipeline |
| [`evaluation/dataset.py`](src/fedresearch/evaluation/dataset.py) | Loads question labels, verifies source quotes and enforces the held-out freeze | Keeps benchmark labels independent of chunking/retrieval |
| [`evaluation/retrieval_metrics.py`](src/fedresearch/evaluation/retrieval_metrics.py) | Computes span-based precision/recall/coverage diagnostics | Measures retrieval against the same original evidence across experiments |
| [`evaluation/runner.py`](src/fedresearch/evaluation/runner.py) | Runs questions, optionally replays saved dense/hybrid pools, and saves candidate/final metrics, answers, timing and failures | Makes comparisons inspectable and isolates reranking effects |
| `__init__.py` files in each package | Mark Python packages; the root also defines the version | Support package imports; they contain no pipeline logic |

The answer prompt lives in `src/fedresearch/llm/prompts/answer.md`. Settings live in `configs/default.yaml`. B0/B0-R retain their original 20-candidate settings. `b1_hybrid.yaml` and `b1_hybrid_rerank.yaml` select hybrid retrieval with a 40-candidate cap; `b0_dense_40.yaml` provides a matching dense control. `b2a_section.yaml` uses section chunks without expansion; `b2_structure.yaml` adds bounded hierarchy expansion over the same index. Phase 5 adds `graph.py`, `retrieval/graph.py`, curated source data and `b3_graph.yaml`/`b3_graph_rerank.yaml`.

Tests are separate from application code:

| Test file | Purpose |
| --- | --- |
| `tests/test_pipeline.py` | Generated-PDF integration checks for parsing/provenance, index persistence, filters, cache, reranking and citations |
| `tests/test_embeddings_api.py` | Voyage embedding request/response handling, document/query roles and vector validation |
| `tests/test_generation_api.py` | Claude structured responses, truncation/refusal handling and sanitized errors |
| `tests/test_reranking_api.py` | Atlas rerank-3 request/response handling, index validation and empty-scope behavior |
| `tests/test_settings.py` | Default/experiment YAML merging and path resolution |
| `tests/test_hybrid.py` | BM25 persistence, exact terms, safe queries, filters and deterministic RRF arithmetic |
| `tests/test_structure.py` | Section source coverage, token limits, heading-only exclusion and bounded parent/child/adjacent navigation |
| `tests/test_graph.py` | Source assertion validation, graph reload/tampering, alias overlap, bounded scopes and exact graph/reranking replays |
| `tests/test_tokenization.py` | Voyage chunk limits, Unicode coverage, exact source spans and no silent tokenizer truncation/padding |

For a quick review, start with `cli.py` → `llm/answering.py` → `retrieval/service.py` → `retrieval/evidence.py`. Read `retrieval/reranking.py` for the optional ranking stage. `indexing/pipeline.py` is the build path; the PDF layout details are isolated under `preprocessing/`.

### Temporary working notes in docs/

These Markdown files are development notes, not runtime dependencies. The README is the main project guide.

| File | Why it is kept during implementation | Final destination |
| --- | --- | --- |
| `docs/requirements.md` | Records the agreed scope so removed course/video/MCP requirements do not return | README scope |
| `docs/decisions.md` | Records implementation choices and constraints between phases | README architecture/setup |
| `docs/corpus.md` | Lists the pinned papers and parsing details | README corpus summary and preprocessing report |
| `docs/models.md` | Holds current provider setup, limits and live-check notes | README setup and final evaluation report |
| `docs/evaluation.md` | Defines source annotations, the held-out freeze and scoring rules before experiments | README evaluation protocol and final report |

**Delivery cleanup:** merge the useful permanent content into the README and `reports/`, update every link, and remove `docs/`. Do not leave duplicate setup/scope documents in the completed project.

## 6. Proposed technology choices

Phase 0–4 local dependencies are locked in `uv.lock` and tested with Python 3.13.1. Hybrid and structural search use Python's existing SQLite FTS5 support, with no added package. Live model access and baseline measurements are recorded; the 40-paper index and all four B0/B0-R development/test runs are verified. Hybrid's matched dense-40/B1 and exact-pool B1/B1-R development comparisons and targeted assistant review are complete. Independent human grading is not claimed.

| Component | Initial choice | Rationale |
| --- | --- | --- |
| Language and packaging | Python, `src` layout, `uv`, `pyproject.toml` | One package with reproducible dependencies |
| Contracts and settings | Pydantic and YAML | Validate stage inputs and configuration |
| PDF parsing | PyMuPDF first; evaluate Docling if layout quality fails | Preserve page and bounding-box information |
| Vector store | Local persistent Chroma | Small corpus, straightforward metadata filtering |
| Keyword search | SQLite FTS5 BM25, persisted alongside Chroma | Match method names, acronyms and technical terms using the same fixed source chunks |
| Fusion | Reciprocal Rank Fusion | Combine rankings without treating unlike scores as equivalent |
| Reranking | MongoDB Atlas `rerank-3`, switchable and verified with a small live call | Rescore a bounded candidate pool against the query; evaluate separately from RRF |
| Metadata and hierarchy | SQLite | Traceable paper, section, block, and chunk lookups |
| Graph | NetworkX with JSON persistence | Small graph without another database service |
| Graph–Tree Links | Graph assertion spans + existing SQLite `chunk_spans` index | Resolve relations to complete original chunks, sections and pages without another mapping database |
| Answer generation | Claude Haiku 5.5 through the Claude API | Use the official Anthropic SDK and structured answers |
| Embeddings | Voyage 4 Large, 2048-dimensional float vectors | Use the same model for documents, queries and controlled comparisons |
| First interface | CLI | Build the research pipeline before optional UI work |
| Verification | pytest for consequential behavior | Protect provenance, retrieval, and integration boundaries |

Generation uses `claude-haiku-5-5` with `ANTHROPIC_API_KEY` from the ignored `.env`. The official SDK handles requests and retries; Pydantic validates the structured answer. Embeddings use `voyage-4-large` through the official Voyage SDK with `VOYAGE_API_KEY`. Documents and questions use their respective retrieval input types, with silent truncation disabled. See [model setup](docs/models.md).

Reranking uses MongoDB Atlas `rerank-3` through the same `VOYAGE_API_KEY` and official SDK as embeddings. It is disabled in B0 and the core experiment ladder so its effect can be measured separately. It scores the same bounded, deduplicated candidate pool before final evidence packing. Original ranks/scores, reranked ranks/scores, usage and latency are recorded; a provider error fails the run rather than silently skipping reranking. BookRAG's Qwen3-Reranker-4B remains a research reference.

PyMuPDF's documentation warns that extracted PDF text may differ from visual reading order; multi-column layouts require inspection. We will inspect three representative FL papers before committing to a parser. A layout parser fallback is a response to observed failure, not a second default pipeline.

Primary documentation: [PyMuPDF text extraction](https://pymupdf.readthedocs.io/en/latest/recipes-text.html), [Claude structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs), [Chroma documentation](https://docs.trychroma.com/).

### Storage options for Production

The following storage choices are planned for the initial project. **Production alternatives** are migration options, not additional dependencies required for the course deliverable.

| Data | Initial project storage | Production option |
| --- | --- | --- |
| **Hierarchical tree** and source metadata | SQLite tables containing paper/section/block IDs, parent links, document order, versions, and provenance | PostgreSQL is preferred for a shared service with concurrent writers and centralized database operations; use parent-ID relationships and recursive queries |
| **BM25 retrieval data** | `bm25.sqlite` per index, containing an FTS5 index and source/tokenizer/SQLite-version metadata | Elasticsearch manages text analysis, persistent lexical indexes, scoring statistics, and BM25 retrieval |
| **Knowledge graph** | NetworkX in memory; nodes, edges, graph metadata, and attributes serialized into versioned JSON | Neo4j is suitable when persistent graph traversal and concurrent graph access become important |
| **Graph–Tree Links** | Assertion block spans/section IDs in graph JSON, resolved through existing SQLite `chunk_spans` | PostgreSQL association tables when hierarchy and graph use separate stores; Neo4j relationships when lightweight document nodes are represented alongside graph entities |

**Hierarchical tree.** SQLite is the persistent source of truth for the initial tree, not merely a cache of an in-memory structure. Store parent IDs and sibling/document order so sections, subsections, paragraphs, tables, and figures can be reconstructed and navigated. PostgreSQL preserves this relational design and supports recursive queries for descendant/ancestor lookup. SQLite can also serve small production workloads; the preference for PostgreSQL applies to a shared service with heavier concurrency and operational requirements. If document nodes are moved into Neo4j, hierarchy can instead be represented through `CONTAINS` relationships.

**BM25.** `fedresearch index` builds `artifacts/indexes/<index-id>/bm25.sqlite` from the same chunk IDs/text as Chroma, including when dense vectors are reused. FTS5 persists its own term index; no custom BM25 scorer or extra package is needed. Its metadata pins the dense index ID, chunk fingerprint, SQLite version, `unicode61 remove_diacritics 0` analyzer and built-in BM25 parameters (`k1=1.2`, `b=0.75`). A mismatch requires rebuilding through the same index command. Query words are quoted and OR-connected; FTS5 handles case-insensitive word matching for documents and queries. There is no stemming, synonym expansion or title boosting. BM25 uses words; chunk/evidence budgets still use the official Voyage tokenizer. Filters apply before each search's result cap, with corpus-wide BM25 statistics. Exposed BM25 scores negate SQLite's native score so larger means better. See [SQLite FTS5](https://sqlite.org/fts5.html). An Elasticsearch migration would need evaluation because its analyzer/scoring can change rankings.

**Knowledge graph.** Persist the NetworkX graph using an explicit, versioned node-link JSON schema, including directed/multigraph flags, stable node IDs, relation IDs, edge keys where needed, and JSON-compatible attributes. Preserve multiple assertions and their paper-specific supporting evidence rather than overwriting edges between shared entities. Reload the JSON into NetworkX for bounded traversal. Neo4j is a suitable production property-graph database; choosing it depends on actual traversal, update, and concurrency needs.

**NetworkX JSON to Neo4j.** The serialized JSON data can be imported to Neo4j, but NetworkX node-link JSON is not an automatic native Neo4j graph-import format. A mapping step must create graph nodes from the JSON node records, then create typed relationships by resolving each edge's source and target IDs. A Python importer can read the JSON and write batches through the Neo4j driver; alternatively, where APOC is available, `apoc.load.json` can parse the JSON and Cypher can construct the graph. `apoc.import.json` expects APOC's graph-export format, so it requires conversion rather than direct use on arbitrary NetworkX JSON. Map node types to labels and relation types to approved relationship types, preserve application IDs, direction, relation identity, and provenance, and flatten nested attributes or model them as separate records to fit Neo4j property types. Verify node/edge counts and source links after migration. This is a documented migration route; no importer is implemented yet.

**Neo4j code tradeoff.** Docker Compose starts the server, but the application still needs a Neo4j driver/credentials, node and relation imports/upserts, constraints, bounded Cypher traversal queries, and mapping of returned evidence IDs back to SQLite sources. These replace the NetworkX JSON save/load and in-process traversal implementation. For the agreed 40-paper scope, NetworkX remains the simpler planned graph store. If Neo4j is selected in Phase 5, implement one store rather than maintaining two. See [Neo4j driver queries](https://neo4j.com/docs/python-manual/current/query-simple/).

**Graph–Tree Links.** Each reviewed assertion retains its original block span, paper/version, section and page. The existing indexed SQLite `chunk_spans` table finds chunks containing the entire quote; those chunk IDs are stored and revalidated in the graph snapshot. Entity-to-document associations follow the incident assertions. This reuses the source store instead of adding duplicate entity-link tables. A mention alone is not treated as a supported relation. Export/rebuild requires matching graph curation and source/index versions.

In production with PostgreSQL and Neo4j kept separate, store these associations in PostgreSQL and use stable application IDs to resolve Neo4j entities; validate cross-store references in the ingestion/application layer because database foreign keys cannot enforce them across services. If document nodes are also represented in Neo4j, model entity-to-document links as `EVIDENCED_IN` relationships, retaining paper/version/block IDs that resolve to the original content. A lightweight document node may act as a reference to PostgreSQL content; copying all PDF text into Neo4j is not required. Relationship evidence can use explicit assertion/evidence nodes when multiple source passages must be represented.

Storage references: [PostgreSQL recursive queries](https://www.postgresql.org/docs/current/queries-with.html), [Elasticsearch index storage](https://www.elastic.co/docs/manage-data/data-store/index-basics), [Elasticsearch BM25 similarity](https://www.elastic.co/docs/reference/elasticsearch/index-settings/similarity), [NetworkX node-link JSON](https://networkx.org/documentation/stable/reference/readwrite/generated/networkx.readwrite.json_graph.node_link_data.html), [Neo4j property-graph concepts](https://neo4j.com/docs/getting-started/appendix/graphdb-concepts/), [Neo4j APOC JSON loading and import](https://neo4j.com/docs/apoc/current/import/load-json/).

## 7. Data contracts and provenance

Parsing/retrieval/answer contracts live in `schemas.py`; `Entity`, `Relation` and the curated input contract live in `graph.py`. Graph-to-tree links are source-span attributes resolved through SQLite, without a separate `GraphTreeLink` class.

| Record | Essential fields |
| --- | --- |
| `Paper` | `paper_id`, title, year, source URL, document version, PDF checksum, method names |
| `Block` | `block_id`, `paper_id`, document version, PDF page, bounding box, type, text, parse warnings |
| `Section` | `section_id`, `paper_id`, title, parent ID, ordered block IDs, detection confidence |
| `Chunk` | `chunk_id`, policy, text, section ID/path, source block spans, token count |
| `Entity` | `entity_id`, kind, canonical label, explicit aliases |
| `Relation` | subject, predicate, object, paper/version, raw source span, exact quote; the curated set records assistant source review |
| Graph-to-tree link | Assertion attributes retain section/page, block span and complete supporting chunk IDs; SQLite resolves original text |
| `Evidence` | evidence ID, paper, section, pages, source spans, text, retrieval origin and score, optional rerank score/rank |
| `Answer` | answer text, citation-to-evidence map, evidence sufficiency, usage and execution trace |

IDs are stable for the same document version and parser/configuration version. A different PDF or incompatible parse creates a new version and invalidates affected indexes and benchmark mappings.

Run IDs are random UUIDv4 values (`uuid4().hex`). Chunk IDs are reproducible: `paper_id:parse_id:cNNNNN:text_hash` for fixed chunks, or `scNNNNN` for section chunks. The ordinal starts at zero within that paper's chunk policy; the final eight characters hash the chunk text. The parse ID hashes the PDF checksum, parser/config and PyMuPDF version. Reranking keeps chunk IDs unchanged; `E1`–`E5` are citation labels assigned within each answer.

Keep a trace from every chunk and relation back to original PDF content. Cleaning must retain a mapping to original block spans. Store printed page labels separately if available; user citations use **1-based PDF page numbers** as the reliable default.

Missing or uncertain headings get an explicit fallback section. Unsupported table content, failed pages, and low-confidence structure are visible in parse diagnostics. Never silently invent document hierarchy.

## 8. Retrieval design

1. **Paper scope:** Search all corpus chunks by default. Apply explicit paper/year/method filters only when requested. Optional later title/method discovery must preserve corpus-wide fallback.
2. **Candidate retrieval:** Search dense and BM25 indexes; fuse ranked lists with RRF in enhanced modes.
3. **Structure expansion:** Follow source section links to relevant neighboring blocks or bounded parent/child content. Avoid adding whole papers or large sections without regard to the context budget.
4. **Graph expansion:** Resolve aliases, traverse a small number of evidence-backed relations, and retrieve their original supporting blocks. The graph never substitutes for the original text.
5. **Merge and deduplicate:** Merge retrieval and expansion candidates, deduplicate overlapping source spans, and apply a bounded candidate cap. Retain original scores, expansion reasons, and provenance.
6. **Optional reranking:** Score candidate passages against the question and reorder them before final evidence selection. Keep the text and source IDs intact. RRF combines existing rankings; reranking evaluates query-passage relevance using a separate model. A reranker cannot recover evidence missing from its candidate pool.
7. **Evidence packing:** Select from the resulting ranking, preserve paper diversity for comparisons, and enforce a shared token budget. Record any diversity constraint separately from relevance scores.
8. **Answering:** Generate claims only from supplied evidence and cite their sources. If required evidence is missing, provide a qualified partial answer or an insufficient-evidence response.

Current B0 settings: 600-token chunks with 100-token overlap, up to 20 Chroma dense candidates, source-overlap deduplication, and up to 5 final evidence items within 4,000 evidence-text tokens. Voyage 4 Large embeds documents and queries at 2048 dimensions. B0-R passes every deduplicated candidate's **text**, together with the query, to `rerank-3`, receives all of them reordered, and applies the same final item/token limits. Chunk IDs resolve the text locally; dense scores are kept for the trace and are not inputs to the reranking API. B0 selects evidence using the dense ranking.

**Deduplication:** after fusion/expansion and before reranking, keep the first chunk in the current order and drop a later chunk if it shares at least 50% of the smaller chunk's original source-character spans with any kept chunk. Only matching source block IDs count. This removes overlapping windows, not semantically similar text from different papers. Fusion/expansion already merge identical chunk IDs. The trace records dropped IDs and `deduplicated_candidates`.

**Phase 3 mental model:** dense search finds similar meaning; BM25 finds matching words; RRF combines their ranked lists. B1 takes up to 40 hits from each, adds `1 / (60 + rank)` for each appearance, keeps the best 40 (ties by chunk ID), removes source overlap, then selects up to five chunks within 4,000 Voyage tokens. B1-R inserts `rerank-3` after deduplication and before that final selection. Raw dense/BM25 scores are retained for inspection, not added together. An empty result list contributes nothing; search/provider errors fail explicitly. The formula follows the [original RRF paper](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf).

Chunk sizes, evidence-text counts and the 1,024-token query limit use the official `voyageai/voyage-4-large` tokenizer, pinned to revision `bb931c2635a93efe400c24741363d8ff61d7bb32`. It runs locally through Hugging Face `tokenizers`; the first use downloads approximately 7 MB into the standard Hugging Face cache (`HF_HOME` can relocate it). No embedding API request or API key is needed for tokenization. Unicode character offsets preserve original-source spans; boundary adjustments can slightly reduce overlap. The 4,000-token budget counts passage text, excluding citation labels and prompt formatting. It is not a Claude context or billing-token count; actual embedding, reranking and generation usage comes from the respective APIs. [Voyage tokenization](https://www.mongodb.com/docs/voyageai/tutorials/tokenization/)

The shared reranking adapter follows structural/graph expansion when enabled. Defaults remain dense retrieval and `reranking.enabled: false`; `reranking.model` is `rerank-3`. `retrieval.mode` selects `dense`, `hybrid`, `structure` or `graph`, `candidate_limit` caps each search and the merged pool, and `rrf_constant` defaults to 60. B0/B0-R use 20; B1/B1-R/B2a/B2/B3/B3-R use 40. Final item/token budgets remain unchanged. Silent truncation is disabled; provider failures are recorded without falling back to a different method.

## 9. Knowledge graph

**Mental model:** resolve a named entity, follow one-hop evidence links, and retrieve the original supporting passages. Graph labels guide navigation; Claude receives source chunks.

Phase 5 implements a small curated graph: **36 entities and 29 assertions from 14 papers**. Entity kinds are method, technique, problem and dataset; relations are `uses`, `addresses` and `evaluated_on`. The remaining papers stay searchable through the shared hybrid/structural retriever. Numeric `outperforms` relations are excluded.

`data/graph_curated.json` stores explicit aliases and exact source quotes/spans. All were reviewed by the assistant, with no extraction API calls; this is not comprehensive automatic extraction or independent human review. Source/type/version validation rejects invalid assertions, and every usable relation has a complete supporting indexed chunk. Alias matching uses whole phrases, longest first, keeping EMNIST distinct from MNIST. The graph snapshot is `artifacts/indexes/679098a5db4830ef644dd3ad/graph.json`; its identity binds the curated inputs and source/chunk index.

B3 preserves B2, then matches at most **four entities named in the question**, visits **12 incident relations in one hop** and selects **six support chunks** using local BM25 (deterministic source fallback if none matches). Existing support chunks are promoted and absent ones added: keep the first existing candidate first, place graph support next, then fill from remaining candidates to the same **40-item cap**. Low-ranked candidates can be displaced. The workflow is **dense + BM25 → RRF → hierarchy → graph → source deduplication → optional reranking → final five chunks / 4,000 tokens → Claude**. Graph traces show original assertions, additions/promotions and dropped IDs. Defaults stay unchanged.

```bash
# New command: local validation/build only; no model API calls. The initial graph is already built.
uv run fedresearch graph-build --config configs/experiments/b3_graph.yaml
# Completed: B3 run 7fcb25b480c44aabb7f2d053810d27ac reuses B2's exact post-hierarchy pool.
HF_HOME=work/hf-cache uv run fedresearch evaluate --config configs/experiments/b3_graph.yaml --split dev --with-answers --seed-source artifacts/runs/d57813b4495b4ed299f6bb47c07bacb1/run.json
# Completed: paired B3-R run 0618efd188e8459ea9c66960d905c9c0 reuses B3's exact final merged pool.
HF_HOME=work/hf-cache uv run fedresearch evaluate --config configs/experiments/b3_graph_rerank.yaml --split dev --with-answers --candidate-source artifacts/runs/7fcb25b480c44aabb7f2d053810d27ac/run.json
```

`--seed-source` supports B2→B3 as well as B2a→B2; `--candidate-source` preserves both expansion traces for B3-R and skips all retrieval/expansion. B3 improves these five dev questions' source-span precision/recall/complete coverage over B2 (0.16/0.467/2-of-5 → 0.36/1.0/5-of-5). Paired B3-R scores **0.20/0.667/3-of-5**, despite identical complete candidate coverage: reranking moves annotated dev04 mechanisms and dev05's EMNIST protocol below the final-five cutoff. Assistant required-point review is 2.0/2 for B3 and 1.8/2 for B3-R, with partial-answer limitations. Keep B3 without reranking as the better measured graph configuration here. These are five-question diagnostics, not independent human accuracy or generalization results; graph curation occurred after dev outcomes were known. See [graph results](reports/graph.md) for exact ranks, verification, usage and limitations.

## 10. Evaluation and measured results

**Final evaluation is complete (2026-10-26).** Nine preserved test runs cover 135 question executions with zero execution failures. All use the same 40 papers, models, answer prompt and final five-chunk / 4,000-Voyage-token budget. The [final report](reports/final_evaluation.md), [verified results](reports/final_evaluation_summary.json), [assistant claim/citation audit](reports/final_answer_audit.json) and unchanged [input protocol](reports/final_evaluation_protocol.json) record the evidence and limitations.

| Mode | Gold-span precision@5 | Group recall@5 | Complete coverage |
| --- | ---: | ---: | ---: |
| B0 — dense 20 | 0.1077 | 0.4103 | 5/13 |
| B0-R — paired reranking | 0.2154 | 0.8077 | 10/13 |
| B0-40 — matched dense control | 0.1077 | 0.4103 | 5/13 |
| B1 — hybrid | 0.1692 | 0.7308 | 9/13 |
| B1-R — paired reranking | 0.2308 | 0.8846 | 11/13 |
| B2a — section chunks | 0.1692 | 0.7692 | 9/13 |
| B2 — hierarchy expansion | 0.1692 | 0.6923 | 8/13 |
| B3 — graph expansion | 0.2308 | 0.8590 | 10/13 |
| B3-R — paired reranking | 0.2000 | 0.8462 | 10/13 |

These macro span diagnostics use 13 answerable questions. Both pre-existing negatives abstain in all nine runs. **Mental model:** hybrid combines dense and word matching; reranking chooses among that bounded pool; hierarchy and graph promote related original passages before the same final-five selection. Promotion can also push useful evidence out. Here B1-R retrieves the strongest gold coverage; section chunks give a modest recall gain, hierarchy regresses, and graph recovers some evidence. Preserving structure does not establish a consistent additional benefit in this experiment.

The non-blind assistant audit covers all 279 structured claims and 517 citation links, with per-claim reasons. It distinguishes grounded but incomplete answers from sparse gold-span misses; independent human accuracy remains unmeasured. Missing original FedAvg/AFL evidence, ranking displacement and a source-interpretation error remain documented. Partial citation support often reflects complementary sources within a compound claim. No test-driven tuning or default change was made: dense-20 remains the default with reranking off. Replay timings exclude upstream retrieval and are not end-to-end speed comparisons; costs remain unconfigured. No new CLI commands, reindexing or label refreeze were needed. Delivery checks and temporary-document consolidation remain next.

### Benchmark construction

The benchmark contains 20 questions: 5 development questions and 15 held-out test questions. Across the test set, include paper-specific questions, cross-section questions, cross-paper comparisons, corpus synthesis, and at least two unanswerable or misleading-premise questions. Keep at least ten useful questions if the benchmark is later reduced; the current target remains twenty.

Annotate each question with:

- Question ID, type, text, and split.
- Expected answerability and manually verified answer points.
- Required evidence groups, paper IDs, PDF pages, and canonical block spans.
- Alternative acceptable supporting passages where applicable.
- Comparison constraints, such as which experimental settings must match.

Do not use retrieval output itself as the gold annotation. Freeze held-out labels before tuning. Indexing the complete corpus is allowed; tuning on held-out question answers is not.

### Experiment ladder

| Experiment | Change | What it tests |
| --- | --- | --- |
| B0 | Fixed chunks, dense retrieval | Conventional baseline |
| B0-R | B0 plus rerank-3 on the same deduplicated candidates | Isolates reranking on the dense baseline |
| B0-40 | Dense retrieval with a 40-candidate cap | Matches B1's candidate budget while preserving original B0 results |
| B1 | Same chunks plus BM25 and RRF | Benefit of hybrid retrieval |
| B2a | Hybrid retrieval over section-aware chunks, without expansion | Isolates the chunk-policy change |
| B2 | Section-aware chunks and bounded hierarchy expansion | Benefit of the structure package beyond B1 |
| B3 | B2 plus evidence-linked graph expansion | Incremental benefit of the graph |
| B1-R | B1 plus reranking of its same candidate pool | Incremental benefit of reranking after hybrid retrieval |
| B3-R | B3 plus reranking of its same candidate pool | Incremental benefit of reranking after structure and graph expansion |

B2 changes both chunk boundaries and hierarchy expansion. B2a is implemented to separate them: compare B1/B2a for section chunking, then B2a/B2 for navigation. The latter can reuse identical hybrid seeds through `evaluate --seed-source`; both keep reranking off.

Keep reranking disabled for B0–B3 and B2a. Compare B1-R with B1 and B3-R with B3 separately, using identical pre-reranking candidates, candidate caps, source text, diversity rules, final top-k, and evidence-token budgets within each pair. Reuse saved candidate pools to make this check inspectable. Choose the reranker and tune its settings on development questions only. A B2-R experiment is optional if we need to isolate its effect without graph expansion. Do not attribute a reranked system's gain to hierarchy or the graph without the corresponding controlled comparison.

First run these modes through a fixed retrieval-and-answer pipeline, with the same corpus, parser outputs, embedding model, generator, answer prompt, and final evidence-token budget. Keep model-based query rewriting and automatic routing disabled for this comparison. If corpus routing is enabled in a comparison, apply the same policy to every arm and report its misses.

### Measures

| Measure | Operational definition |
| --- | --- |
| Precision@5 | Relevant retrieved evidence items divided by 5; missing slots count as zero |
| Evidence-group recall@5 | Required evidence groups covered by top 5 items divided by all required groups |
| Complete evidence coverage@5 | Fraction of answerable questions for which all required groups are covered |
| Answer correctness | Human 0–2 score: incorrect, partially correct, correct against expected points |
| Groundedness | Supported substantive claims divided by all substantive claims |
| Citation support | Citations whose passages support the associated claims divided by all citations |
| Abstention behavior | Correct rejection of unanswerable questions and false abstention on answerable questions |
| Efficiency | Query latency, separate reranking latency/usage/cost, embedding/generation tokens, request counts, indexing time, total observed cost |

Gold evidence uses source block spans so annotations remain comparable across chunk policies. Before experiments, define a fixed span-overlap and required-fact rule for relevance, and manually adjudicate ambiguous matches. Deduplicate overlapping results before scoring; report token budgets and retrieval item sizes so large expanded items cannot hide their cost.

Unanswerable questions have no positive evidence groups and are excluded from retrieval precision/recall aggregates; evaluate their abstention separately. For corpus synthesis, define required method/theme groups and supporting papers rather than claiming an exhaustive gold set.

Report per-question results and macro averages over the appropriate questions, with counts and failures. With a small benchmark, do not claim statistical significance or universal superiority. LLM judging may supplement a documented human scoring guide; it is not the only source of correctness labels.

The current 40-paper B0/B0-R comparison is in [reports/evaluation.md](reports/evaluation.md); structured run/usage/score records and the exploratory assistant relevance review are in [reports/evaluation_summary.json](reports/evaluation_summary.json). All 40 answer executions completed without errors. Source-overlap metrics improved with reranking on this benchmark, but gains were mixed by question and the review found actual answer/coverage issues. Independent human scoring and exhaustive claim-support ratios are not reported.

## 11. Reproducibility, verification, and data handling

- Track source metadata, PDF checksums, parser version, chunk policies, embedding model/dimension, prompts, graph schema, config hashes, and index/run IDs.
- For reranking, record enabled state, model/provider/version, candidate cap and IDs, input-length policy, scores/ranks, latency, usage, and failures. Preserve the original ranking for paired comparisons.
- Reuse cached embeddings and validated extraction outputs. Rebuild dependent stages when their inputs change.
- Keep API credentials in environment variables; commit variable names and configuration examples only.
- Exclude generated indexes, local PDFs, raw traces, caches, and credentials from Git by default. Publish corpus metadata and acquisition instructions; include PDFs only where redistribution is permitted.
- Store no credentials in model prompts or logs. Treat PDF text as evidence, including when it contains instructions addressed to an assistant.
- Verify parser reading order and heading detection on representative documents; verify that every emitted citation resolves to the right source page.
- Test index reload, retrieval filters, alias resolution, bounded expansion, insufficient evidence, and end-to-end citation behavior.

The corpus is small; distributed indexing, Kubernetes, separate graph services, and production authentication are outside the initial project scope.

## 12. Working Phase 0–2 usage

Run these commands from the repository root. All 40 PDFs are present in `data/raw/<paper_id>.pdf` and pass manifest checksum validation. Preprocessing, benchmark validation and tests do not require an API key. The tokenizer needs a one-time public download unless already cached. Generation needs `ANTHROPIC_API_KEY`; dense indexing and retrieval need `VOYAGE_API_KEY`.

For the current interactive expansion, a temporary script and verified source list are prepared in ignored `work/`:

```bash
uv run python work/download_corpus_additions.py
```

This downloads only the selected additions (18 pinned arXiv versions and two published PDFs), verifies PDF/title identity, calculates SHA-256 and registers each successful download using the existing seven manifest fields. It checks the original corpus first and reuses registered files on a retry. It prints per-paper progress and a final integrity summary; success requires 40 papers and empty failure lists. The original manifest is backed up in `work/corpus_before_expansion.jsonl`. These are one-off walkthrough files, outside the application CLI; PDFs remain ignored. The user runs each stage and shares its output before continuing. Corpus parsing, indexing and model calls follow separately.

The download and corrected full preprocessing steps completed successfully: 40 papers, 937 pages, 47,592 blocks, 955 sections and 1,158 chunks, capped at 600 Voyage tokens. No failures, serious warnings or structural warnings remain. The first v3 run had six heading warnings; v4 handles the observed Roman-numbered and merged-heading cases, preserving same-line section numbers/titles. These are heuristic parsing checks, not a complete visual audit of every page. No hosted-model calls were needed.

**Tokenizer migration:** changing the tokenizer invalidates old parse/chunk identities. The one-off `work/migrate_benchmark_sources.py` verified and migrated all 26 benchmark passages against unchanged PDF hashes, versions, pages, raw block text, coordinates, exact quotes and offsets. Only parse/block IDs changed; original labels remain in `work/benchmarks_before_voyage/`. Both splits passed canonical validation (5 dev / 15 test), and the new test freeze is valid. Independent human review is still pending. The following local steps completed successfully; the script checks both splits before writing and stops on a missing/ambiguous match or unexpected label edit. Old indexes/results remain historical artifacts; compatibility checks prevent querying the old index with the new settings.

```bash
HF_HOME=work/hf-cache uv run python work/migrate_benchmark_sources.py --apply
HF_HOME=work/hf-cache uv run fedresearch benchmark validate
HF_HOME=work/hf-cache uv run fedresearch benchmark freeze
```

Experiment YAML files in `configs/experiments/` are merged with `configs/default.yaml`. Experiment fields override conflicting defaults within each section; unspecified fields keep their defaults. No `extends` field or recursive inheritance is used. Relative data paths resolve from the project root. Model names in environment variables remain the final override.

```bash
uv sync --locked
uv run fedresearch doctor
uv run fedresearch preprocess
# During tokenizer migration, verify/rebind benchmark source IDs before this command.
uv run fedresearch benchmark validate
uv run pytest -q
```

Configure your provider without putting credentials in Git or chat:

```bash
cp -n .env.example .env
# Set ANTHROPIC_API_KEY and VOYAGE_API_KEY in .env.
uv run fedresearch doctor --live
uv run fedresearch index
uv run fedresearch retrieve "How does SCAFFOLD address client drift?" --paper-id scaffold
uv run fedresearch retrieve "How does SCAFFOLD address client drift?" --config configs/experiments/b0_dense_rerank.yaml
uv run fedresearch ask "How does SCAFFOLD address client drift?" --mode dense
uv run fedresearch ask "How do FedProx and SCAFFOLD differ?" --json
uv run fedresearch evaluate --config configs/experiments/b0_dense.yaml --split dev --with-answers
# Paired B0-R: reuse the exact candidates saved by the completed B0 run.
HF_HOME=work/hf-cache uv run fedresearch evaluate \
  --config configs/experiments/b0_dense_rerank.yaml --split dev --with-answers \
  --candidate-source artifacts/runs/640d302142b1483cb256139526f5a3bc/run.json
```

Live access was verified for Claude Haiku 5.5, Atlas Voyage 4 Large (2048 dimensions) and rerank-3. The historical 20-paper index built in 20.21 seconds using 392,830 embedding tokens across 21 successful calls and passed saved-index reuse. The new 40-paper Voyage-tokenized index `6f8ba8be92dcc84b51a5514f` is now active: 1,158 chunks, 683,346 API-reported embedding tokens over 37 calls and 34.77 seconds. Vector/source IDs, dimensions, chunk fingerprints and all benchmark source spans were verified locally; all four new development/test runs completed (40 answer executions) with exact shared candidates within each pair, zero execution failures and correct abstention on both designated unanswerables in each mode. The held-out reranked run used 181,734 reranking tokens over 15 calls and zero additional query embeddings. Five historical development answers and a separate successful insufficient-evidence check are recorded in [the evaluation report](reports/evaluation.md). See [model setup](docs/models.md).

Citations appear as `[E1]` and resolve to the original paper/version, all contributing section paths, 1-based PDF pages and raw block spans. `--json` includes the answer, cited evidence, usage and execution trace. Citation existence/provenance is checked in code; whether evidence supports a claim requires review. Unsupported questions should yield partial answers or insufficient evidence according to the supplied source text; one live unsupported-measurement check returned insufficient evidence; both designated held-out unanswerables also returned insufficient with zero claims in both retrieval modes.

`evaluate --candidate-source <unreranked-run.json>` verifies index, labels, split, questions, prompt and settings (allowing only the reranking enable switch). It supports dense and hybrid sources, preserving exact candidate IDs/order/scores and saved component rankings while skipping all query embedding/search. Hybrid replay also checks lexical identity and fusion settings. Original B0 files without the new RRF setting remain compatible through its default. The new run records source-run identity/hash and reduced timing scope. Claude is called once per question with nonempty evidence; an empty list produces an insufficient answer locally. Every selected chunk is sent in the prompt: `records[].answer.evidence` stores the input set; `records[].answer.citations` holds the subset actually cited. Query vectors remain transient. Usage is recorded separately.

### Phase 3 development comparison

Phase 3 is complete: BM25 covers all 1,158 existing chunks without re-embedding. The same CLI commands select dense/hybrid modes through configuration; no new Typer commands or packages were added.

| Five-question development metric | Dense-40 | B1 hybrid | B1-R, exact B1 pool |
| --- | ---: | ---: | ---: |
| Gold-span precision@5 | 0.16 | 0.20 | 0.28 |
| Evidence-group recall@5 | 0.467 | 0.533 | 0.800 |
| Complete coverage@5 | 2/5 | 2/5 | 4/5 |
| Candidate group recall | 1.00 | 0.90 | 0.90 |

All runs completed without execution failures. B1-R replayed B1's exact 40 candidates per question with **zero query embeddings/searches**; its run is `f0945144613e412f877f41ec22e8f065`. Reranking improves dev03/dev05 evidence coverage. Hybrid also excludes dev04's annotated SCAFFOLD passage at fused rank 43; the reranker cannot recover it. An assistant review against expected points stays 1.8/2 across all three modes: dev05 still omits two requested EMNIST factors despite retrieving their source. These small dev results do not establish a general answer-quality gain. Full provenance, per-question results, usage and observed limits are in [the hybrid report](reports/hybrid_development.md) and [structured summary](reports/hybrid_development_summary.json).

Reproduce the completed development procedure below. The paired command uses the verified saved B1 run; use your new B1 run ID when making a new pair. Held-out comparisons remain part of the final evaluation phase.

```bash
HF_HOME=work/hf-cache uv run fedresearch evaluate \
  --config configs/experiments/b0_dense_40.yaml --split dev --with-answers
HF_HOME=work/hf-cache uv run fedresearch evaluate \
  --config configs/experiments/b1_hybrid.yaml --split dev --with-answers
HF_HOME=work/hf-cache uv run fedresearch evaluate \
  --config configs/experiments/b1_hybrid_rerank.yaml --split dev --with-answers \
  --candidate-source artifacts/runs/0bd7c449468a4a11b0f7fac4a9d72df5/run.json
```

Reports save `retrieval_protocol`, macro `summary`, per-question `candidate_metrics` and final evidence metrics. With answers, inspect `answer.trace.retrieval`: `rankings` holds dense/BM25 ranks and scores, `candidates` the fused pool, `deduplicated_candidates` the reranker inputs, and `reranking.results` the new ordering. Candidate metrics use the bounded deduplicated pool; final metrics use selected evidence, both under the same source-span rule. Replay timings exclude source retrieval, so do not compare them directly with fresh-run totals. The separate fresh-search B1-R run and earlier local top-20 diagnostic remain in the report.

Default retrieval stays dense-20 with reranking off. B1/B1-R remain explicit configurations; the structural modes below keep the corpus, models, prompt and final budgets fixed.

### Phase 4: section chunks and bounded hierarchy

**Mental model:** B2a searches passages that stay inside a section. B2 then follows a few nearby/parent/child links around strong hits, keeping the same 40-candidate cap and five-chunk/4,000-token answer budget. It considers three anchors, selects up to two context chunks per anchor and at most six overall, using local BM25 within a bounded neighborhood. Context follows its anchor and inherits the anchor's score; the trace records its real source and reason.

No PDF reparse or benchmark migration is needed. `indexing.chunk_policy: section` derives **1,514 chunks** from the existing blocks; the original **1,158 fixed chunks** and their active index remain intact. Both modes use the same 600-token cap/100-token within-section overlap target. Heading-only windows stay as tree metadata; short sections retain short passages. Unclassified sections use adjacency only. The section index is built and verified: **636,094 API embedding tokens, 48 requests, 41.27 seconds**. All vectors, BM25 texts and source records match; benchmark spans and the held-out freeze remain valid. B2a development results are verified: P@5 **0.24**, group recall **0.733**, complete coverage **3/5**, versus B1's 0.20/0.533/2-of-5. These are five-question source-span diagnostics; assistant required-point relevance remains 1.8/2. The exact-seed B2 comparison then scores 0.16/0.467/2-of-5: neighbor interleaving displaces annotated evidence at the final five-item limit, with candidate coverage unchanged. Keep expansion experimental and off by default. See [the structure report](reports/structure.md).

Continue the interactive walkthrough one step at a time:

```bash
# 1. Completed: shared B2a/B2 index, 1,514 chunks. Repeating reuses the completed index.
HF_HOME=work/hf-cache uv run fedresearch index --config configs/experiments/b2a_section.yaml
# 2. Completed: section chunking alone, run fca749fc1c0a4a7a81904e33978df1d5.
HF_HOME=work/hf-cache uv run fedresearch evaluate --config configs/experiments/b2a_section.yaml --split dev --with-answers
# 3. Completed: exact-seed B2 comparison, run d57813b4495b4ed299f6bb47c07bacb1.
HF_HOME=work/hf-cache uv run fedresearch evaluate --config configs/experiments/b2_structure.yaml --split dev --with-answers --seed-source artifacts/runs/fca749fc1c0a4a7a81904e33978df1d5/run.json
```

No new Typer commands were added. `evaluate --seed-source` reuses initial hybrid candidates for hierarchy expansion; `--candidate-source` reuses a final pool for reranking. They are mutually exclusive. Structural traces expose `structural_expansion` with seed IDs, section links, reasons, budgets and dropped seeds. Reports add `seed_candidate_metrics` to distinguish initial coverage from the expanded pool and final evidence; replay timing scopes differ from fresh searches. Models, prompt and labels remain fixed; no new held-out tests run during development.

Generated artifacts are in ignored `data/raw`, `data/processed`, and `artifacts`. Indexes include `metadata.sqlite`, Chroma storage and `index.json` under `artifacts/indexes/<index-id>/`; `CURRENT.json` selects the fixed index and `CURRENT_section.json` the section index; each activates only after a successful build. Embeddings are cached in SQLite. Answer/evaluation traces are saved under `artifacts/runs/<run-id>/`.

Twenty source-span benchmark annotations (5 dev / 15 test) are in `data/benchmarks`. They were prepared independently of retrieval and passed historical canonical validation. The new parse migration is complete: all 26 passages passed canonical validation and the new held-out freeze is valid. Independent human review is still pending; see [evaluation protocol](docs/evaluation.md), including the exact development score calculations. The label freeze hashes the entire `data/benchmarks/test.jsonl` reference-annotation file into `data/benchmarks/frozen.json`; test evaluation rejects a hash mismatch. It does not make files read-only or freeze model weights/settings. Development and held-out span-overlap diagnostics and the completed final assistant claim/citation audit are reported; none is an independent human accuracy score.

Graph retrieval, all final held-out comparisons and the assistant source audit are complete. Delivery verification remains. MCP will not be implemented for this project.

## 13. Implementation roadmap

The sequence is dependency-driven, without a mandatory day allocation. Detailed tasks and acceptance gates are in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

| Phase | Deliverable and exit gate |
| --- | --- |
| 0 — Foundation | Complete: package/contracts/lockfile and Claude/Atlas access verified; bulk indexing succeeds |
| 1 — Preprocessing | Corrected 40-paper parse verified: 937 pages / 955 sections / 1,158 chunks, no diagnostic warnings; all 26 benchmark passages migrated/validated and test labels refrozen |
| 2 — Baseline | Complete for the 40-paper reference: persistent index, cited B0/B0-R answers on 5 dev / 15 held-out questions, paired candidates, abstention checks and reported limitations; independent human grading remains optional follow-up |
| 3 — Hybrid retrieval | Complete: BM25/RRF, B1/B1-R and matched dense-40 configs; 55 offline tests, exact-pool dev comparison, usage and assistant answer review verified. Final held-out comparison and source audit complete; see Section 10 |
| 4 — Structure | Implemented: section chunks, bounded hierarchy, separate B2a/B2 configs and exact seed replay; 67 offline tests/preflight pass. Complete: section index and B2a/B2 exact-seed dev comparison verified. B2a P@5/recall/complete: 0.24/0.733/3-of-5; B2: 0.16/0.467/2-of-5. Hierarchy stays experimental |
| 5 — Graph | Complete: 36 entities / 29 assertions / 14 papers, persistent NetworkX, aliases and bounded B3/B3-R; 81 tests pass. Exact-pool dev comparison verified: B3 0.36/1.0/5-of-5 versus B3-R 0.20/0.667/3-of-5; retain optional reranking off here |
| Evaluation | Complete: nine test runs, 135 successful executions, paired replay checks, full structured-claim/citation assistant audit, usage/timing and observed limitations |
| Delivery | Reproducible setup, current documentation and useful example queries |

Preserve the baseline, structural retrieval, citations and honest comparisons. Keep graph breadth and optional reranking small until measurements justify expansion.

## 14. Definition of done

- [x] Scope is agreed with the user; course rubric and video requirements are excluded.
- [x] The expanded 40-paper corpus is parsed/indexed with the pinned Voyage tokenizer and documented source versions.
- [x] Dense, hybrid, structural and graph retrieval can be selected through configuration; controlled development comparisons are documented, including regressions.
- [x] Source evidence resolves to paper, section and PDF page. (Canonical/indexed-source checks and the final structured-claim/citation assistant audit are complete.)
- [x] Held-out comparisons use fixed inputs/settings and report precision@5, evidence coverage and answer relevance/grounding.
- [x] Any optional reranking is assessed separately with paired candidate pools and cost/latency measurements.
- [x] Actual observed failures and limitations are documented without a failure-count quota.
- [ ] Clean-environment setup, example-query demonstration and temporary-document consolidation pass the delivery gate.

## 15. Updating this README

After each phase, replace planned behavior with verified behavior, update the roadmap and definition of done, add actual setup commands, and link measured results. Record architecture decisions in `docs/decisions.md`. Keep the project described accurately: implemented, experimental, and deferred features should remain distinguishable.
