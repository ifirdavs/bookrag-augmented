# Baseline benchmark and evaluation protocol

The target is five development questions and fifteen held-out questions. Question labels reference canonical blocks rather than chunks, so later chunk policies can use the same annotations. A question's evidence groups describe required facts; each group contains one or more acceptable source passages with paper/version/parse/page, a raw-text span, and an exact quote.

Annotations are prepared from original source text independently of the retriever. `source_verified` means the quote and its supporting fact were checked against canonical text; it does not assert independent human review. Review source passages and expected points before setting `annotation_status: human_reviewed`. Test labels are frozen at their source-verified version and must not be used for tuning. The freeze explicitly records that independent human review has not occurred. No benchmark selection was based on retrieval output.

Here, “labels” means the reference annotations used to judge each question: `answerable`, `expected_points`, `evidence_groups` (required facts plus acceptable paper/version/parse/page/block spans and exact quotes), comparison constraints and annotation status. These are evaluation references; they are not model-training labels and are not included in the generation prompt. `data/benchmarks/dev.jsonl` contains five development questions and `data/benchmarks/test.jsonl` contains fifteen held-out questions.

`benchmark freeze` validates the test annotations and their original-source spans, rejects draft labels, computes SHA-256 over the **entire test.jsonl file**, and writes that hash to `data/benchmarks/frozen.json` under the key `test.jsonl`. It also records a UTC timestamp, annotation statuses and whether every item was independently human-reviewed. The current freeze is source-verified with `human_review_complete: false`. Before any test evaluation, `require_frozen` recomputes the hash and requires equality. Any byte change, including whitespace, invalidates the recorded hash. This is an integrity check, not a filesystem lock: the file remains editable, and this command does not freeze dev labels, model weights, settings or PDFs. Corpus/settings identities are tracked separately. After an intentional pre-evaluation source-ID migration, validate and freeze the new version; do not edit/refreeze held-out labels to improve observed scores.

```bash
uv run fedresearch benchmark validate
# Source-verified labels were refrozen after migration on 2026-10-17:
uv run fedresearch benchmark freeze
uv run fedresearch evaluate --config configs/experiments/b0_dense.yaml --split dev
uv run fedresearch evaluate --config configs/experiments/b0_dense.yaml --split dev --with-answers
# Only after all settings are fixed and labels are frozen:
uv run fedresearch evaluate --config configs/experiments/b0_dense.yaml --split test --with-answers
```

The baseline runner saves each question's evidence, candidates, filters, index/configuration, timings, and optional generated answer under `artifacts/runs/<run-id>/run.json`. Its optional `--candidate-source` flag verifies the source B0 index, label hash, split, question IDs, prompt and settings; only the reranking enable flag may differ. It then replays the exact original candidate IDs/order/cosine scores through shared deduplication/ranking/packing and answer generation. The run records source-run identity/hash; replay timings omit original query embedding/search and must not be compared as full end-to-end latency. Claude is skipped only when no evidence fits the scope/budget. Failures remain explicit and cause a nonzero CLI exit. It does not supply automatic human answer scores.

Every evaluation report must spell out the retrieval stages: Chroma dense cosine search with 2048-dimensional `voyage-4-large` embeddings retrieves up to 20 candidates; source-overlap deduplication follows. B0 selects up to five chunks by dense rank. B0-R uses `rerank-3` to reorder every deduplicated candidate, then selects up to five. The reranking API receives the query string and a list of candidate texts, not chunk IDs, embeddings or dense scores. IDs resolve texts locally from SQLite; returned input indices are mapped back to those IDs. Dense cosine scores remain in the trace as `original_score`, while `score` in each reranking result is the new reranker relevance score. Both development runs had 20 candidates after deduplication; the reranker returned all 20 and evidence packing selected five. Both enforce the same 4,000-token passage-text budget. Report counts before/after deduplication, final evidence counts and the actual tokenizer/revision. Current defaults use `voyageai/voyage-4-large` revision `bb931c2635a93efe400c24741363d8ff61d7bb32`; the historical report used `cl100k_base`. These counts exclude prompt formatting and are separate from provider-reported billing usage.

The corrected 40-paper / 1,158-chunk index and all four B0/B0-R development/test runs are verified (40 answer executions, zero failures). Dense/paired reranked held-out gold-span P@5 is 0.1077/0.2154, group recall 0.4103/0.8077 and complete coverage 5/13 versus 10/13. Both modes abstain on both designated unanswerables. Full counts, per-question results, usage, run hashes and limitations are in [the report](../reports/evaluation.md) and [structured summary](../reports/evaluation_summary.json). An exploratory post-run assistant review reads all 40 answers against expected points, with targeted cited-source checks; its relevance scores are not independent human correctness/support scores. The original model/prompt/settings and frozen labels remained unchanged throughout the held-out comparison.

The tokenizer/parser migration updated only parse/block IDs after verifying all 26 original gold passages against unchanged PDF hashes/versions, raw text, page coordinates, quotes and offsets. Both splits validate and the new test freeze is valid; original annotations remain backed up in ignored `work/`. The following local migration commands were completed before evaluation:

```bash
HF_HOME=work/hf-cache uv run python work/migrate_benchmark_sources.py --apply
HF_HOME=work/hf-cache uv run fedresearch benchmark validate
HF_HOME=work/hf-cache uv run fedresearch benchmark freeze
```

The existing negatives remain source-scoped (a BLEU score in the unchanged original SCAFFOLD paper) or refer to an absent paper (`FedQuantum-X`); the 20 additions do not supply those requested results. Questions, expected points, groups, quotes, offsets and annotation statuses are preserved. Both test modes have now been run once; their outputs were read after settings/labels were fixed. Do not silently reuse stale references or rewrite historical metrics.

The initial machine relevance rule is at least 50% coverage of a gold passage's raw character span in one retrieved evidence item. Matching IDs/offsets is necessary, but a human must adjudicate whether a partial overlap includes the required fact. Overlapping retrieved source passages are deduplicated before scoring.

- Precision@5 counts relevant evidence items divided by five, including missing slots in the denominator.
- Evidence-group recall@5 counts covered required groups divided by all required groups.
- Complete coverage@5 is one only when every required group is covered.

For each answerable question, a group is covered if **one** of the first `k` evidence items covers at least 50% of the raw characters in **any one** of that group's alternative gold passages, matching the original block ID. Overlapping spans within that evidence item are unioned to avoid double counting; separate evidence items each covering less than 50% are not combined. Multiple hits on the same group still count once, and one evidence item may cover multiple groups. Thus `evidence_group_recall_at_k = covered groups / required groups` and `complete_coverage_at_k = int(covered groups == required groups)`. Macro complete coverage is the fraction of answerable questions with every group covered.

The per-question counts behind the current development results are:

| Question | Relevant chunks B0 / B0-R | Covered groups B0 / B0-R | Required groups |
| --- | ---: | ---: | ---: |
| dev01 | 1 / 1 | 1 / 1 | 1 |
| dev02 | 2 / 2 | 1 / 1 | 1 |
| dev03 | 0 / 1 | 0 / 1 | 1 |
| dev04 | 0 / 0 | 0 / 0 | 2 |
| dev05 | 1 / 3 | 1 / 3 | 3 |

Every run supplies five chunks per question. Precision counts unique matching evidence items, while group recall counts each required group once. For example, both E1 and E2 in dev02 cover all 349 characters of the same annotated passage: precision is 2/5 but group recall is 1/1.

```text
B0 P@5       = (1/5 + 2/5 + 0/5 + 0/5 + 1/5) / 5 = 0.16
B0-R P@5     = (1/5 + 2/5 + 1/5 + 0/5 + 3/5) / 5 = 0.28
B0 recall    = (1 + 1 + 0 + 0 + 1/3) / 5 = 0.466666...
B0-R recall  = (1 + 1 + 1 + 0 + 1) / 5 = 0.80
B0 complete  = (1 + 1 + 0 + 0 + 0) / 5 = 0.40
B0-R complete= (1 + 1 + 1 + 0 + 1) / 5 = 0.80
```

These are macro averages over the five answerable development questions. Annotations are in `data/benchmarks/dev.jsonl`; the per-question score fields are `records[].precision_at_k`, `records[].evidence_group_recall_at_k` and `records[].complete_coverage_at_k` in the two saved development `run.json` files. `covered_groups` records which required facts received overlap credit. Recomputing from saved evidence/spans reproduces all of these fields.

For dev05, the three required groups are mechanism, simulation and real experiments. B0 covers one of three (recall 1/3, complete coverage 0); B0-R covers all three (recall 1, complete coverage 1). These metrics use the evidence supplied to Claude, including chunks it may not cite. They are calculated from source-character overlap, independently of vector/reranker scores or Claude's sufficiency label.

Unanswerable questions have no positive evidence groups; positive-evidence retrieval metrics are null. Score their abstention separately.

For generated answers, record correctness (0–2 against expected points), supported substantive claims / all substantive claims, supported citations / all citations, correct abstention on negatives, and false abstention on positives. Review comparisons for matching experimental conditions and source-qualified claims.

Keep parser, corpus, fixed chunks, embeddings, generator, prompt, top-k and evidence budget fixed for B0/B1. Structural and graph modes are later work. Do not infer semantic retrieval performance from synthetic integration tests, nor count mocked provider calls as hosted measurements.

Failure analysis uses actual observations, with no quota. Do not deliberately impair a retrieval mode to create failure examples. Unsupported questions test correct abstention, which is a successful result. Measure answer relevance as how directly and completely the answer addresses the question against its expected points, alongside correctness, groundedness and citation support.

Initial live B0 and paired B0-R development results are recorded in [reports/evaluation.md](../reports/evaluation.md). The historical paired check replays the exact saved B0 candidate IDs/order/scores rather than re-embedding questions. New comparisons can use the built-in option:

```bash
HF_HOME=work/hf-cache uv run fedresearch evaluate \
  --config configs/experiments/b0_dense_rerank.yaml --split dev --with-answers \
  --candidate-source artifacts/runs/640d302142b1483cb256139526f5a3bc/run.json
```

The current source run has passed compatibility checks; local replay reproduces all five dense evidence lists exactly with zero hosted-model calls. One independent reranking run changed the dense ordering for dev04 and was excluded from the controlled comparison. Scores remain sparse-gold-span diagnostics; independent semantic adjudication is still needed. The 15 held-out questions have now been queried once for B0. The paired B0-R test has also completed with exact candidate pools and unchanged settings. Do not retune models, prompt, retrieval budgets, annotations or relevance rules on these test outcomes; keep the runs as the fixed baseline for subsequent comparisons. Assistant review is exploratory and not blind or independent; see the report for the 0–2 relevance rubric, per-question judgments and unscored correctness/support limitations.
