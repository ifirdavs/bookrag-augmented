# FedResearch implementation plan

Status: **planning only**. This file turns the [README](../README.md) into an ordered build plan. No application implementation is included in this planning deliverable.

Work through the phases sequentially. Each phase produces a reviewable result, updates the README, and passes its acceptance gate before the next phase begins. The 14-day schedule is provisional, not a commitment to a known deadline.

## Phase 0 — Foundation and design freeze

**Purpose:** Resolve decisions that would otherwise force changes across the pipeline.

Tasks:

1. Check the original course rubric: allowed libraries, originality requirements, corpus minimum, agent requirements, MCP requirements, metrics, report format, and demo/video duration. Save a requirement-to-deliverable checklist.
2. Confirm the hosted generation and embedding provider. Check account deployment availability, credentials, tool-calling support, API shape, embedding dimensions, rate limits, and observed cost. The earlier GPT-6 Luna preference remains conditional on actual availability.
3. Create `pyproject.toml`, the package skeleton, `.gitignore`, `.env.example`, validated settings, and a lockfile. Pin compatible dependency versions after a small connectivity/compatibility check.
4. Define `Paper`, `Block`, `Section`, `Chunk`, `Entity`, `Relation`, `Evidence`, and `Answer` contracts. Specify versioning, source spans, PDF page numbering, and the output schema of each stage.
5. Define separate preprocessing, indexing, retrieval, generation, MCP, and evaluation settings. Set explicit starting context budgets and tool-call limits.
6. Choose 3 representative PDFs for development and a candidate manifest of at least 20. Include original-method papers and some related heterogeneity/optimization papers; include surveys when useful, while distinguishing their reported claims from original results.
7. Record decisions and working assumptions in `docs/decisions.md` and `docs/corpus.md`.

**Outputs:** Package foundation, configuration draft, schema definitions, initial manifest, verified requirements checklist.

**Acceptance gate:** A local package import works; required provider calls are feasible; manifest entries are uniquely identifiable; every downstream artifact has a defined source-provenance contract.

**README update:** Actual provider/configuration requirements, confirmed targets, dependency choices, and implemented status.

## Phase 1 — Corpus and preprocessing

**Purpose:** Make document evidence reliable before it becomes searchable.

Tasks:

1. Acquire selected PDFs and record source URL, version, retrieval date, checksum, title, authors, and year. Detect duplicate files and multiple versions of the same paper.
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
2. Build persistent dense chunk retrieval and SQLite provenance lookup. Create a lightweight paper metadata/abstract search index, but keep experimental routing policy explicit.
3. Implement `RetrievalService` with query, filters, mode, top-k, and evidence budget. Return typed evidence records.
4. Add a fixed answer pipeline: retrieve, pack evidence, call the hosted model, validate citation IDs, and return answer plus evidence. This is the baseline, before agent planning.
5. Implement a minimal `ask` CLI and an insufficient-evidence response.
6. Begin manual benchmark annotation from the canonical source blocks. Target 5 development and 15 held-out questions. Include required evidence groups for multi-section and multi-paper questions.
7. Verify annotation answerability independently of the retriever; freeze the held-out set before tuning enhanced methods.

**Outputs:** B0 index/configuration, cited CLI answers, benchmark files, baseline dev traces.

**Acceptance gate:** An index can be saved/reloaded; filters work; representative questions return original supporting text; citations resolve correctly; an absent answer is handled; benchmark annotations do not depend on chunk policy.

**README update:** Working install and baseline commands, selected model/embedding deployment, citation format, benchmark construction details.

## Phase 3 — Hybrid retrieval

**Purpose:** Test whether lexical matching improves evidence discovery.

Tasks:

1. Index the same fixed chunks with BM25.
2. Implement ranked-list RRF with deterministic tie handling and source-span deduplication.
3. Add B1 configuration while preserving B0. Use the same generator, answer prompt, final evidence budget, and corpus-routing policy.
4. Implement the retrieval metric runner on the development questions.
5. Inspect method-name/acronym questions and failure cases. Tune candidate count and fusion settings using development questions only.

**Outputs:** BM25 index, hybrid service, B1 config, paired B0/B1 dev results.

**Acceptance gate:** Dense and lexical rankings can be inspected; fusion handles missing/empty lists; duplicated evidence does not inflate coverage; observed benefits and regressions are recorded.

**README update:** Hybrid settings and actual retrieval behavior. Do not claim improved performance without measured support.

## Phase 4 — Document hierarchy and structure-aware retrieval

**Purpose:** Recover relevant evidence that spans document structure.

Tasks:

1. Finalize section-aware chunking with the same approximate size target as fixed chunks. Split oversized sections and preserve parent/child links and full section paths.
2. Add section hints and retrieval of adjacent source blocks, bounded children, or relevant parent content.
3. Enforce an expansion budget and record why each evidence item was added. Expansion should stop before it fills context with an entire paper.
4. Add B2: hybrid retrieval over section-aware chunks plus hierarchy expansion.
5. If time permits, add B2a: section-aware chunks without expansion, so chunking and navigation can be analyzed separately.
6. Compare on development questions using canonical gold spans. Review questions connecting methodology and experiments.

**Outputs:** Section chunk policy, hierarchy retrieval, B2/B2a configs, dev comparisons.

**Acceptance gate:** Expanded evidence traces back to real sections; context remains bounded; both fixed and structural indexes remain runnable; section-detection failures have documented fallbacks.

**README update:** Implemented structural operators, limits, and observed strengths/failures.

## Phase 5 — Evidence-linked knowledge graph

**Purpose:** Add semantic navigation only where original evidence supports it.

Tasks:

1. Define a narrow entity/relation schema and curated alias map.
2. Extract structured relations from canonical source passages. Cache extraction outputs by source/configuration/model version.
3. Validate entity types, relation types, supporting IDs, and quoted/spanned evidence. Remove unsupported relations; flag uncertainty.
4. Review a representative sample, including shared method/dataset names across papers. Store canonical entity identities with paper-specific relation evidence.
5. Persist the graph and graph-to-block/section links. Implement bounded traversal, starting with one hop and a small candidate cap.
6. Add B3 and inspect whether graph expansion supplies missing gold evidence or adds noise. Preserve exact relation provenance in traces.

**Outputs:** Graph data, validation report, graph retrieval, B3 config and dev results.

**Acceptance gate:** Every usable edge resolves to original supporting text; graph persistence/reload works; alias resolution is reviewed; traversal is bounded; no numeric ranking of methods is inferred from incompatible experiments.

**README update:** Graph coverage, relation types, extraction approach, cost, and observed failure modes.

**Scope fallback:** A curated evidence-backed graph is acceptable for a small corpus if documented honestly. Reduce relation breadth before sacrificing citation quality or evaluation.

## Phase 6 — MCP server and bounded agent

**Purpose:** Turn the retrieval pipeline into an agent-accessible research assistant.

Tasks:

1. Build the FastMCP server with `search_papers`, `retrieve_evidence`, and `fl://corpus/statistics`.
2. Make the server wrappers call the existing retrieval service. Choose and document local transport and process lifecycle.
3. Verify tool discovery, argument validation, returned evidence records, error handling, and resource reads using a real MCP client.
4. Build the agent as an MCP client with model tool calling. Handle paper discovery, scoped evidence gathering, and a missing-evidence follow-up.
5. Set maximum tool calls, timeouts, retries, and a final answer/evidence token budget.
6. Log observable tool calls and evidence IDs. Check citation existence in code; retain claim-support judgment for evaluation.
7. Show a comparison requiring evidence from both methods and an unanswerable query. Inspect failure behavior when the server or provider is unavailable.

**Outputs:** MCP server, real client integration, agent CLI, documented execution traces.

**Acceptance gate:** Calls travel through MCP; tools and resource work; the agent cannot loop indefinitely; invalid citations are rejected/repaired within a bounded process; missing evidence leads to a qualified answer or abstention.

**README update:** Actual launch/connect commands, interface examples, supported agent behaviors, and limits.

## Phase 7 — Controlled evaluation and analysis

**Purpose:** Measure changes and distinguish retrieval effects from agent behavior.

Tasks:

1. Confirm the frozen benchmark, relevance mapping rule, human scoring rubric, and applicable denominators.
2. Run B0–B3, plus B2a if implemented, using a fixed retrieval-and-answer pipeline. Keep the corpus, embedding model, generator, prompt, and final evidence-token budget constant.
3. Save retrieved evidence IDs/spans, scores, answer text, citations, configuration, index version, token usage, cost, and latency for each question.
4. Score precision@5, evidence-group recall@5, complete evidence coverage, answer correctness, groundedness, citation support, and abstention. Exclude unanswerable questions from positive-evidence retrieval aggregates.
5. Evaluate the agent separately using the best supported retrieval configuration. Report additional tool calls, latency, evidence coverage, and failures.
6. Report paired per-question results and macro averages with sample counts. Review regressions, not just improvements.
7. Write at least two observed failure cases with retrieved evidence, cause, attempted fix if any, and remaining limitation. Label any post-test changes and reruns explicitly rather than treating the old held-out set as fresh.

**Outputs:** Run records, evaluation report, failure report, updated conclusions.

**Acceptance gate:** Results can be traced to the exact corpus/index/configuration; scores use declared rules; claims match the data; missing runs and failures remain visible.

**README update:** Measured results, supported conclusions, reproducibility instructions, limitations.

## Phase 8 — Documentation and demonstration

**Purpose:** Make the project reproducible and easy to assess.

Tasks:

1. Update the README to show what is implemented and remove or label obsolete planned commands.
2. Verify installation and a complete small-corpus workflow in a clean environment. Keep credentials external and document index rebuilding.
3. Prepare demonstrations: one method explanation, one comparison, and one corpus-wide synthesis. Show source evidence, PDF pages, MCP calls, and one insufficient-evidence example.
4. Explain the baseline and ablations, strongest result, regression/failure cases, and practical limits.
5. Prepare the required recording and submission artifacts using the verified assignment rubric. Cite research and dependencies consulted.

**Outputs:** Final README, demo guide, required recording/report, reproducible repository.

**Acceptance gate:** A new reader can obtain the corpus, configure credentials, build indexes, run a cited answer, and reproduce the documented evaluation procedure.

## Decisions to finalize in the next session

| Decision | Working default | Resolve during |
| --- | --- | --- |
| Project name | FedResearch | Phase 0 |
| Corpus | 20+ text-based FL papers; 3 development examples | Phase 0–1 |
| Provider and deployment | Hosted generation and embeddings; verify earlier preference | Phase 0 |
| PDF parser | PyMuPDF, with layout quality gate | Phase 1 |
| Retrieval storage | Chroma, SQLite, BM25, NetworkX | Phase 0 compatibility check |
| Benchmark size | 20 questions, 5 dev / 15 test | Phase 2 |
| First user interface | CLI | Phase 0 |
| MCP transport | Local stdio if supported by pinned FastMCP | Phase 6, interface agreed in Phase 0 |
| Optional work | B2a before UI polish; reranker and table-result records later | After core gates |

## How we will work phase by phase

For each implementation session: identify the phase and its acceptance gate, implement its bounded scope, verify consequential behavior, inspect outputs, and update documentation. Do not start all folders as placeholder code. Add modules when needed and keep shared contracts stable.

The next session begins with **Phase 0**, not graph extraction or agent orchestration. Its concrete result is a runnable package foundation and verified choices for the corpus and hosted model access.
