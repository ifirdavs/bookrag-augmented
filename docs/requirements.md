# Agreed scope and acceptance status

This scope reflects the user's instructions through 2026-10-16. The original course rubric, video requirement, mandatory timeline, MCP implementation and quota of two failure cases do not apply.

| Area | Agreed target | Current deliverable |
| --- | --- | --- |
| Corpus | 40 papers: preserve the existing 20 and add 20 selected papers | All 40 PDFs / 937 pages verified; corrected v4 parse has 955 sections / 1,158 chunks and no diagnostic warnings |
| Baseline | Dense retrieval and grounded cited answers | Complete 40-paper index and four B0/B0-R dev/test runs (40 answer executions), zero execution failures, exact paired candidates and successful abstention on both designated negatives in each mode; observed source/answer limitations documented |
| Enhanced retrieval | BM25/RRF, optional rerank-3 and BookRAG-inspired hierarchy | Reranking implemented; BM25/RRF and hierarchy remain Phases 3–4 |
| Graph | Small evidence-backed graph where it helps | Phase 5; not implemented |
| Agent | Bounded direct retrieval function calls | Phase 6; not implemented |
| Models | Claude Haiku 5.5 generation; Voyage 4 Large embeddings | Claude structured-output access verified; Voyage 2048-dimensional bulk embeddings and rerank-3 verified; Atlas throughput blocker resolved |
| Tokenization | Official Voyage 4 Large tokenizer for chunks, queries and evidence text | Pinned tokenizer, all 26 migrated gold passages, test freeze and 1,158-chunk index verified throughout all reported runs |
| Evaluation | Same corpus/models/questions/budgets across baseline/enhanced; precision@5 and answer relevance/grounding | Current B0/B0-R dev/test comparisons complete; exploratory assistant relevance review and targeted source checks recorded. Independent human grading/exhaustive support scoring and future hybrid/structure/graph comparisons remain |
| Reporting | Observed strengths, regressions, failures and limitations | No deliberate system failures and no failure quota; report genuine observations |
| Delivery | Reproducible package, documentation and useful examples | Local setup verified; no video/submission-rubric deliverable |

MCP is not necessary for the direct agent and will not be implemented for this project. A wrapper may be mentioned as a possible future extension for external clients; no two-tool/one-resource quota applies.

Core BookRAG-inspired scope remains document trees, evidence-linked entities/relations and graph–tree links. Full query classification, retrieval operators, graph-based scoring, Skyline selection and gradient-based entity resolution are optional later research extensions.

The agreed expansion broadens surveys, privacy, communication efficiency, systems and applications. Preserve a fixed corpus/tokenizer during controlled comparisons; verify and regenerate affected benchmark source references consistently. The walkthrough is interactive: provide a command in an answer-field question, inspect the user's output, then give the next step.

Phases 0–2 have a historical live 20-paper baseline: saved-index reuse worked, five development answers completed and an unsupported-measurement check abstained. One mechanistic comparison remained partial. The new 40-paper Voyage-tokenizer baseline and paired reranked evaluation are now complete. Future hybrid/structure/graph comparisons remain evaluation work; independent human grading is not claimed and the original rubric is not a gate.
