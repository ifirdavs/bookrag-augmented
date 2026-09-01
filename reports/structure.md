# Phase 4 — Section-aware retrieval

Phase 4 implementation and development-evaluation gate complete, 2026-10-23. Section chunking improves annotated retrieval over B1 on these five development questions; bounded hierarchy interleaving then regresses final gold-span coverage. Keep expansion experimental. Phase 3 was committed first as `2dfcd59`, with both author and committer dates `2026-08-31T20:17:37+05:00` as requested. Phase 4 changes remain uncommitted.

## What changed

`indexing.chunk_policy: section` derives section-bounded windows from existing canonical blocks. It reuses the fixed chunker's pinned Voyage tokenizer, 600-token cap, 100-token within-section overlap target and original raw-source offsets. Oversized sections split into multiple chunks; short sections remain short. Heading-only windows are excluded, while their section nodes remain in the tree. Blocks, parse IDs, source versions, sections, paths and benchmark references are unchanged. No PDF reparse or label migration is needed.

B2a (`configs/experiments/b2a_section.yaml`) applies the existing dense/BM25/RRF search to these section chunks, without expansion or reranking. It isolates chunk boundaries relative to B1. B2 (`b2_structure.yaml`) uses the same index and adds bounded hierarchy navigation, without reranking, to isolate navigation relative to B2a.

**Mental model:** B2a searches passages that stay inside sections. B2 then looks at a few neighboring or directly linked section passages around strong hits, while keeping the same total candidate and answer budgets.

## Navigation rules and limits

B2 starts with up to 40 fused hybrid seeds. The first three are anchors. For each, consider only the immediately previous/next chunk within its section, the first content chunk of its direct parent, and the first content chunk of at most two direct children. No recursive traversal, whole-section/paper insertion or graph expansion occurs.

BM25 selects up to two matching neighbors per anchor from that small set, with at most six promotions/additions globally. If no neighbor matches lexically, only same-section adjacency is eligible as fallback. Missing parent content is skipped. Unclassified/fallback sections use adjacency only, without inferred parent/child navigation. Paper/year/method filters and section hints remain hard boundaries.

Selected context follows its anchor, inherits that anchor's RRF score and retains its original chunk ID/text/spans. The lexical score selects neighbors and is recorded separately; it is not added to RRF. Existing seed candidates may be promoted; new ones may be added. The merged list remains capped at 40, so context can displace lower-ranked seeds. Source-overlap deduplication, the shared optional reranker, and final up-to-five/4,000-Voyage-token packing follow. This is a simple explicit ordering policy, not a learned relevance score or full BookRAG implementation.

`trace.structural_expansion` records the original seed pool, budgets, reasons (`adjacent_chunk`, `parent_section`, `child_section`), originating seed/section, target section, selection/fallback, lexical score, promotion/addition and dropped seed IDs. Standard traces retain dense/BM25 ranks/scores and final candidates. Optional reranking still receives the merged deduplicated pool before packing; no additional B2-R experiment is introduced at this stage.

## Local corpus preflight

| Check | Result |
| --- | --- |
| Papers / existing sections / parent links | 40 / 955 / 430 |
| Section chunks | 1,514 |
| Voyage tokens: min / median / max | 9 / 499 / 600 |
| Total local passage tokens | 637,093 |
| Short chunks under 64 tokens | 45 |
| Heading-only windows excluded | 46 |
| Chunks in unclassified/fallback sections | 46 |
| Cross-section chunks | 0 |
| Expected structural index ID | `679098a5db4830ef644dd3ad` |
| Matching cached embeddings / expected batches | 0 / 48 at batch size 32 |
| Hosted requests during preflight | 0 |

All canonical files and source/parse identities remain unchanged. The fixed index's chunk fingerprint is identical, both benchmark splits' source quotes/spans validate, and the held-out freeze remains valid. All five evidence lists from each historical B0-20, dense-40 and B1 dev run reproduce exactly without model calls. Representative real-source navigation smoke checks trace context back to original blocks; they use manually selected anchors and are not retrieval-quality measurements. Details are in [structure_preflight.json](structure_preflight.json).

**67 offline tests pass**, including section boundaries/token limits/Unicode coverage, retained source IDs, omitted heading-only evidence, direct parent/child/adjacent operators, budgets/filters/fallback, independent fixed/section index pointers, exact seed replay, final structural-pool reranking replay and empty evidence. Ruff and whitespace checks pass. No new Python dependency or Typer command was added; `evaluate` gains the optional `--seed-source` argument.

## Development results

| Five-question macro diagnostic | B1: fixed chunks | B2a: section chunks | B2: exact B2a seeds + hierarchy |
| --- | ---: | ---: | ---: |
| Gold-span precision@5 | 0.200 | 0.240 | 0.160 |
| Evidence-group recall@5 | 0.533 | 0.733 | 0.467 |
| Complete coverage@5 | 2/5 | 3/5 | 2/5 |
| Candidate group recall | 0.900 | 0.933 | 0.933 |
| Candidate complete coverage | 4/5 | 4/5 | 4/5 |
| Execution failures | 0 | 0 | 0 |
| Exploratory assistant relevance / 2 | 1.80 | 1.80 | 1.80 |

B2a run `fca749fc1c0a4a7a81904e33978df1d5` uses the verified section index, up to 40 dense and 40 BM25 hits, RRF constant 60 and a 40-candidate merge cap. Source-overlap deduplication precedes selection of up to five chunks within 4,000 Voyage tokens. Both hierarchy expansion and reranking are disabled. Its settings match B1 after changing only the chunk policy; canonical corpus, labels, models, prompt, search caps and final budgets are unchanged. These are separate live searches over different chunk indexes, not identical candidate pools.

All five B2a BM25 lists and fused pools reproduce locally. Saved-pool replay reproduces every final evidence item exactly; all final/candidate metrics, citation IDs and original source spans validate. Benchmark hashes and the held-out freeze remain unchanged. B2 run `d57813b4495b4ed299f6bb47c07bacb1` uses all five exact saved 40-candidate B2a seed pools, including original IDs/order/scores and dense/BM25 component rankings. Models, prompt, labels, section index and final budgets are identical; only retrieval mode changes. Replaying both the seeds through local expansion and the final merged pools reproduces every B2 trace/evidence selection exactly. All expanded relations, source links, inherited scores, per-anchor/global budgets and recomputed seed/candidate/final metrics validate. No model API calls were made during verification, and no new held-out evaluation or prompt/label tuning occurred.

| Question | B1 group recall@5 | B2a group recall@5 | B2 group recall@5 | B2 precision@5 |
| --- | ---: | ---: | ---: | ---: |
| dev01 | 1 | 1 | 1 | 0.20 |
| dev02 | 1 | 1 | 1 | 0.20 |
| dev03 | 0 | 1 | 0 | 0.00 |
| dev04 | 0 | 0 | 0 | 0.00 |
| dev05 | 2/3 | 2/3 | 1/3 | 0.40 |

The final group-recall gain comes from dev03: its annotated SCAFFOLD control-variate passage now reaches rank five. For dev04, both annotated sources are available in the pool (SCAFFOLD rank 15, FedProx rank 23), but neither reaches the final five. Its answer still explains both mechanisms using other cited passages, including FedNova's FedProx summary; zero exact gold-span credit does not mean zero relevant evidence. It labels itself partial and adds an unrequested performance-comparison limitation.

For dev05, the section pool covers the mechanism and simulation groups but lacks the annotated EMNIST protocol passage, unlike B1's full candidate coverage for this question. The answer explains correction and simulated results, names extended MNIST, and appropriately marks real-data details unavailable in its supplied evidence. It omits the three expected real-data factors: local updates, participating clients and client similarity. This is a retrieval limitation in this run; it differs from B1-R's earlier omission despite receiving the protocol passage.

All five answer texts were read against the unchanged expected points, with targeted checks of cited mechanism/algorithm/experimental passages. Using the existing required-point relevance rubric gives `[2, 2, 2, 2, 1]`, mean **1.80/2**, unchanged from B1. This post-run assistant review is neither independent human grading nor an exhaustive claim-support audit. Sparse span labels and changing chunk boundaries also affect precision; improved retrieval diagnostics alone do not establish improved answer quality or generalization.

B2 makes 18 traced context selections across the five questions: 13 adjacent and five parent-section passages; seven are new additions and 11 promotions of existing candidates. No child-section or fallback selection occurs in these runs; their implementation is covered by local tests. Twelve context selections reach final evidence. Seven lower seeds are dropped at the candidate cap, but the covered gold groups remain unchanged for every candidate pool.

The final-score regression comes from interleaving context before other strong seeds. The annotated SCAFFOLD abstract passage moves from fused rank 5 to 8 for dev03 and from 4 to 7 for dev05. It remains in the candidate pool but falls outside final evidence. Dev04's two gold passages remain later in the pool (ranks 19/27 after expansion). The annotated real-data protocol remains absent for dev05; bounded expansion does not recover it. Thus this ordering adds context without increasing annotated group coverage and crowds out some already available gold evidence at the five-item limit.

All five B2 answers were also read against unchanged expected points, with targeted checks of FedAvg's one-step endpoint/averaging, the SCAFFOLD algorithm and Option II update, FedNova's FedProx summary and simulated results. Required-point relevance stays `[2, 2, 2, 2, 1]`, mean **1.80/2**. Dev03 still explains drift correction correctly using other original-source evidence despite zero abstract-span credit. Dev04 explains both mechanisms without B2a's unrequested performance-comparison caveat; dev01 adds an unnecessary convergence/performance qualification and labels itself partial. Dev05 still omits the real-data protocol and labels itself partial. These are observations from a non-blind assistant review, not an independent correctness/groundedness score or a demonstrated answer-quality improvement.

| Usage / timing | B2a fresh retrieval | B2 exact-seed replay |
| --- | ---: | ---: |
| Query-embedding calls / tokens | 5 / 80 | 0 / 0 |
| Claude responses | 5 | 5 |
| Claude input / output tokens | 27,205 / 3,811 | 28,038 / 3,176 |
| Reranking calls | 0 | 0 |
| Sum of question times | 25.63 s | 33.70 s |
| Retrieval or local expansion/packing | 2.37 s | 1.22 s |
| Final evidence tokens per question | 2,028–2,760 | 2,425–2,851 |

B2 timing excludes the original query embedding/dense/global BM25 searches; local neighborhood BM25 and expansion are included. Raw totals do not establish an end-to-end speed comparison, and generation latency varies. USD costs remain unconfigured. Exact hashes, per-question metrics, gold ranks, expansion traces, usage and review notes are in [structure_development_summary.json](structure_development_summary.json).

## Storage and reproducibility

The user completed the shared section-index build. Read-only verification confirms:

| Build check | Result |
| --- | --- |
| Active section index | `679098a5db4830ef644dd3ad` |
| Papers / chunks / vector dimensions | 40 / 1,514 / 2,048 |
| API embedding tokens / requests / cache hits | 636,094 / 48 / 0 |
| Build time | 41.27 seconds |
| Chroma IDs, vector metadata and finite/nonzero vectors | All valid |
| SQLite chunks and spans vs regenerated section chunks | Exact match |
| BM25 IDs and passage texts vs SQLite chunks | Exact match |
| Canonical papers, sections and blocks vs fixed index | Unchanged |
| Both benchmark splits / held-out freeze | Valid and unchanged |
| B2a/B2 settings | Identical except retrieval mode |

The local preflight's 637,093 passage-token estimate and the API's 636,094 reported input count are recorded separately. No model requests were made during verification. [structure_development_summary.json](structure_development_summary.json) records the verified build and both development runs; [structure_preflight.json](structure_preflight.json) preserves the earlier pre-build snapshot.

The fixed index `6f8ba8be92dcc84b51a5514f` remains selected by `artifacts/indexes/CURRENT.json`; `CURRENT_section.json` now selects the completed section index. Each index has its own Chroma vectors, `metadata.sqlite`, `bm25.sqlite` and `index.json`. B2a and B2 share the section index. Builds activate their own pointer only after success; a missing section index fails explicitly instead of querying fixed chunks. The existing embedding cache resumes successful batches after interruption.

1. Build once using the existing `index` command (completed; repeating reuses the saved index):

```bash
HF_HOME=work/hf-cache uv run fedresearch index --config configs/experiments/b2a_section.yaml
```

2. Run B2a on the five dev questions with answers (completed as `fca749fc1c0a4a7a81904e33978df1d5`):

```bash
HF_HOME=work/hf-cache uv run fedresearch evaluate --config configs/experiments/b2a_section.yaml --split dev --with-answers
```

3. Run B2 using that run's exact initial hybrid seeds, including the final `--seed-source` argument (completed as `d57813b4495b4ed299f6bb47c07bacb1`):

```bash
HF_HOME=work/hf-cache uv run fedresearch evaluate --config configs/experiments/b2_structure.yaml --split dev --with-answers --seed-source artifacts/runs/fca749fc1c0a4a7a81904e33978df1d5/run.json
```

`--seed-source` validates source index/policy, labels, questions, prompt/settings and reranking-off state, allowing only the hybrid→structure mode change. It skips query embedding and the initial dense/BM25 search, but still executes local bounded-neighbor BM25 selection/expansion. `--candidate-source` instead replays a final merged pool for optional reranking, preserving its expansion trace and skipping expansion. The two options cannot be combined. Reports distinguish `seed_source` from `candidate_source` and state timing scope.

The original `candidate_metrics` scores the final bounded deduplicated pool before reranking/packing. Structural runs also save `seed_candidate_metrics` for the unchanged initial pool. Final evidence uses the same canonical gold-span metric. B1/B2a measures chunking; the exact-seed B2a/B2 comparison measures navigation, with a separate cited-answer review. Models, prompt, final evidence limits and corpus remain fixed; leave new held-out evaluations to Phase 7.

## Phase decision

Phase 4's engineering and development-evaluation gate is complete: section chunks and bounded inspectable hierarchy navigation work, both indexes remain runnable, and fallbacks, budgets and source provenance are verified. The measured result is mixed: section chunking improves annotated final retrieval over B1 on five dev questions, while this hierarchy interleaving policy reduces it. Assistant required-point relevance stays unchanged. This does not establish a general benefit or harm from document hierarchy.

Retain B2 as an explicit experimental configuration; keep hierarchy expansion off by default. B2a is the better measured structural configuration. The existing dense-20 default and optional reranking settings remain unchanged. Do not alter prompts, labels or results to force an improvement. Any alternative context-ordering or reranking study should be a separately recorded development experiment. No additional hosted execution is required to close this phase. Phase 5's evidence-linked graph is the next planned implementation, when requested. No new Typer commands, commits or pushes occurred during this verification.
