# Agreed scope and acceptance status

Implementation status updated 2026-10-26; scope follows the user's instructions. The original course rubric, video requirement, mandatory timeline, MCP implementation and quota of two failure cases do not apply.

| Area | Agreed target | Current deliverable |
| --- | --- | --- |
| Corpus | 40 papers: preserve the existing 20 and add 20 selected papers | All 40 PDFs / 937 pages verified; corrected v4 parse has 955 sections / 1,158 chunks and no diagnostic warnings |
| Baseline | Dense retrieval and grounded cited answers | Complete 40-paper index and four B0/B0-R dev/test runs (40 answer executions), zero execution failures, exact paired candidates and successful abstention on both designated negatives in each mode; observed source/answer limitations documented |
| Enhanced retrieval | BM25/RRF, optional rerank-3 and BookRAG-inspired hierarchy | BM25/RRF dev comparisons complete; Phase 4 section chunking/hierarchy implemented and section index verified; B2a/B2 exact-seed dev comparisons complete; hierarchy expansion stays experimental after a final-evidence regression |
| Graph | Small evidence-backed graph where it helps | Phase 5 complete: 36 entities, 29 curated assertions, 14 papers; 81 tests pass. Exact-pool dev comparison verified: B3 P@5/recall/complete 0.36/1.0/5-of-5; B3-R 0.20/0.667/3-of-5. Keep optional reranking off for this graph configuration |
| Models | Claude Haiku 5.5 generation; Voyage 4 Large embeddings | Claude structured-output access verified; Voyage 2048-dimensional bulk embeddings and rerank-3 verified; Atlas throughput blocker resolved |
| Tokenization | Official Voyage 4 Large tokenizer for chunks, queries and evidence text | Pinned tokenizer, all 26 migrated gold passages, test freeze and 1,158-chunk index verified throughout all reported runs |
| Evaluation | Same corpus/models/questions/budgets across baseline/enhanced; precision@5 and answer relevance/grounding | B0/B0-R dev/test, dense-40/B1/B1-R and B2a/B2/B3/B3-R controlled dev comparisons complete, with exploratory assistant relevance/source review. Final held-out enhanced-retrieval comparisons remain; independent human grading/exhaustive support scoring is not claimed |
| Reporting | Observed strengths, regressions, failures and limitations | No deliberate system failures and no failure quota; report genuine observations |
| Delivery | Reproducible package, documentation and useful examples | Local setup verified; no video/submission-rubric deliverable |

MCP and external-client wrappers are outside this project’s scope.

Core BookRAG-inspired scope remains document trees, evidence-linked entities/relations and graph–tree links. Full query classification, retrieval operators, graph-based scoring, Skyline selection and gradient-based entity resolution are optional later research extensions.

The agreed expansion broadens surveys, privacy, communication efficiency, systems and applications. Preserve a fixed corpus/tokenizer during controlled comparisons; verify and regenerate affected benchmark source references consistently. The walkthrough is interactive: provide a command in an answer-field question, inspect the user's output, then give the next step.

Phases 0–2 have a historical live 20-paper baseline: saved-index reuse worked, five development answers completed and an unsupported-measurement check abstained. One mechanistic comparison remained partial. The new 40-paper Voyage-tokenizer baseline and paired reranked evaluation are complete. Phases 3–5 implementation, source validation, controlled development comparisons and targeted assistant review are also complete. Final held-out hybrid/structure/graph comparisons are pending; graph curation is non-blind and its five-question dev results do not establish generalization. Independent human grading is not claimed and the original rubric is not a gate.
