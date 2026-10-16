# FedResearch implementation plan

Status: **Phases 0–5 and final evaluation complete; delivery remains** (2026-10-26). Phase 3 was committed as `2dfcd59` and Phase 4 as `509beaf` with the requested dates. Section chunks reuse canonical sources; the fixed index is preserved. All 81 offline tests pass. B3/B3-R exact-pool development results are verified (P@5 0.36/0.20, recall 1.0/0.667, complete 5/5 vs 3/5). Keep B3 without reranking as the better measured graph configuration here; hierarchy/graph remain explicit experiments and defaults stay dense-20 with reranking off. See [phase status](reports/phase_status.md), [graph results](reports/graph.md), [hybrid results](reports/hybrid_development.md) and [structure results](reports/structure.md).

Work through the phases sequentially. Each phase produces a reviewable result, updates the README, and passes its acceptance gate before the next phase begins. There is no mandatory deadline or day allocation; keep the implementation focused on grounded answers and measured retrieval improvements.

## Phase 0 — Foundation and design freeze

**Purpose:** Resolve decisions that would otherwise force changes across the pipeline.

Tasks:

1. Follow the user-agreed scope in `docs/requirements.md`: grounded FL answers, hybrid search, BookRAG-inspired structure and controlled evaluation. No course-rubric, video, MCP or failure-count requirement applies.
2. Use Claude Haiku 5.5 through the official Anthropic SDK and `ANTHROPIC_API_KEY`. Use Voyage 4 Large at 2048 dimensions for document and query embeddings, with `VOYAGE_API_KEY`. Check access, structured outputs, dimensions, input limits and observed usage before corpus indexing.
3. Create `pyproject.toml`, the package skeleton, `.gitignore`, `.env.example`, validated settings, and a lockfile. Pin compatible dependency versions after a small connectivity/compatibility check.
4. Define the current `Paper`, `Block`, `Section`, `Chunk`, `Evidence` and `Answer` contracts. Specify versioning, source spans and PDF page numbering. Add graph contracts in Phase 5 when they are used.
5. Configure preprocessing, embeddings, retrieval, generation and evaluation. Experiment files merge their fields with `default.yaml`, overriding conflicts without an inheritance mechanism. The optional rerank-3 adapter/settings are implemented and access-verified.
6. Preserve the confirmed 20 papers and add the 20 selected additions for the agreed 40-paper target. Use FedAvg/FedProx/SCAFFOLD as initial representatives and inspect the added layouts. Distinguish surveys from original results. Use the pinned `voyageai/voyage-4-large` tokenizer; revalidate source references after migration and keep the corpus/tokenizer fixed within each controlled comparison.
7. Record decisions and working assumptions in `docs/decisions.md` and `docs/corpus.md`.

**Outputs:** Package foundation, configuration draft, schema definitions, initial manifest, agreed scope checklist.

**Acceptance gate:** A local package import works; required provider calls are feasible; manifest entries are uniquely identifiable; every downstream artifact has a defined source-provenance contract.

**README update:** Actual provider/configuration requirements, confirmed targets, dependency choices, and implemented status.

## Phase 1 — Corpus and preprocessing

**Purpose:** Make document evidence reliable before it becomes searchable.

Tasks:

1. Preserve the existing 20 PDFs in `data/raw/<paper_id>.pdf` and download the 20 selected additions interactively. Keep only paper ID, title, year, source URL, document version, SHA-256 and method names in the manifest. Check file identities and duplicate versions; keep one-off acquisition outside the application CLI.
2. Parse the 3 development PDFs into text blocks with page and bounding-box metadata. Inspect title pages, two-column body pages, headings, references, and at least one experimental-results page.
3. Check for mixed columns, missing text, repeated headers/footers, hyphenation, and unsupported tables. Preserve original text/provenance through cleaning.
4. Implement heading detection and parent/child section relationships using numbering and font/layout cues. Use explicit fallback sections when detection is uncertain.
5. Implement fixed-size chunks first, retaining source block spans. Implement the interface for section-aware chunking; finalize that policy in Phase 4.
6. If reading order or tables fail materially, evaluate Docling on the same three PDFs and select one default parser. Record the reason and quality differences.
7. Run the chosen parser over the full selected corpus. Produce parse diagnostics, failure counts, and a manifest of successfully processed versions.

**Outputs:** Processed canonical documents, section records, baseline chunks, quality diagnostics.

**Acceptance gate:** Sample blocks match visible PDF content and cited pages; reading order is usable; headings and fallbacks are inspectable; no failed paper silently counts as indexed. Review all documents with serious warnings.

**README update:** Parser choice, processed corpus count, table/figure limitations, actual artifact locations.

## Phase 2 — Conventional RAG baseline and benchmark foundation

**Purpose:** Establish a working system and a fair reference point.

Tasks:

1. Batch embeddings and cache them by document/chunk/configuration/model identity.
2. Build persistent dense chunk retrieval and SQLite provenance lookup. Search the full corpus unless an explicit filter is supplied; keep automatic routing disabled.
3. Implement `RetrievalService` with query, filters, mode, top-k, and evidence budget. Return typed evidence records.
4. Add a fixed answer pipeline: retrieve, pack evidence, call the hosted model, validate citation IDs, and return answer plus evidence.
5. Implement a minimal `ask` CLI and an insufficient-evidence response.
6. Begin manual benchmark annotation from the canonical source blocks. Target 5 development and 15 held-out questions. Include required evidence groups for multi-section and multi-paper questions.
7. Verify annotation answerability independently of the retriever; freeze the held-out set before tuning enhanced methods.

**Outputs:** B0 index/configuration, cited CLI answers, benchmark files, baseline dev traces.

**Acceptance gate:** An index can be saved/reloaded; filters work; representative questions return original supporting text; citations resolve correctly; an absent answer is handled; benchmark annotations do not depend on chunk policy.

**README update:** Working install and baseline commands, selected generation and embedding models, citation format, benchmark construction details.

## Phase 3 — Hybrid retrieval and optional reranking

**Purpose:** Test whether lexical matching improves evidence discovery, then independently test whether reranking improves evidence selection.

Complete (2026-10-22): SQLite FTS5 BM25, RRF and shared reranking use the same fixed chunks and existing CLI commands. Dense-40 (`f4be2b88c53e42998e1fc7c88c605eaf`), B1 (`0bd7c449468a4a11b0f7fac4a9d72df5`) and exact-pool B1-R (`f0945144613e412f877f41ec22e8f065`) are verified, with five questions each and zero execution failures. P@5 is 0.16/0.20/0.28; group recall 0.467/0.533/0.800; complete coverage 2/5, 2/5, 4/5. Candidate recall is 1.00/0.90/0.90. Targeted assistant relevance stays 1.8/2, so retain the original defaults and report retrieval gains separately from answer quality. Usage, timing scope, regressions and source checks are recorded. The additional fresh-search reranked run remains separate. Original B0-20 is preserved; no new Typer commands were added.

Tasks:

1. Index the same fixed chunks with BM25.
2. Implement ranked-list RRF with deterministic tie handling and source-span deduplication.
3. Add B1 configuration while preserving B0. Use the same generator, answer prompt, final evidence budget, and corpus-routing policy.
4. Implement the retrieval metric runner on the development questions.
5. Inspect method-name/acronym questions and failure cases. Tune candidate count and fusion settings using development questions only.
6. The `retrieval/reranking.py` adapter and independent settings toggle are implemented using Atlas rerank-3; keep them shared across later retrieval modes. Score bounded query-passage pairs after merging/deduplication and before final evidence packing; later reuse this stage after hierarchy/graph expansion. Preserve source IDs, original scores/ranks, and rerank scores/ranks. RRF remains rank fusion rather than model-based relevance scoring.
7. Start with a candidate cap of 40 (development tuning range 30–50). Verify scientific-passage input limits using the selected tokenizer and log truncation. Keep final top-k, diversity rules, and evidence-token budget identical with reranking off/on. Confirm provenance and deterministic tie handling; record empty candidate sets and provider failures without silently substituting successful evaluation results.
8. Add B1-R (`b1_hybrid_rerank.yaml`) and compare it with B1 on the same saved pre-reranking candidate pool. Keep B0/B1 core runs without reranking. Record candidate recall before reranking, final evidence metrics, answer quality, extra latency, and usage/cost. Freeze model/settings using development questions only.

**Outputs:** BM25 index, hybrid service, configurable reranking adapter, B1/B1-R configs, separate paired B0/B1 and B1/B1-R dev results.

**Acceptance gate:** Dense, lexical, and reranked rankings can be inspected; fusion handles missing/empty lists; duplicated evidence does not inflate coverage; reranking preserves provenance and obeys candidate/input limits; off/on runs share candidates and final budgets; failures, benefits, regressions, latency, and cost are recorded.

**README update:** Hybrid and reranking settings, selected reranker, actual retrieval behavior, and separate comparisons. Do not claim improved performance without measured support. Enable reranking by default only if development results justify its quality/latency/cost tradeoff.

## Phase 4 — Document hierarchy and structure-aware retrieval

**Purpose:** Recover relevant evidence that spans document structure.

Implementation (2026-10-23): the section policy reuses canonical source IDs, excludes heading-only windows and produces 1,514 chunks. Fixed/section indexes have independent active pointers. B2a uses hybrid search over section chunks; B2 adds bounded one-hop adjacency/parent/child context (three anchors, two per anchor, six overall, total cap 40). Existing final budgets and optional reranking are shared. `evaluate --seed-source` isolates navigation using B2a's exact hybrid seeds; no new Typer commands/packages. All 67 offline tests, source validation and historical-run replay checks pass. The shared section index is built and verified (636,094 API tokens / 48 requests / 41.27 seconds). B2a dev is verified: P@5 0.24, group recall 0.733, complete coverage 3/5; assistant required-point relevance remains 1.8/2. B2 exact-seed evaluation and targeted answer review are complete: P@5 0.16, group recall 0.467, complete coverage 2/5, with unchanged candidate coverage and assistant relevance. Neighbor interleaving displaces gold evidence from final selection. The engineering/development gate is complete; retain expansion as experimental and keep it off by default.

Tasks:

1. Finalize section-aware chunking with the same approximate size target as fixed chunks. Split oversized sections and preserve parent/child links and full section paths.
2. Add section hints and retrieval of adjacent source blocks, bounded children, or relevant parent content.
3. Enforce an expansion budget and record why each evidence item was added. Expansion should stop before it fills context with an entire paper.
4. Add B2: hybrid retrieval over section-aware chunks plus hierarchy expansion.
5. If time permits, add B2a: section-aware chunks without expansion, so chunking and navigation can be analyzed separately.
6. Compare on development questions using canonical gold spans. Review questions connecting methodology and experiments.
7. Keep B2/B2a core runs without reranking. Route merged structural candidates through the shared optional reranking stage before packing; retain expansion reasons and source links. Add B2-R only if needed to isolate reranking without graph expansion.

**Outputs:** Section chunk policy, hierarchy retrieval, B2/B2a configs, dev comparisons.

**Acceptance gate:** Expanded evidence traces back to real sections; context remains bounded; both fixed and structural indexes remain runnable; section-detection failures have documented fallbacks.

**README update:** Implemented structural operators, limits, and observed strengths/failures.

## Phase 5 — Evidence-linked knowledge graph

Complete (2026-10-24), after verified commit `509beaf`: curated graph fallback selected to keep code/model use simple. Typed aliases and 29 source assertions across 14 papers produce 36 canonical nodes; NetworkX persistence, complete source links and bounded one-hop retrieval are verified. Existing SQLite span mappings are reused instead of a separate link store. B2→B3 exact-seed and B3→B3-R exact-pool development comparisons, metrics and targeted answer review are verified. All 81 offline tests pass; result verification made no hosted calls. B3-R regresses final gold-span coverage despite identical complete candidate coverage; preserve that result. Graph curation is non-blind; the final frozen-test comparison is recorded separately and does not establish independent generalization. See [graph results](reports/graph.md).

**Purpose:** Add semantic navigation only where original evidence supports it.

Tasks:

1. Define a narrow entity/relation schema and curated alias map.
2. Extract structured relations from canonical source passages. Cache extraction outputs by source/configuration/model version.
3. Validate entity types, relation types, supporting IDs, and quoted/spanned evidence. Remove unsupported relations; flag uncertainty.
4. Review a representative sample, including shared method/dataset names across papers. Store canonical entity identities with paper-specific relation evidence.
5. Persist the graph and graph-to-block/section links. Implement bounded traversal, starting with one hop and a small candidate cap.
6. Add B3 and inspect whether graph expansion supplies missing gold evidence or adds noise. Preserve exact relation provenance in traces.
7. Keep B3 without reranking for the structure/graph ladder. Add B3-R (`b3_graph_rerank.yaml`) using the same merged, deduplicated, bounded B3 candidate pool; rerank supporting source passages, never graph labels alone. Compare coverage and cost on development questions independently of the B2/B3 graph comparison.

**Outputs:** Graph data, validation report, graph retrieval, B3/B3-R configs and separate paired dev results.

**Acceptance gate:** Every usable edge resolves to original supporting text; graph persistence/reload works; alias resolution is reviewed; traversal is bounded; no numeric ranking of methods is inferred from incompatible experiments.

**README update:** Graph coverage, relation types, extraction approach, cost, and observed failure modes.

**Scope fallback:** A curated evidence-backed graph is acceptable for a small corpus if documented honestly. Reduce relation breadth before sacrificing citation quality or evaluation.

## Final evaluation and analysis

Complete (2026-10-26), after verified commit `cb95b06`. All seven new tests plus two preserved baseline controls are verified: 135 executions, zero execution failures. B1-R has the highest group recall (0.8846) and complete coverage (11/13); B2a/B2/B3/B3-R complete coverage is 9/13, 8/13, 10/13 and 10/13. Both negatives abstain in every mode. The [final report](reports/final_evaluation.md) and [structured results](reports/final_evaluation_summary.json) include candidate/final scores, exact pairings, source checks, usage/timing and observed regressions. The [assistant audit](reports/final_answer_audit.json) reviews all 279 structured claims and 517 citation links, with per-claim reasons and explicit non-independent scoring limits. The [input protocol](reports/final_evaluation_protocol.json), labels, prompt, graph and settings remain unchanged. Defaults were not selected from test outcomes. No additional hosted calls or new Typer commands were needed for analysis. Independent human review remains optional; delivery checks are next.

**Purpose:** Measure dense, hybrid, structure, graph and reranking effects under controlled conditions.

Tasks:

1. Confirm the frozen benchmark, relevance mapping rule, human scoring guide, and applicable denominators.
2. Run B0–B3, plus B2a if implemented, with reranking disabled through a fixed retrieval-and-answer pipeline. Separately run B1-R/B3-R (and optional B2-R) against their matching unreranked configurations. Reuse identical pre-reranking candidate pools within each pair; hold candidate caps, source text, diversity rules, final top-k, and evidence-token budget constant. Keep the corpus, embedding model, generator, and prompt constant across comparisons. Freeze all choices on development questions before test runs.
3. Save pre-reranking candidate IDs/spans and original ranks/scores, final evidence IDs/spans and rerank scores/ranks, answer text, citations, configuration, index version, token usage, cost, and latency for each question. Report reranking model/version, input truncation, latency, usage/cost, and failures separately from totals.
4. Score precision@5, evidence-group recall@5, complete evidence coverage, answer correctness, groundedness, citation support, and abstention. Exclude unanswerable questions from positive-evidence retrieval aggregates.
5. Report paired per-question results and macro averages with sample counts. Separate dense/hybrid, structure, graph, and reranking effects; examine candidate recall before reranking as well as final evidence coverage. Review regressions, not just improvements, and report the latency/cost tradeoff without assuming reranking always helps.
6. Document any failures actually observed, with evidence, cause, attempted fixes and remaining limitations. Do not fabricate or induce failures or impose a reporting quota. If no failures are observed, state that result for the tested questions without claiming universal correctness. Label post-test changes/reruns explicitly.

**Outputs:** Run records, evaluation report, observed-limitations report, updated conclusions.

**Acceptance gate:** Results can be traced to the exact corpus/index/configuration; scores use declared rules; claims match the data; missing runs and failures remain visible.

**README update:** Measured results, supported conclusions, reproducibility instructions, limitations.

## Delivery — Documentation and demonstration

**Purpose:** Make the project reproducible and easy to assess.

Tasks:

1. Update the README to show what is implemented and remove or label obsolete planned commands.
2. Verify installation and a complete small-corpus workflow in a clean environment. Keep credentials external and document index rebuilding.
3. Prepare useful example queries: a method explanation, a comparison and a bounded corpus synthesis. Show original source evidence and PDF pages. Include an abstention example to demonstrate appropriate evidence limits.
4. Explain the baseline and ablations, strongest result, regression/failure cases, and practical limits.
5. Provide the reproducible package, setup/configuration guide and evaluation artifacts. Cite research and dependencies consulted. No video or course submission checklist is required.
6. Merge useful content from temporary `docs/` notes into the README and final reports, rewrite every link, and remove `docs/` as requested. Keep the README Python file guide accurate.

**Outputs:** Final README, example-query guide, evaluation report, reproducible repository.

**Acceptance gate:** A new reader can obtain the corpus, configure credentials, build indexes, run a cited answer, and reproduce the documented evaluation procedure.

## Decisions to finalize in the next session

| Decision | Working default | Resolve during |
| --- | --- | --- |
| Project name | FedResearch | Phase 0 |
| Corpus | 40 papers: existing 20 plus 20 selected additions | Acquired, parsed and indexed |
| Generation and embeddings | Claude Haiku 5.5; Voyage 4 Large, 2048 dimensions | Index, cited development answers and baseline diagnostics verified live |
| PDF parser | PyMuPDF, with layout quality gate | Phase 1 |
| Retrieval storage | Chroma; SQLite sources and FTS5 BM25; NetworkX JSON | Dense/lexical/graph persistence and source links verified |
| Benchmark size | 20 questions, 5 dev / 15 test | Phase 2 |
| First user interface | CLI | Phase 0 |
| Reranking | Atlas rerank-3 implemented; disabled in core ladder; B0-R/B1-R/B3-R pairs | All three pairs verified; B3-R reduces final dev coverage, so retain reranking off for the measured graph configuration |
| Optional work | Separate B2-R/context-ordering experiments; table-result records later | After core gates |

## How we will work phase by phase

For each implementation session: keep the code small and direct, implement only the current phase, reuse library features and shared logic, verify consequential behavior, inspect outputs, and update documentation. Do not start all folders as placeholder code. Add modules when needed and keep shared contracts stable.

Phases 0–5 and final evaluation are complete. The measured results include both gains and regressions; keep the experimental modes explicit and preserve all runs and frozen choices. Delivery is next: verify a clean setup/workflow, prepare example queries, and consolidate useful temporary documentation before removing `docs/`. Independent human review remains optional and is not implied by the assistant source audit.
