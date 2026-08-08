# Baseline benchmark and evaluation protocol

The target is five development questions and fifteen held-out questions. Question labels reference canonical blocks rather than chunks, so later chunk policies can use the same annotations. A question's evidence groups describe required facts; each group contains one or more acceptable source passages with paper/version/parse/page, a raw-text span, and an exact quote.

Annotations are prepared from original source text independently of the retriever. `source_verified` means the quote and its supporting fact were checked against canonical text; it does not assert independent human review. Review source passages and expected points before setting `annotation_status: human_reviewed`. Test labels are frozen at their source-verified version and must not be used for tuning. The freeze explicitly records that independent human review has not occurred. No benchmark selection was based on retrieval output.

```bash
uv run fedresearch benchmark validate
# To freeze reviewed/source-verified annotations (already done for the initial version):
uv run fedresearch benchmark freeze
uv run fedresearch evaluate --config configs/experiments/b0_dense.yaml --split dev
uv run fedresearch evaluate --config configs/experiments/b0_dense.yaml --split dev --with-answers
# Only after all settings are fixed and labels are frozen:
uv run fedresearch evaluate --config configs/experiments/b0_dense.yaml --split test --with-answers
```

The baseline runner saves each question's evidence, candidates, filters, index/configuration, timings, and optional generated answer under `artifacts/runs/<run-id>/run.json`. Failures remain explicit and cause a nonzero CLI exit. It does not supply automatic human answer scores.

The initial machine relevance rule is at least 50% coverage of a gold passage's raw character span in one retrieved evidence item. Matching IDs/offsets is necessary, but a human must adjudicate whether a partial overlap includes the required fact. Overlapping retrieved source passages are deduplicated before scoring.

- Precision@5 counts relevant evidence items divided by five, including missing slots in the denominator.
- Evidence-group recall@5 counts covered required groups divided by all required groups.
- Complete coverage@5 is one only when every required group is covered.
- Unanswerable questions have no positive evidence groups; positive-evidence retrieval metrics are null. Score their abstention separately.

For generated answers, record correctness (0–2 against expected points), supported substantive claims / all substantive claims, supported citations / all citations, correct abstention on negatives, and false abstention on positives. Review comparisons for matching experimental conditions and source-qualified claims.

Keep parser, corpus, fixed chunks, embeddings, generator, prompt, top-k and evidence budget fixed for B0/B1. Structural and graph modes are later work. Do not infer semantic retrieval performance from synthetic integration tests, nor count mocked provider calls as hosted measurements.

Failure analysis uses actual observations, with no quota. Do not deliberately impair a retrieval mode to create failure examples. Unsupported questions test correct abstention, which is a successful result. Measure answer relevance as how directly and completely the answer addresses the question against its expected points, alongside correctness, groundedness and citation support.

Initial live B0 and paired B0-R development results are recorded in [reports/evaluation.md](../reports/evaluation.md). The paired check replays the exact saved B0 candidate IDs/order/scores rather than re-embedding questions. One independent reranking run changed the dense ordering for dev04 and was excluded from the controlled comparison. Scores remain sparse-gold-span diagnostics; independent semantic adjudication is still needed. The 15 held-out questions have not been queried.
