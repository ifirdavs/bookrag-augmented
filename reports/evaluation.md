# Initial live development results

Recorded 2026-10-15 (Asia/Tashkent). This is the Phase 2 baseline and an initial B0-R retrieval check, before hybrid/structural retrieval. The 15 held-out questions were not queried; their frozen hash is unchanged. No independent human answer scores are reported.

## Configuration and artifacts

- Corpus: 20 papers, 614 pages, 657 fixed chunks; 600-token windows / 100-token overlap using `cl100k_base`.
- Embeddings: Atlas `voyage-4-large`, 2048-dimensional float vectors; document/query input roles are explicit.
- Generation: Claude `claude-haiku-5-5`; current prompt identity recorded in answer traces: `607d28b135416421a91808e91b058341946adeb6e30a7690a43dab74c1002d46`.
- Retrieval: 20 dense candidates, source-overlap deduplication, final top 5, 4000 evidence tokens; automatic routing disabled.
- Optional reranking: Atlas `rerank-3`, same frozen candidates, no truncation, same final budget.
- Index: `da44ff5cde9177848b1ad969`; 392,830 reported embedding tokens / 21 successful calls / 20.21 seconds. Reload/reuse passed without additional embedding calls. All 20 source annotations resolve against its SQLite records.
- Development labels SHA-256: `f19d3bf6954f3dfcded8b1f2ed9aed41aea9b4fed6de4da0836a35bd302103fc`.
- Final B0 answer run: `31960e1721b54df681b95531b56453cd`.
- Paired retrieval-only B0-R replay: `f3aae18fddd6485b9c5af7fe11799408`, with `candidate_source_run_id` pointing to the B0 run.

Raw local records are in `artifacts/runs/<run-id>/run.json`; index records are under `artifacts/indexes/<index-id>/`. These generated artifacts are ignored by Git. The report preserves the measurements and identities; fresh runs can vary.

## Retrieval diagnostics

The rule is at least 50% overlap with an annotated original character span. These are **annotated-span diagnostics**, not independently adjudicated semantic precision or answer correctness. The gold passages are sparse: a different valid passage explaining the same fact may receive no overlap credit.

| Question | B0 span precision@5 | B0-R span precision@5 | B0 group recall@5 | B0-R group recall@5 | B0 model sufficiency |
| --- | ---: | ---: | ---: | ---: | --- |
| dev01 | 0.20 | 0.20 | 1.00 | 1.00 | sufficient |
| dev02 | 0.20 | 0.20 | 1.00 | 1.00 | sufficient |
| dev03 | 0.00 | 0.20 | 0.00 | 1.00 | sufficient |
| dev04 | 0.00 | 0.00 | 0.00 | 0.00 | partial |
| dev05 | 0.20 | 0.60 | 0.33 | 1.00 | sufficient |
| Macro mean (n=5) | 0.12 | 0.24 | 0.4667 | 0.80 | — |

Complete annotated-group coverage was 40% for B0 and 80% for the reranked replay. Both runs completed five questions with zero execution errors. The paired replay used 61,875 reranking tokens and made no query-embedding calls. It did not generate answers, so there is no paired answer-quality or total answer-latency claim. With five development questions, these results do not establish general superiority.

Candidate IDs, order and original scores were checked as exactly identical within each reported pair. An earlier independent B0-R run (`a6334356f54844689e3ff056184ee1c9`) changed the ordering/scores for dev04 on a fresh query-embedding call; it is excluded from this controlled comparison. Reusing saved candidates avoids attributing query-time variation to reranking.

## Answer and source checks

All five B0 responses passed structured-answer and citation-ID validation. The model marked dev01/dev02/dev03/dev05 sufficient and dev04 partial; these labels are model judgments, not human accuracy scores. Selected cited text was inspected against the indexed original passages. Required-fact and claim-support adjudication remains to be completed for final evaluation.

A separate, unscored smoke question asked for kilograms of CO2 measured in the original FedAvg experiments, with a FedAvg paper filter. The assistant returned insufficient evidence and zero claims instead of inventing a number. This successful abstention check is outside the frozen benchmark and did not alter its labels.

The answer prompt was refined once on development questions to reduce unrelated theory/results and to judge sufficiency against the information actually requested. The original answer run (`ab7a8f3ca04d46deba9b8bd862b537c9`) is retained. The final run above uses the refined prompt; retrieval settings and labels were unchanged.

Observed limitations:

- The B0 dev04 final evidence lacks the FedProx mechanism, so the answer cannot provide the full requested mechanistic comparison. The candidate pool contains more relevant source material than the final dense top 5. This is a real retrieval limitation to assess in the next phases.
- Dev03 receives zero gold-span credit although its answer cites SCAFFOLD's control-variate update description on PDF pages 4–5. Sparse gold spans therefore require semantic adjudication before treating overlap scores as relevance scores.
- Some responses still add unnecessary formula/proof qualifications. The free-text limitations field is not semantically validated; dev04's caveat names the missing proximal mechanism. Valid citation IDs alone do not prove that every sentence is supported by its packed evidence.
- Fixed chunks can cross sections/pages and contain fragmentary equations. No changes were made to invent failures or satisfy a reporting quota.
- USD costs remain null because prices/free-credit balances were not configured or queried. Reported token usage is not an invoice or account-credit measurement.

## Reproduction and next work

Run `uv run fedresearch index` to reuse/build the current index, then `uv run fedresearch evaluate --config configs/experiments/b0_dense.yaml --split dev --with-answers`. The B0-R config enables reranking for normal use. For a strict paired comparison, replay the saved B0 `trace.retrieval.candidates` through `deduplicate_candidates`, `VoyageReranker.rerank` and `pack_evidence` under the same budgets; a fresh retrieval call is not an exact replay.

Next implement BM25/RRF and section-aware retrieval against this saved baseline. Keep corpus, models, prompt, development/test split and final evidence budgets fixed. Leave held-out execution until the methods/settings are fixed. Review semantic support and sample answers before making final quality claims.
