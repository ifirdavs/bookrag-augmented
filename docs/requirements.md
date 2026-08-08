# Agreed scope and acceptance status

This scope reflects the user's instructions through 2026-10-15. The original course rubric, video requirement, mandatory timeline, MCP implementation and quota of two failure cases do not apply.

| Area | Agreed target | Current deliverable |
| --- | --- | --- |
| Corpus | Confirmed 20-paper FL corpus; expand for demonstrated gaps | 20 pinned/checksummed PDFs; 614 pages and 657 traceable fixed chunks |
| Baseline | Dense retrieval and grounded cited answers | Full persistent corpus index, saved-index reuse, cited Claude development answers and successful insufficient-evidence check verified live |
| Enhanced retrieval | BM25/RRF, optional rerank-3 and BookRAG-inspired hierarchy | Reranking implemented; BM25/RRF and hierarchy remain Phases 3–4 |
| Graph | Small evidence-backed graph where it helps | Phase 5; not implemented |
| Agent | Bounded direct retrieval function calls | Phase 6; not implemented |
| Models | Claude Haiku 5.5 generation; Voyage 4 Large embeddings | Claude structured-output access verified; Voyage 2048-dimensional bulk embeddings and rerank-3 verified; Atlas throughput blocker resolved |
| Evaluation | Same corpus/models/questions/budgets across baseline/enhanced; precision@5 and answer relevance/grounding | 5 dev / 15 frozen held-out source annotations; initial live development results recorded; semantic adjudication and held-out evaluation remain |
| Reporting | Observed strengths, regressions, failures and limitations | No deliberate system failures and no failure quota; report genuine observations |
| Delivery | Reproducible package, documentation and useful examples | Local setup verified; no video/submission-rubric deliverable |

MCP is not necessary for the direct agent and will not be implemented for this project. A wrapper may be mentioned as a possible future extension for external clients; no two-tool/one-resource quota applies.

Core BookRAG-inspired scope remains document trees, evidence-linked entities/relations and graph–tree links. Full query classification, retrieval operators, graph-based scoring, Skyline selection and gradient-based entity resolution are optional later research extensions.

The current corpus is enough to build and assess the planned assistant. Preserve a fixed corpus during controlled comparisons; if it expands, version it and regenerate affected benchmark mappings consistently. Add papers according to topic relevance and original-method coverage rather than volume alone.

Phases 0–2 now have a live operational baseline: all 20 papers are indexed, saved-index reuse works, five development answers completed and an unsupported-measurement check abstained. One mechanistic comparison remains partial; quality limitations are documented. Next implement hybrid and structure-aware retrieval. Semantic adjudication and held-out evaluation remain part of the evaluation work; the original rubric is not a gate.
