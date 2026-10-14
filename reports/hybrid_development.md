# Phase 3 — Hybrid retrieval results

Complete, 2026-10-22. BM25/RRF, optional reranking, the matched development comparisons and an exploratory assistant answer review are verified. All runs use the same 40 papers / 1,158 fixed chunks, Voyage 4 Large embeddings, Claude Haiku 5.5, answer prompt and source-span labels. No held-out questions were rerun or used for tuning.

## Main development results

| Five-question macro diagnostic | Dense-40 | B1 hybrid | B1-R, exact B1 pool |
| --- | ---: | ---: | ---: |
| Gold-span precision@5 | 0.160 | 0.200 | 0.280 |
| Evidence-group recall@5 | 0.467 | 0.533 | 0.800 |
| Complete coverage@5 | 2/5 | 2/5 | 4/5 |
| Candidate group recall | 1.000 | 0.900 | 0.900 |
| Candidate complete coverage | 5/5 | 4/5 | 4/5 |
| Execution failures | 0 | 0 | 0 |
| Exploratory assistant relevance / 2 | 1.80 | 1.80 | 1.80 |

| Configuration | Saved run |
| --- | --- |
| `b0_dense_40.yaml` | `f4be2b88c53e42998e1fc7c88c605eaf` |
| `b1_hybrid.yaml` | `0bd7c449468a4a11b0f7fac4a9d72df5` |
| `b1_hybrid_rerank.yaml`, replaying B1 | `f0945144613e412f877f41ec22e8f065` |

Exact hashes, protocols, per-question metrics, usage and review notes are in [hybrid_development_summary.json](hybrid_development_summary.json). Full answers/evidence/traces are retained in each local `artifacts/runs/<run-id>/run.json`. The index is `6f8ba8be92dcc84b51a5514f`; development-label SHA-256 is `9318d9aa89601583ba6cb2237b97651133b885459db4a2383e1ab598f50f1ca3`.

## Retrieval and verification

Dense-40 takes up to 40 Chroma cosine hits. B1 takes up to 40 dense and 40 SQLite FTS5 BM25 hits, sums `1 / (60 + rank)` per appearance, and caps the fused list at 40. Source-overlap deduplication follows. B1-R sends the deduplicated passages and question to Atlas `rerank-3`, which returns every candidate reordered. All modes select up to five final chunks within 4,000 Voyage passage-text tokens; the actual runs selected five chunks totaling 2,999–3,000 tokens per question. RRF combines ranks; raw dense and BM25 scores are not added together.

The existing index command built `bm25.sqlite` for all 1,158 chunks in 0.70 seconds with embedding calls blocked, preserving the dense index and vectors. Its metadata pins chunk/index identity, SQLite version, the `unicode61 remove_diacritics 0` analyzer and built-in BM25 parameters. No extra dependency or Typer command was added.

The B1-R replay's source-run hash matches B1. All five pools, IDs/order/scores, component rankings, source references, prompts and settings match exactly, except `reranking.enabled`. Each pool retained 40 passages after deduplication; reranking returned all 40 without truncation. There were **zero query-embedding requests and no new dense/BM25 searches**. Candidate coverage is unchanged. All candidate/final metrics were recomputed, reranker index/rank/score mappings validated, final evidence repacked exactly, and citation IDs/source provenance checked locally without hosted calls. The test-label freeze remains valid.

Dense-40 and B1 are separate live searches: their dense components differ for dev01/dev04 and match exactly for the other three questions. Re-fusing BM25 with the saved control dense lists preserves every B1 final selection and candidate metric, although the two complete fused pools differ. Thus the original dense/hybrid comparison is not mislabeled as sharing exact dense inputs. The B1/B1-R pair does share its entire pool exactly.

## Per-question coverage and observed limits

| Question | Dense-40 group recall | B1 group recall | B1-R group recall | B1-R precision@5 |
| --- | ---: | ---: | ---: | ---: |
| dev01 | 1 | 1 | 1 | 0.20 |
| dev02 | 1 | 1 | 1 | 0.40 |
| dev03 | 0 | 0 | 1 | 0.20 |
| dev04 | 0 | 0 | 0 | 0.00 |
| dev05 | 1/3 | 2/3 | 1 | 0.60 |

Hybrid's final retrieval gain over dense-40 is on dev05. Reranking then improves dev03 and dev05, with the other three final group recalls unchanged. These are sparse gold-span diagnostics on five development questions, not general answer-accuracy measurements.

For dev04, the original annotated SCAFFOLD passage `scaffold:5698214a4f6e337e:c00000:4e3b989b` is at dense rank 28, absent from BM25 top-40 and at uncapped fused rank 43. The cap excludes it, leaving only the FedProx gold group available. Reranking cannot recover the missing passage. Nevertheless the answers describe both mechanisms from cited survey/non-IID/FedDyn passages outside the fixed original-source gold labels: zero gold-span credit is not zero semantic relevance. This is a measured candidate-coverage regression, not an intentionally introduced failure.

For dev05, B1-R retrieves all three annotated groups but its answer still omits two requested EMNIST experimental factors: varying local update counts and participating-client counts. It does describe varying client similarity. Its cited E3 passage, SCAFFOLD PDF p7 (`scaffold:5698214a4f6e337e:c00013:2f44ba39`), explicitly contains all three factors. Mentioning simulated K values does not supply the missing real-data factors. Retrieval success and the model's sufficient label do not guarantee a complete answer.

## Exploratory answer review

All 15 answer texts from dense-40, B1 and the controlled B1-R were read against unchanged expected points. Targeted checks inspected the cited FedAvg/FedOpt passages, FedProx's two-benefit passage, the SCAFFOLD algorithm and experiments, and the secondary comparison passages. This is a post-run, non-blind assistant review, not independent human grading or an exhaustive per-claim audit. The additional fresh-search reranked run is excluded from this paired review.

Reuse the previously documented relevance/required-point rubric: 2 when requested core facts are addressed, 1 when partly addressed, 0 when not addressed. Extra claims/source risks are noted separately; relevance is not correctness.

| Question | Dense-40 / B1 / B1-R relevance | Observation |
| --- | --- | --- |
| dev01 | 2 / 2 / 2 | All address local updates and server averaging. B1 adds unrequested FSVRG details and labels itself partial; B1-R focuses on FedAvg with an additional supported FedOpt interpretation. |
| dev02 | 2 / 2 / 2 | All state the statistical-heterogeneity and variable-local-work benefits. |
| dev03 | 2 / 2 / 2 | All address control-variate correction. Current B1-R uses the consistent gradient correction `c - c_i`; the historical B0-R verbal sign error is not repeated. |
| dev04 | 2 / 2 / 2 | Both mechanisms are explained from secondary evidence despite missing original gold-span credit. |
| dev05 | 1 / 1 / 1 | All describe correction and simulation/EMNIST but omit some requested real-data experimental factors, including in B1-R despite retrieving the source. |

Mean relevance stays **1.80/2 in all three modes**. The review does not establish an answer-quality gain from the improved retrieval scores. Original outputs, prompt and labels remain unchanged.

## Usage and timing

| Run | Query embedding calls / tokens | Reranking calls / tokens | Claude input / output tokens | Sum of question times |
| --- | ---: | ---: | ---: | ---: |
| Dense-40 | 5 / 80 | 0 / 0 | 31,365 / 3,768 | 30.19 s |
| B1 | 5 / 80 | 0 / 0 | 31,679 / 4,337 | 32.89 s |
| B1-R replay | 0 / 0 | 5 / 122,464 | 30,902 / 3,449 | 29.02 s, excludes source retrieval |

All three produced five Claude responses. Replay timings omit original query embedding/search/fusion. The reranking stage itself took 4.23 seconds across five questions. Adding B1's recorded retrieval time (2.87 seconds) to the replay yields a reconstructed 31.89-second workflow estimate, with a small duplicate deduplication/packing overhead; this is not a directly measured fresh run or evidence of stable speed improvement. Generation lengths and request latency vary. USD costs remain null because pricing is unconfigured; API-reported token usage is retained.

## Other preserved runs

The additional fresh-search B1-R run `207cb38716224ec6a2a56d116d1f5cb4` omitted candidate-source, made five query embeddings and changed one dev01 candidate. Four input pools match B1 exactly. Its P@5/recall/complete coverage are 0.28/0.80/4-of-5, but it remains a separate end-to-end result, not the primary paired comparison. It used 122,463 reranking tokens and 30,902/3,175 Claude input/output tokens; sum of question times was 35.10 seconds including fresh searches. Its complete provenance is retained in the structured summary and original run.

The earlier local top-20 diagnostic replayed original B0 run `640d302142b1483cb256139526f5a3bc`, added BM25 top-20, fused with cap 20 and made no hosted calls. It reproduced all five original B0 evidence selections. Dense/hybrid P@5 was 0.16/0.20, group recall 0.467/0.533, complete coverage 2/5 in both, and candidate recall 0.90/0.80. It is separate from the main cap-40 results. Exact component ranks, source hash, scores and procedure are in [hybrid_dev_replay.json](hybrid_dev_replay.json).

## Phase decision

Phase 3's engineering and development-evaluation gate is complete. Keep the original dense-20 default and reranking off in the core experiment ladder. B1/B1-R retain cap 40, RRF constant 60, top-five/4,000-token evidence limits; the optional reranked configuration has the strongest annotated retrieval in this small dev comparison, without an established relevance gain. No additional tuning, prompt/label changes or global reranking enablement is justified here. All 55 offline tests previously passed, including source provenance, lexical persistence/filters, empty lists, deterministic fusion and exact-pool replay; code is unchanged during this result verification.

Next is Phase 4: section-aware chunks and bounded hierarchy expansion, with separate structural comparisons and the same corpus/models/prompt/final budgets. Final held-out comparisons are pending. Temporary `docs/` notes remain until the agreed delivery consolidation. No new model calls, Typer commands, commits, pushes or publication were made during this verification.
