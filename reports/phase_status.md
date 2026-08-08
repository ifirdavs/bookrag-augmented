# Current implementation status

Updated 2026-10-15 (Asia/Tashkent).

| Phase | Current result | Remaining work |
| --- | --- | --- |
| 0 — Foundation | Complete: runnable package, locked dependencies, typed contracts, configuration, corpus identities and live Claude/Atlas access. | No current access blocker for the required workload. |
| 1 — Preprocessing | Complete: 20 PDFs / 614 pages / 34,577 blocks / 628 sections / 657 fixed chunks with source validation and representative visual checks. | Revisit only if new questions expose parsing gaps. |
| 2 — Baseline | Operational baseline complete: all corpus chunks indexed, saved-index reuse, cited development answers, successful abstention check, benchmark annotations and initial measurements. | Semantic adjudication and independent held-out review remain recommended; known retrieval/answer limitations are documented. |
| 3 — Hybrid/reranking | Optional Atlas rerank-3 adapter and an initial paired B0-R development replay are verified. | BM25/RRF and controlled hybrid comparisons. |
| 4–6 | Design documented. | Section-aware retrieval, evidence-backed graph and bounded direct-function agent. |
| 7–8 | Source-based benchmark protocol and initial development report available. | Final controlled evaluation/analysis, clean reproducibility checks and documentation consolidation. |

The user added a payment method after the trial limit rejected the default batch. On recheck, the complete **2048-dimensional** Atlas index built in **20.21 seconds**, using **392,830 embedding tokens over 21 successful calls**. Index ID: `da44ff5cde9177848b1ad969`. It is selected by `artifacts/indexes/CURRENT.json`. Reload/reuse passed without additional embedding calls. The exact new account rate limits were not queried.

The final B0 development answer run completed all five questions with zero execution errors and valid citation IDs. The model marked four answers sufficient and one comparison partial because the final dense evidence missed the FedProx mechanism. The prompt was refined once on development data to reduce unrelated theory/proof qualifications; both original/final runs are retained. These sufficiency labels are not independent human accuracy scores.

An unscored FedAvg CO2-measurement question returned insufficient evidence with zero claims. Atlas rerank-3 was checked on real passages and in an exact frozen-candidate replay. See [initial development results](evaluation.md) for per-question span diagnostics, run identities and observed limitations. No universal improvement claim or paired answer-quality claim is made.

All 20 benchmark source annotations validate against the actual saved index. The 15 held-out questions were not queried, and their frozen hash is unchanged. The corpus/models/chunk settings remain fixed for later comparisons.

Verification: **35 offline tests passed** for the implementation, with the 17 pipeline tests rechecked after the prompt update. Ruff lint/format, benchmark/index checks, package build and whitespace checks pass. PyMuPDF emits upstream SWIG deprecation warnings under Python 3.13. Small and corpus-scale hosted checks complement the mocked SDK transport tests; they do not establish universal semantic correctness.

All **133 source/test functions** and all Python modules have descriptions. README Section 5 explains every application Python file. Temporary `docs/` notes will be merged into the README/final reports, links updated and the directory removed in Phase 8.

Next: Phase 3 BM25/RRF, then Phase 4 section-aware chunks and bounded hierarchy expansion against the saved B0 reference. The planned graph store remains NetworkX; no graph or Neo4j service is implemented. Course/video requirements, MCP implementation and failure quotas remain excluded. No commits, pushes or publication were performed.
