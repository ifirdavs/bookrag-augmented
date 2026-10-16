# Current implementation status

Updated 2026-10-26 (Asia/Tashkent).

**Implementation, final evaluation and delivery are complete.** The 40-paper corpus has persistent fixed/section indexes, dense and BM25/RRF retrieval, optional reranking, bounded hierarchy, evidence-linked graph navigation and cited answers. All nine frozen test arms are verified: 135 question executions, zero execution failures, with both negatives correctly abstaining in every mode. No source/configuration/label changes were made during final evaluation.

| Phase | Verified result | Remaining work |
| --- | --- | --- |
| 0 — Foundation | Runnable package, locked dependencies, validated contracts/settings, Claude and Atlas access | No current implementation blocker |
| 1 — Preprocessing | 40 PDFs / 937 pages / 47,592 blocks / 955 sections; corrected v4 parse has no diagnostics warnings; 26 benchmark source references migrated/validated | Preserve corpus/parser/tokenizer identities |
| 2 — Baseline | 1,158 fixed chunks, persistent Chroma/SQLite index; cited B0/B0-R dev/test runs, paired pools, source checks and abstention | Independent human grading remains optional |
| 3 — Hybrid/reranking | Persistent SQLite FTS5 BM25, RRF, dense-40 control and exact-pool B1-R; dev and final test comparisons complete | Preserve measured outcomes/defaults |
| 4 — Structure | 1,514 section chunks derived from canonical sources, bounded hierarchy and exact-seed B2a/B2 comparisons | Expansion stays experimental after measured regressions |
| 5 — Graph | 36 entities / 29 curated assertions / 14 papers, NetworkX persistence, original source links and bounded one-hop traversal; B3/B3-R dev/test checks complete | Non-blind curation and narrow coverage remain interpretation limits |
| Final evaluation | Nine verified test arms; all 279 structured claims and 517 citation links reviewed by the assistant; paired comparisons, usage, timing scopes and observed limitations reported | Complete with assistant judgments; independent human scores are not claimed |
| Delivery | Locked install and built wheel verified in isolation; full canonical reparse/source/evidence checks, one-paper live cited answer/abstention, four examples, acquisition/integrity helpers and selected-run archive delivered; temporary docs removed | Complete; other platforms and fresh downloads from every remote endpoint remain untested |

## Final measured comparison

Macro scores use 13 answerable test questions; two pre-existing negatives are scored separately. Complete coverage is based on sparse original gold spans, not independent semantic accuracy.

| Arm | Gold-span P@5 | Group recall@5 | Complete final | Complete candidate |
| --- | ---: | ---: | ---: | ---: |
| B0 | 0.1077 | 0.4103 | 5/13 | 10/13 |
| B0-R | 0.2154 | 0.8077 | 10/13 | 10/13 |
| B0-40 | 0.1077 | 0.4103 | 5/13 | 11/13 |
| B1 | 0.1692 | 0.7308 | 9/13 | 11/13 |
| B1-R | 0.2308 | 0.8846 | 11/13 | 11/13 |
| B2a | 0.1692 | 0.7692 | 9/13 | 10/13 |
| B2 | 0.1692 | 0.6923 | 8/13 | 10/13 |
| B3 | 0.2308 | 0.8590 | 10/13 | 11/13 |
| B3-R | 0.2000 | 0.8462 | 10/13 | 11/13 |

B1-R has the strongest span coverage in this matrix. Section chunks modestly improve group recall over unreranked hybrid; hierarchy displaces useful seeds, and graph recovers some sources while introducing a regression. B3-R restores test08's span coverage but demotes FedMD on test11 and q-FFL/Ditto on test13. The graph's five-question development gain does not establish independent generalization. Defaults remain dense-20 with reranking off; hierarchy/graph remain explicit experiments. No default was selected using these test results.

The source audit finds grounded but incomplete comparisons and useful alternative passages that receive no sparse gold-span credit. It also records two partially supported structured claims and one unsupported citation pair. Complementary partial citations are distinguished from unsupported sources. Review is non-blind and by the assistant; labels remain source-verified with `human_review_complete: false`. No failure quota or invented error applies.

See the [final report](final_evaluation.md), [structured results](final_evaluation_summary.json), [claim/citation audit](final_answer_audit.json) and immutable [input protocol](final_evaluation_protocol.json). The development reports remain separate: [baseline](evaluation.md), [hybrid](hybrid_development.md), [structure](structure.md) and [graph](graph.md).

## Artifact and verification status

- Fixed index: `6f8ba8be92dcc84b51a5514f`; section index: `679098a5db4830ef644dd3ad`; graph: `d3b352f901862f55267baad8`. Active fixed/section pointers remain independent.
- Models: `claude-haiku-5-5`, 2,048-dimensional `voyage-4-large`, optional `rerank-3`. Pinned Voyage tokenizer revision: `bb931c2635a93efe400c24741363d8ff61d7bb32`.
- All 55 frozen input hashes, nine run hashes, canonical source references, final evidence budgets and recomputed scores validate. Exact replay pairing, BM25/RRF, hierarchy/graph expansion and reranker mappings reproduce locally with hosted calls blocked.
- All 84 offline tests, Ruff lint/format and whitespace checks pass. The additional three tests protect download byte identity and cleanup; application code is unchanged. PyMuPDF emits upstream SWIG deprecation warnings under Python 3.13.
- Costs remain null while pricing is unconfigured. Replay timing excludes upstream work and is not full-pipeline latency. No hosted calls were made during result verification/source auditing.
- No new Typer commands were introduced for final evaluation. The user committed evaluation as `75ffd4c` with author/committer date `2026-10-16T23:40:51+05:00`; delivery changes are separate from that evaluation commit. The temporary delivery checkout was removed after verification; built packages and recorded evidence remain available.

Historical commits remain `2dfcd59` (Phase 3), `509beaf` (Phase 4) and `cb95b06` (Phase 5), created by the user with the requested dates. Source modules/functions have descriptions; README Section 5 explains the Python files. Course/video requirements and MCP implementation remain excluded. Temporary `docs/` notes were consolidated into the README/reports and removed. The nine final test runs remain in `artifacts/runs/` and the portable archive; 14 older runs were pruned. See [delivery checks](delivery.md) and [examples](examples.md).
