# Final evaluation and analysis

**Complete — 2026-10-26 (Asia/Tashkent).** Seven new test runs and two preserved baseline runs cover 135 successful question executions, with zero execution failures. All saved structured claims/citations have an assistant source audit. No further hosted comparisons are planned for this stage. Delivery verification and documentation consolidation are recorded separately in [delivery checks](delivery.md).

Hybrid search plus reranking (B1-R) has the strongest gold-span retrieval results in this matrix: complete coverage on 11/13 answerable questions versus dense-20's 5/13. This is a retrieval result, not an independent human answer-accuracy estimate. Section chunks modestly improve group recall over unreranked hybrid; bounded hierarchy reduces it, and the curated graph recovers some missing evidence while introducing a regression. Reranking the graph pool does not improve complete coverage. Defaults remain dense-20 with reranking off; no settings were tuned on these results.

## Inputs, stages and controls

The immutable [input protocol](final_evaluation_protocol.json) was recorded after implementation commit `cb95b06`, before the seven new runs. It records 55 source/configuration/dependency/input file hashes, resolved settings, both indexes, graph identity, prior run hashes and preflight checks. The mutable [results summary](final_evaluation_summary.json) records all nine run hashes, per-question metrics, replay checks, rank changes, usage and source-audit totals.

- **Corpus:** 40 unchanged PDFs / 937 pages. Fixed index `6f8ba8be92dcc84b51a5514f` has 1,158 chunks; section index `679098a5db4830ef644dd3ad` has 1,514.
- **Models:** `voyage-4-large`, 2,048 dimensions, for document/query embeddings; `claude-haiku-5-5` for answers; `rerank-3` only in paired reranking arms. All arms share the answer prompt and generation settings.
- **Candidate retrieval:** Chroma cosine dense search. B0 uses up to 20 dense candidates; B0-40 uses 40. B1/B2a search up to 40 dense and 40 local SQLite FTS5 BM25 hits, fuse with `sum(1/(60+rank))`, and cap at 40.
- **Hierarchy:** B2 reuses B2a's exact fused seeds and adds local adjacency/parent/child context, bounded by three anchors, two selections each and six overall, retaining cap 40.
- **Graph:** B3 reuses B2's exact post-hierarchy pool/trace. Graph `d3b352f901862f55267baad8` has 36 entities / 29 curated assertions from 14 papers. Traversal matches at most four query entities, visits 12 one-hop relations and selects six original supporting chunks, retaining cap 40.
- **Selection:** source overlap of at least half the smaller span triggers deduplication. Optional reranking receives the query and every surviving passage's text; returned input indices map back to original chunk IDs. Dense scores/IDs are not reranker inputs. B1-R receives/returns 40 passages per question; B3-R receives/returns 38–40 (594 total). Final packing follows ranking and sends up to five chunks within 4,000 passage tokens to Claude. Every recorded question has five chunks.
- **Tokenizer:** `voyageai/voyage-4-large`, revision `bb931c2635a93efe400c24741363d8ff61d7bb32`. Local passage counts exclude prompt formatting; provider billing usage is reported separately.

B0/B0-R and B1/B1-R and B3/B3-R hold candidate pools fixed to isolate reranking. B2a→B2 holds fused seeds fixed; B2→B3 holds post-hierarchy seeds fixed. Fresh dense-40/B1 searches are budget-matched but are not identical source pools; their saved dense rankings match on 12/15 questions. B1→B2a changes chunk policy and its derived indexes, preserving source annotations/models/budgets. Fresh generation can vary even with an unchanged prompt.

## Retrieval results

Macro averages use **13 answerable questions**. Two pre-existing negatives are excluded from positive-evidence scores and assessed for abstention. One item must cover at least 50% of a gold passage's raw characters in the original block to cover its group; separate subthreshold items are not combined. Precision@5 counts matching items / 5; group recall counts covered required groups / all required groups; complete coverage requires every group. Candidate coverage applies the same rule before reranking/packing. Sparse gold spans are diagnostics rather than exhaustive semantic relevance labels.

| Arm | Retrieval | Gold-span P@5 | Group recall@5 | Complete final | Complete candidate |
| --- | --- | ---: | ---: | ---: | ---: |
| B0 | Dense 20, fixed | 0.1077 | 0.4103 | 5/13 | 10/13 |
| B0-R | B0 exact pool → rerank | 0.2154 | 0.8077 | 10/13 | 10/13 |
| B0-40 | Dense 40, fixed | 0.1077 | 0.4103 | 5/13 | 11/13 |
| B1 | Hybrid, fixed | 0.1692 | 0.7308 | 9/13 | 11/13 |
| B1-R | B1 exact pool → rerank | 0.2308 | 0.8846 | 11/13 | 11/13 |
| B2a | Hybrid, section chunks | 0.1692 | 0.7692 | 9/13 | 10/13 |
| B2 | B2a exact seeds → hierarchy | 0.1692 | 0.6923 | 8/13 | 10/13 |
| B3 | B2 exact pool → graph | 0.2308 | 0.8590 | 10/13 | 11/13 |
| B3-R | B3 exact pool → rerank | 0.2000 | 0.8462 | 10/13 | 11/13 |

All nine runs abstain on **both negatives (18/18 answers)** with zero structured claims, and none fully abstains on an answerable question (0/117). Those successful abstentions are not execution failures. There were no failed attempts or post-test setting changes in this final seven-run sequence.

The per-question group recalls show which effects are retained or lost; exact covered group IDs and gold ranks are in the structured summary.

| Question | B0 | B0-R | B0-40 | B1 | B1-R | B2a | B2 | B3 | B3-R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| test01 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| test02 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| test03 | 0.000 | 1.000 | 0.000 | 1.000 | 1.000 | 1.000 | 0.000 | 1.000 | 1.000 |
| test04 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| test05 | 0.000 | 0.500 | 0.000 | 0.000 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 |
| test06 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 | 1.000 | 1.000 |
| test07 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| test08 | 0.000 | 1.000 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 1.000 |
| test09 | 0.000 | 1.000 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| test10 | 0.000 | 1.000 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| test11 | 0.000 | 1.000 | 0.000 | 0.500 | 1.000 | 0.500 | 0.500 | 1.000 | 0.500 |
| test12 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| test13 | 0.333 | 0.000 | 0.333 | 0.000 | 0.000 | 0.000 | 0.000 | 0.667 | 0.000 |

## What each comparison shows

| Change | Observed effect on final group coverage | Interpretation |
| --- | --- | --- |
| B0 → B0-40 | Final metrics unchanged; complete candidate coverage 10→11/13 | More candidates do not ensure better final-five selection. Fourteen of fifteen final chunk lists are identical; answers are fresh generations. |
| B0-40 → B1 | Complete final 5→9/13; recall improves on test03/08/09/10/11 and regresses on test13 | Lexical rank fusion improves selection without changing covered candidate groups. |
| B1 → B1-R | Complete final 9→11/13; recall improves on test05/06/11, with no recall regression | Exact-pool reranking promotes the FedBN, SCAFFOLD and FedMD sources from ranks 6/17/9 to 1/2/1. |
| B1 → B2a | Recall 0.731→0.769; complete final stays 9/13, candidate complete 11→10/13 | Section chunks help test05's feature-shift group but lose some candidate gold-span coverage. The final precision average is unchanged. |
| B2a → B2 | Complete final 9→8/13; candidate groups unchanged | Hierarchy interleaving moves test03's annotated FedAvg source from rank 5 to 8. It also adds a second matching item for test10 without covering a new group. |
| B2 → B3 | Complete final 8→10/13, candidate complete 10→11/13; recall improves test03/06/11/13 and regresses test08 | Original graph support promotes missing sources, including FedMD, but test08's FedOpt passage moves from rank 5 to 6. |
| B3 → B3-R | Complete final stays 10/13; recall 0.859→0.846, precision 0.231→0.200 | The exact 594 reranker inputs preserve candidate coverage. Test08 improves, while test11/test13 regress: FedMD moves 3→35, q-FFL 2→9 and Ditto 3→20. |

B0-R's historical dense-pool replay also improves final coverage from 5→10/13. This does not imply that reranking benefits every pool: B3-R regresses aggregate recall despite fixed candidates. The core research question receives **mixed evidence** here: preserving sections alone modestly raises span recall; the implemented hierarchy expansion does not establish an additional benefit. The curated graph helps this particular ladder, but its narrow, non-blind coverage limits the inference.

## Assistant answer/source audit

The [full audit](final_answer_audit.json) records **135 answers, 279 structured claims and 517 claim–citation pairs**, with run hashes, claim text, passage/chunk IDs, pages and a rationale for every judgment. It is a non-blind assistant review, not independent human grading, and does not replace the earlier targeted development/historical reviews.

Correctness is 0 for a wrong core answer, 1 for a missing required point or material error, and 2 when all required points and comparison constraints are correct. Relevance/completeness is 0 for failing to address the request, 1 for addressing part, and 2 for directly covering all expected points. Means use 13 positives; generator sufficiency labels are not scores.

Groundedness requires all assertions in a structured claim to follow from the combined provided evidence. A **strict citation pair** counts as fully supported only if that individual passage supports the whole compound claim. Complementary/partial citations are recorded separately. This fine-grained conservative convention was made explicit during review, not independently preregistered; it can penalize legitimate complementary citations and is sensitive to claim granularity. Support ratios are micro counts, and are null for zero-claim negative answers.

| Arm | Correctness /2 | Relevance /2 | Fully grounded claims | Fully supporting citation pairs | Partial pairs | Unsupported pairs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| B0 | 1.769 | 1.769 | 32/32 | 31/59 | 28 | 0 |
| B0-R | 1.846 | 1.846 | 31/31 | 38/60 | 22 | 0 |
| B0-40 | 1.692 | 1.692 | 31/31 | 30/54 | 24 | 0 |
| B1 | 1.846 | 1.846 | 28/29 | 27/55 | 27 | 1 |
| B1-R | 1.846 | 1.846 | 29/29 | 37/64 | 27 | 0 |
| B2a | 1.846 | 1.846 | 32/32 | 36/59 | 23 | 0 |
| B2 | 1.769 | 1.769 | 32/32 | 35/57 | 22 | 0 |
| B3 | 1.846 | 1.846 | 31/31 | 34/48 | 14 | 0 |
| B3-R | 1.769 | 1.846 | 31/32 | 31/61 | 30 | 0 |

The review finds 277/279 fully supported structured claims; two are partial. The B1 MOON answer includes a previous-model/same-input mechanism not fully established by its supplied excerpts. B3-R's test03 answer calls a pseudocode weight a local example count, although that excerpt defines it from a collection of minibatches; this extra claim also lowers correctness. One B1 test04 citation supplies no proximal-mechanism support, while a different cited passage supports that claim. The remaining 217 non-full citation pairs have partial support, often because one long claim combines facts from different passages. These counts are not a prose-wide hallucination rate: unstructured factual remarks in limitations are outside the frozen structured-claim denominator.

**Retrieval credit and answer support differ.** B2a/B2/B3-R explain FedMD using its original method passage despite missing its annotated abstract span. Several SCAFFOLD/FedOpt answers also explain requested mechanisms from alternative sources with zero gold-span credit. Conversely, all arms leave test05's original FedAvg non-IID comparison incomplete, and none supplies the requested original AFL target-mixture formulation on test13. An answer can be well grounded yet incomplete.

## Usage and timing

All arms generate 15 Claude responses. Cells list requests / provider-reported input tokens for embedding/reranking, and input / output tokens for Claude. Seconds are summed question execution times, not a throughput benchmark or clean-environment wall clock.

| Arm | Query embeddings: calls / tokens | Reranking: calls / tokens | Claude tokens: input / output | Seconds | Measured scope |
| --- | ---: | ---: | ---: | ---: | --- |
| B0 | 15 / 275 | 0 / 0 | 92,920 / 8,210 | 64.46 | Full pipeline |
| B0-R | 0 / 0 | 15 / 181,734 | 93,760 / 8,001 | 58.41 | Rerank + answer |
| B0-40 | 15 / 275 | 0 / 0 | 92,915 / 8,042 | 66.54 | Full pipeline |
| B1 | 15 / 275 | 0 / 0 | 93,530 / 8,715 | 68.76 | Full pipeline |
| B1-R | 0 / 0 | 15 / 365,151 | 93,891 / 7,243 | 60.59 | Rerank + answer |
| B2a | 15 / 275 | 0 / 0 | 81,125 / 7,772 | 67.45 | Full pipeline |
| B2 | 0 / 0 | 0 / 0 | 80,064 / 8,048 | 54.22 | Hierarchy + answer |
| B3 | 0 / 0 | 0 / 0 | 77,458 / 8,035 | 54.85 | Graph + answer |
| B3-R | 0 / 0 | 15 / 287,090 | 78,222 / 7,910 | 61.85 | Rerank + answer |

The seven new runs account for 45 query-embedding calls, 30 reranking calls and 105 Claude responses; the two historical controls add 15 embedding, 15 reranking and 30 Claude calls. B1-R spends 7.62 seconds in reranking; B3-R spends 6.22. B2's local hierarchy/retrieval/packing takes 0.98 seconds; B3's graph/retrieval/packing takes 0.33. Local final passage totals fall from B2a's 37,471 to B2's 37,146 and B3's 35,204 Voyage tokens, but prompts and billing totals differ.

**Replay timing omits upstream work.** Candidate replay skips embedding/search/expansion; seed replay skips the initial searches and any inherited expansion. These are controlled stage measurements, not faster full pipelines. Do not sum replay latencies as a measured end-to-end run or compare them directly with fresh-run time. Cost remains null because deployment pricing is unconfigured. The indexes were reused; indexing usage is outside these query-evaluation totals.

## Observed limitations and follow-up

These are observed cases, not a required failure quota. Saved outputs remain unchanged; no fix was applied using test results.

- **Missing source pool:** test05 lacks the annotated original FedAvg non-IID passage; test13 lacks original AFL target-mixture evidence. Larger final context or reranking alone cannot recover a source absent from the bounded candidate pool. A future development experiment could test explicit subquestion searches and cross-paper evidence selection.
- **Selection displacement:** hierarchy pushes test03's needed source below five; graph displaces test08; graph-pool reranking demotes FedMD to 35 on test11. Future development work could compare preserving strong seeds or source-diverse packing within the same budget, on new or development questions.
- **Incomplete synthesis:** some test13 answers describe only q-FFL and a secondary AFL account; others recover Ditto but still omit the original mixture formulation. Complete gold-span coverage is neither necessary nor sufficient for a semantically complete answer.
- **Source interpretation/citation granularity:** the local-count ambiguity and complementary compound citations show why valid citation IDs alone are not semantic validation. Future development work could test smaller factual claims and explicit source qualifiers without altering these recorded results.

The benchmark has only 13 positives and two negatives, with sparse source passages and source-verified labels rather than independent human review. Some queries naturally have alternative supporting passages. Baseline test outputs had already been inspected on 2026-10-17; this prior exposure is disclosed. Graph inputs were curated after development outcomes were known and overlap some gold source passages; construction was not blind and covers only 14 papers. These are controlled comparisons on this existing frozen set, not independent generalization estimates or statistically significant rankings. Fixed settings do not guarantee immutable provider model snapshots or deterministic generation. PDF equations/tables remain parsing limitations. No default/model/prompt/label/graph change is justified solely by this test matrix.

## Run identities and reproducibility

| Arm | Saved run ID | Provenance |
| --- | --- | --- |
| B0 | `81929cc51c1e4dbfb8c747a7547bc416` | Reused historical |
| B0-R | `31200136e531442788c1df1c0a21b052` | Reused historical |
| B0-40 | `dd189c43bc14486db8b105f45b897a59` | New final test |
| B1 | `da9ec3ae738341c4813504c8ab368ba2` | New final test |
| B1-R | `b34ebe340a77429889e77c38d18137c1` | New final test |
| B2a | `ad00dc64d3ad44daab5cf8d85259ae93` | New final test |
| B2 | `9ae5b228cdc64c93bb4df7a2a0990701` | New final test |
| B3 | `84a5e1f05cf348aeaa58709714a72b3f` | New final test |
| B3-R | `771cbc25fe9d4c9ca09a71b888f24d96` | New final test |

Each raw run is at `artifacts/runs/<run_id>/run.json`; SHA-256 values are in the structured summary. Local verification recomputes all final/candidate metrics, checks source spans/text/citations and budgets, and reproduces final packing from saved pools. Dedicated checks reproduce BM25/RRF and hierarchy/graph expansion from recorded upstream inputs. All inherited pools/traces and 600 B1-R / 594 B3-R index-score mappings validate, with hosted calls blocked. Historical settings are normalized with added default fields for compatibility; their recorded raw settings hashes and original run files remain unchanged. All 55 frozen input hashes and nine raw-run hashes were checked again at completion. All 81 offline tests, benchmark validation, Ruff lint/format and whitespace checks pass; PyMuPDF emits only its existing SWIG deprecation warnings.

To reproduce hosted results, use the existing `evaluate --config ... --split test --with-answers` commands for `b0_dense_40.yaml`, `b1_hybrid.yaml` and `b2a_section.yaml`. Feed each newly generated source run into its corresponding `--candidate-source` or `--seed-source` step exactly as in the stage table above. Use test sources for test comparisons, not dev runs. Reproduction makes new model calls and produces new run IDs/answers; the original measurements stay preserved. No reparse, reindex, label refreeze or new Typer command was needed for this evaluation stage.

The complete matrix, source audit, observed limitations and setup references are recorded. Delivery subsequently verified the isolated setup/workflow, prepared source-linked examples and consolidated/removed temporary documentation; see [delivery checks](delivery.md).

## Delivered evidence and benchmark rules

The nine selected raw tests are preserved byte-for-byte in [final_runs.zip](final_runs.zip), with the archive checksum in [final_runs.sha256](final_runs.sha256) and per-arm run hashes in the structured summary. [verify_delivery.py](../scripts/verify_delivery.py) checks the 55 frozen inputs, archive/run bytes, final span scores and assistant-audit arithmetic without model calls or rebuilt indexes. Candidate source-span replay and expansion provenance were verified against the original indexes during analysis; rebuilding those indexes is needed to repeat those deeper checks. Semantic judgments remain the recorded assistant review rather than something the verifier regrades. Local `artifacts/runs/` now retains these nine tests; 14 older exploratory/development runs were removed during delivery. Historical metrics/reviews remain in their labeled reports.

Benchmark annotation fields are `answerable`, `expected_points`, required `evidence_groups` with acceptable original quotes/spans, comparison constraints and annotation status. They are evaluation references, not training labels, and never enter the generation prompt. `benchmark freeze` hashes every byte of `test.jsonl` into `frozen.json`, records a UTC timestamp/status/human-review flag and checks all original spans. Test execution recomputes that hash and rejects a mismatch. It does not lock the file or freeze settings, PDFs or model weights; those identities are recorded separately. Current labels remain source-verified, with no independent human review. The historical source-ID migration is complete. Do not refreeze labels or change relevance rules after inspecting outcomes to force a gain.

Candidate metrics score the bounded source-deduplicated pool before reranking/packing. `--seed-source` copies ordered candidate IDs/scores, component ranks and inherited hierarchy traces from B2a→B2 or B2→B3; it does not reuse final evidence, answers, vectors, usage or latency. `--candidate-source` holds the final merged pool and inherited traces fixed for reranking. Index/split/question/prompt/label/settings/fusion identities are compatibility checks rather than overrides; source run ID and SHA-256 identify each replay. Query embeddings are not stored in the raw run.

When reporting future runs, keep failed attempts visible and include the scored count next to the expected positive denominator. The CLI averages successful positives; if failures occur, also report a conservative average counting failed positives as zero rather than silently omitting them. Correct negative abstention is a successful answer behavior. Use development questions or a new benchmark for future tuning.

Delivery installation, live smoke attempts, cleanup and source-linked demonstrations are recorded separately in [delivery checks](delivery.md) and [examples](examples.md). The original protocol, test runs, labels and measured results above remain unchanged.
