# Phase 5 — Evidence-linked graph

Phase 5 complete: implementation, B3 exact-seed development comparison and paired B3-R comparison verified, 2026-10-24. Phase 4 was committed first as `509beaf`, with both author and committer dates `2026-09-01T18:56:06+05:00`.

## What is implemented

**Mental model:** the question names an entity; one-hop relations point to verified original passages; those passages join the existing retrieval pool. Graph labels guide navigation and never replace evidence sent to Claude.

The graph uses the plan's curated fallback, avoiding a second extraction model/prompt and extraction API cost. `data/graph_curated.json` contains explicit aliases and assistant-reviewed assertions from original method/experiment descriptions. It covers 14 of the 40 papers, with 36 entities: 14 methods, 12 techniques, six problems and four datasets. There are 29 assertions: 13 `uses`, 11 `addresses` and five `evaluated_on` relations. The other papers remain searchable through dense/BM25/hierarchy retrieval.

All assertions and aliases were reviewed by the assistant against canonical text; this is not independent human review or comprehensive automatic extraction. Curation occurred after development results were known, so it is not a blind selection. Benchmark files are not extraction inputs, and held-out questions were not used to select assertions. Treat subsequent five-question dev comparisons cautiously; do not infer generalization from them.

`Entity` and `Relation` contracts validate types and require exact original quotes, block character spans, paper IDs and document versions. Only method→technique, method→problem and method→dataset assertions are allowed. Source code checks the provenance and schema; the semantic assertion is manually curated. Reference-list text, missing/altered quotes, stale versions, unknown entities, ambiguous aliases and quotes without a complete supporting indexed chunk are rejected. No numeric `outperforms` or universal method rankings are inferred.

Aliases match case/punctuation-normalized whole phrases, longest first. For example, “extended MNIST” resolves to EMNIST without also matching MNIST; “EMNIST versus MNIST” can resolve both. No fuzzy merging or model-based entity linking is implemented. Named methods can still be ambiguous outside this domain.

## Persistence and source links

NetworkX 3.7 is installed; the locked dependency supports the project's Python versions. The directed multigraph retains separate assertions and source evidence instead of overwriting a shared entity pair. It is serialized through explicit `edges="edges"` node-link JSON, following the [NetworkX API](https://networkx.org/documentation/stable/reference/readwrite/generated/networkx.readwrite.json_graph.node_link_data.html).

Snapshot: `artifacts/indexes/679098a5db4830ef644dd3ad/graph.json`.

Graph ID: `d3b352f901862f55267baad8`; curation hash: `15930dfb201a9db7cebb2acf6d46ea93a1223050577f75ed7bf839211f7842ba`.

Identity binds schema, curated inputs, index ID and chunk fingerprint. Loading revalidates every assertion against current SQLite sources and rejects changed inputs or altered snapshots. The existing indexed SQLite `chunk_spans` table resolves graph spans to complete supporting chunks; edge attributes retain block/span, quote, paper/version, section, page and chunk IDs. No duplicate graph-link database or Neo4j service is added. Restoring an older graph requires its matching curated input version and index. Curated inputs are the extraction artifact; the content hash replaces any need for a model-extraction cache.

Both active index pointers, original block/parse IDs, chunk indexes and benchmark labels remain unchanged. Graph construction/reload requires no PDF reparse, embedding or generation call.

## Bounded retrieval and paired comparisons

B3 preserves B2's section index and hierarchy settings, then adds graph navigation. It resolves at most four query entities, visits at most 12 incident relations in one hop and selects at most six original supporting chunks. Both incoming and outgoing incident assertions are usable; the stored relation direction is preserved. Newly reached entities are not traversed recursively. Paper/year/method and section filters apply before edge/passage selection. Two explicitly matched endpoints take priority; remaining edge ties use stable relation IDs.

Local BM25 ranks only verified support passages from those bounded relations. If none matches lexically, deterministic relation-support order is used. The first existing candidate stays first, graph supports follow, and remaining candidates fill the list up to 40. Support scores inherit the first anchor's score; BM25 is recorded separately and is not added to RRF. New support can be added or existing support promoted; displaced IDs are traced. This simple ordering can also add noise or crowd out useful evidence, so quality is not assumed.

Shared source-overlap deduplication, optional `rerank-3` and final up-to-five/4,000-Voyage-token packing follow. Reranking and Claude receive original chunk text, never graph-label summaries. Traces include `graph_expansion.identity`, matched entities, full traversed assertion provenance, base candidates, support selections/reasons and dropped IDs. `graph_base_metrics` scores the pre-graph pool; existing seed/candidate/final diagnostics retain their meanings.

The fresh B3/B3-R order is: **dense + BM25 → RRF (40) → hierarchy (40) → graph (40) → source deduplication → optional reranking → final evidence (5 / 4,000 tokens) → Claude**. The query's explicit aliases drive graph navigation; entities are not extracted from the 40 retrieved texts. Existing support passages are promoted; absent ones are added, displacing low-ranked base candidates if necessary. For the paired B3-R run, the saved post-graph pool replaces all stages before deduplication.

### Deduplication and identifiers

RRF merges identical chunk IDs across searches; expansion also keeps IDs unique. The later [source deduplicator](../src/fedresearch/retrieval/evidence.py#L19) handles different IDs sharing original text: walk the current ranking, keep the first chunk, and drop a later chunk if its source-character intersection with any kept chunk is at least 50% of the smaller chunk's source length. Intersections count only matching original block IDs. For example, 450 shared characters out of a smaller 800-character chunk gives 56.25%, so the later chunk is dropped. This is neither token overlap nor semantic similarity; similar sentences in different papers are not duplicates by this rule. It runs after both expansions and before reranking. Skipped IDs/reasons and the surviving input order are saved in the trace.

Evaluation run IDs are random `uuid4().hex` values, independent of date or score. Chunk IDs are deterministic: `paper_id:parse_id:cNNNNN:text_hash` for fixed chunks and `paper_id:parse_id:scNNNNN:text_hash` for section chunks. The zero-based ordinal is within that paper's policy output; the final eight hex characters hash its text. For example, `fedavg:b2992067bda5ce59:sc00009:02a20bbd` is the tenth section-policy chunk in that FedAvg parse. The parse hash includes PDF checksum, parser/configuration and PyMuPDF version; changing these can change IDs. Reranking preserves chunk IDs; `E1`–`E5` are separate per-answer citation labels assigned after packing.

The existing `--seed-source` now accepts B2→B3: B2's exact post-hierarchy candidate pool and hierarchy trace are reused, with no query embedding, initial dense/global BM25 search or hierarchy re-expansion. Local graph-support BM25 still runs. For B3-R, `--candidate-source` reuses B3's exact final merged pool and both expansion traces, skipping all retrieval/expansion before reranking. Compatibility checks include index, labels/questions, prompt/settings and graph identity. Timing scopes distinguish these replays from fresh searches.

### Exactly what seed replay reuses

For B2→B3 with answers, let `T = records[i].answer.trace.retrieval` in the source `run.json`:

| Source field | Reuse |
| --- | --- |
| `T.candidates[*].chunk_id` and `.score`, in array order | The full post-hierarchy pool, before source deduplication/final evidence selection; 40 candidates per question in this pair |
| `T.rankings.dense[*]` and `T.rankings.bm25[*]` | Ordered chunk IDs and scores retained for tracing; rank numbers are reconstructed from array position |
| `T.structural_expansion` | The complete saved hierarchy trace, including original hybrid seeds, context selections and dropped IDs; hierarchy is not rerun |

Chunk text and provenance are loaded by ID from the matching current SQLite index. The source run's final five `answer.evidence` items, answer/claims, model usage/timing and query embeddings are not reused. The question comes from the current benchmark; graph expansion, source deduplication, evidence packing and Claude generation run again. Index, split, label hash, settings, question IDs/text, prompt hash, filters and fusion/lexical identities are compatibility checks, not configuration overrides. The source run ID plus SHA-256 of its file are recorded in the new root `seed_source`. See [the loader](../src/fedresearch/evaluation/runner.py#L87).

For the earlier B2a→B2 path, the same candidate/ranking fields are loaded from B2a, then hierarchy runs. For B3-R, `--candidate-source` instead freezes B3's final merged pool and preserves both expansion traces; both hierarchy and graph expansion are skipped.

## Verified B3 development results

Run `7fcb25b480c44aabb7f2d053810d27ac` uses B2's exact saved pools, component rankings and hierarchy trace. All five graph expansions and final-pool replays reproduce locally; all candidate/base/seed/final metrics, relation provenance, citation IDs, source spans and budgets validate. Models, prompt, graph/index identity and benchmark hashes match, and the held-out freeze remains valid. Verification made no hosted calls or changes to prompts, labels, graph inputs or retrieval code.

| Five-question diagnostic | B2 | B3 |
| --- | ---: | ---: |
| Gold-span precision@5 | 0.160 | 0.360 |
| Evidence-group recall@5 | 0.467 | 1.000 |
| Complete coverage@5 | 2/5 | 5/5 |
| Candidate group recall | 0.933 | 1.000 |
| Candidate complete coverage | 4/5 | 5/5 |
| Execution failures | 0 | 0 |
| Exploratory required-point review / 2 | 1.80 | 2.00 |

| Question | B2 recall@5 | B3 recall@5 | B3 precision@5 | Observation |
| --- | ---: | ---: | ---: | --- |
| dev01 | 1 | 1 | 0.20 | Original mechanism evidence retained; a source-backed introduction passage is added. |
| dev02 | 1 | 1 | 0.20 | Both proximal-term benefits remain covered. |
| dev03 | 0 | 1 | 0.20 | Graph promotion restores the original SCAFFOLD mechanism passage to final evidence. Mime also enters the context; the answer explicitly excludes it from the SCAFFOLD explanation. |
| dev04 | 0 | 1 | 0.40 | Both original FedProx/SCAFFOLD gold passages are promoted into final evidence. |
| dev05 | 1/3 | 1 | 0.80 | Mechanism evidence is promoted and the missing EMNIST protocol passage is added. |

There are 11 graph support selections: five additions and six promotions, all selected with local BM25. Five low-ranked base candidates are displaced at the cap. Graph-base metrics reproduce B2's candidate metrics exactly; the previously absent EMNIST protocol is the new covered candidate group. Source-overlap deduplication leaves **40, 40, 39, 40 and 38** candidates for dev01–dev05 respectively; B3-R reranked exactly these same passages.

All five answer texts were reviewed against the unchanged expected points, with targeted checks of cited method/experiment passages. The same narrow required-point rubric gives `[2, 2, 2, 2, 2]`. In particular, dev05 now names all three EMNIST controlled factors; its cited experiment text/caption supports the logistic-regression target of 0.5 test accuracy. However, its final evidence no longer includes the simulated setup/results, and the answer explicitly flags that gap. Dev03 marks itself partial because it lacks the explicit update equation. Full gold-span coverage and full required-point credit therefore do not guarantee a fully complete answer, correctness or groundedness on every claim.

This is a post-run assistant review, not independent human grading or an exhaustive claim audit. The curated graph was built after dev outcomes were known, and some curated assertions use the same original source passages as the annotations. These results demonstrate navigation within that curated scope on five dev questions; they do not establish generalization to the held-out set or unseen questions.

B3 used **zero query embeddings/reranking calls** and **five Claude responses: 26,316 input / 3,402 output tokens**. Sum of question times was **25.23 seconds**, including **0.22 seconds** of graph selection/packing. Evidence totals were 2,088–2,851 Voyage tokens. Timing excludes the original embedding/search/hierarchy work, so it is not a direct end-to-end speed comparison. Pricing remains unconfigured. Exact hashes, protocols, per-question results, usage, source checks and review notes are in [graph_development_summary.json](graph_development_summary.json).

## Verified paired B3-R development results

Run `0618efd188e8459ea9c66960d905c9c0` reuses B3's exact candidate IDs/order/scores, component rankings, hierarchy/graph traces and identical deduplicated reranker inputs. Index, graph, models, prompt, labels and final budgets match; the only configuration change is enabling reranking. All returned indices, scores and original-rank mappings validate. Replaying the recorded reranker order reproduces every final evidence item without hosted calls. All citations/source spans, metrics and the unchanged held-out freeze validate.

| Five-question diagnostic | B3 | B3-R |
| --- | ---: | ---: |
| Gold-span precision@5 | 0.360 | 0.200 |
| Evidence-group recall@5 | 1.000 | 0.667 |
| Complete coverage@5 | 5/5 | 3/5 |
| Candidate group recall | 1.000 | 1.000 |
| Candidate complete coverage | 5/5 | 5/5 |
| Execution failures | 0 | 0 |
| Exploratory required-point review / 2 | 2.00 | 1.80 |

For dev01–dev05, B3-R supplies 1, 1, 1, 0 and 2 gold-relevant chunks respectively: P@5 is `(1 + 1 + 1 + 0 + 2) / 25 = 0.20`. Its group recall is `(1 + 1 + 1 + 0 + 1/3) / 5 = 0.667`; three questions cover all required groups. Candidate coverage stays complete because the pool is unchanged.

| Question / annotated support | Rank before reranking | Reranked rank | Effect at the final-five limit |
| --- | ---: | ---: | --- |
| dev04 / FedProx mechanism | 4 | 9 | Removed from final evidence |
| dev04 / SCAFFOLD mechanism | 3 | 11 | Removed from final evidence |
| dev05 / SCAFFOLD mechanism | 2 | 6 | Removed from final evidence |
| dev05 / EMNIST protocol | 3 | 12 | Removed from final evidence |

Deduplication is identical in the pair; these changes occur during reranking. All five B3-R answers were reviewed against expected points with targeted cited-source checks. Dev03 gives an explicit consistent correction/update equation. Dev04 still explains both methods using other supported passages despite receiving zero exact gold-span credit. Dev05 explains the correction and qualitative simulated results, but omits all three EMNIST protocol factors and marks the real-data detail gap. Its annotated experiment passage was available in the pool but ranked below the cutoff. The narrow required-point rubric is `[2, 2, 2, 2, 1]`; this assistant review is not independent human grading or an exhaustive claim audit. Sparse gold-span scores do not count every semantically useful passage.

B3-R used **zero query embeddings/searches/expansions**, **five reranking calls / 102,403 reranking tokens**, and **five Claude responses / 27,258 input / 4,420 output tokens**. Sum of question times was **30.41 seconds**, including **2.68 seconds** of reranking; evidence totals were 2,290–2,805 Voyage tokens. Its timing excludes the original retrieval and both expansions. These small replays do not establish end-to-end latency or stable speed differences. Pricing remains unconfigured.

**Decision:** Phase 5's engineering/development gate is complete. Keep B3 without reranking as the better measured graph configuration on these five dev questions; optional reranking improved B1 but regressed B3, so no universal benefit is assumed. Defaults remain dense-20 with reranking off; B3/B3-R remain explicit experiments. The graph curation is non-blind, and generalization remains untested. Final held-out comparisons and delivery verification are next.

## Verification and walkthrough

**81 offline tests pass**, with Ruff/format and whitespace checks. Tests cover invalid quotes/versions/types, missing complete evidence, parallel assertions, snapshot/input tampering, alias boundaries/overlap, one-hop and candidate limits, filters/empty scopes, fresh retrieval, exact B2→B3 seed replay and B3→B3-R final-pool replay. The reranker receives only indexed source texts. All Python functions/modules have descriptions.

The real graph is already built and reloaded locally. Every relation's quote and full supporting chunks validate. Compatibility checks and local integration smoke checks passed for all five B2 saved pools, with embeddings/dense search/hierarchy re-expansion blocked. These are plumbing checks, not new quality measurements. No hosted model call or new held-out evaluation was made. See [graph_preflight.json](graph_preflight.json).

New Typer command, for reproduction (local only):

```bash
uv run fedresearch graph-build --config configs/experiments/b3_graph.yaml
```

Completed B3 step, using the exact verified B2 pools:

```bash
HF_HOME=work/hf-cache uv run fedresearch evaluate --config configs/experiments/b3_graph.yaml --split dev --with-answers --seed-source artifacts/runs/d57813b4495b4ed299f6bb47c07bacb1/run.json
```

Completed paired B3-R step, run `0618efd188e8459ea9c66960d905c9c0`, using B3's exact final merged pool:

```bash
HF_HOME=work/hf-cache uv run fedresearch evaluate --config configs/experiments/b3_graph_rerank.yaml --split dev --with-answers --candidate-source artifacts/runs/7fcb25b480c44aabb7f2d053810d27ac/run.json
```

Both hosted results and cited answers are reviewed. Verification made no additional hosted calls or changes to prompts, labels, graph inputs or retrieval code. Keep the original defaults and the recorded Phase 4/5 regressions intact. MCP remains outside project scope.
