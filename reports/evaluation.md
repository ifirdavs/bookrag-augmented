# Baseline evaluation and index builds

Phase 3 is complete (2026-10-22). The separate [hybrid report](hybrid_development.md) records dense-40/B1/exact-pool B1-R dev comparisons: P@5 0.16/0.20/0.28, group recall 0.467/0.533/0.800 and complete coverage 2/5, 2/5, 4/5. Targeted assistant relevance remains 1.8/2; retrieval gains are not an answer-accuracy claim. The B0/B0-R results below remain unchanged.

## Current 40-paper index, 2026-10-17

The 40-paper rebuild and all four B0/B0-R development/test runs are complete: **40 answer executions, zero execution failures**. Every paired run uses exactly the same original dense candidate IDs/order/scores, index, frozen question labels, prompt and settings except the reranking enable flag.

| Held-out result | Dense B0 | Paired reranked B0-R |
| --- | ---: | ---: |
| Gold-span precision@5 (13 answerables) | 0.1077 | 0.2154 |
| Evidence-group recall@5 | 0.4103 | 0.8077 |
| Complete annotated coverage | 5/13 (38.5%) | 10/13 (76.9%) |
| Designated unanswerables: abstention with zero claims | 2/2 | 2/2 |
| Exploratory assistant relevance, 0–2 | 1.77 | 1.85 |

This small benchmark shows a gain in annotated-source retrieval, not a universal performance or answer-accuracy result. Answer relevance was reviewed after execution by the assistant, using expected points and targeted source checks; it is **not independent human grading, blind review or exhaustive claim-support scoring**. One SCAFFOLD verbal sign error, missed requested details and cross-paper evidence gaps are retained in the analysis below. All generated answers and frozen labels remain unchanged. Structured per-question metrics, usage, run hashes and review judgments are saved in [evaluation_summary.json](evaluation_summary.json).

| Build item | Verified value |
| --- | --- |
| Corpus | 40 papers / 937 pages |
| Canonical content | 47,592 blocks / 955 sections / 1,158 fixed chunks |
| Parser and chunks | `pymupdf-columns-v4`; 600 Voyage-token cap / 100-token overlap target |
| Tokenizer | `voyageai/voyage-4-large`, revision `bb931c2635a93efe400c24741363d8ff61d7bb32` |
| Embeddings | Atlas `voyage-4-large`, 2048-dimensional floats, explicit document/query roles, truncation disabled |
| Active index | `6f8ba8be92dcc84b51a5514f` |
| Chunk fingerprint | `039e6518f7d4dcbc16457b366aee2068f4c46665fc73c46fd6f02998aa556124` |
| Build usage | 683,346 API-reported input tokens / 37 successful calls / zero cache hits |
| Build time | 34.77 seconds |
| Validation | All 1,158 vector IDs match source chunks; vectors have 2048 finite/nonzero dimensions; source identities, chunk fingerprint and all 26 benchmark passages validate |
| Labels | 5 dev / 15 test; only parse/block IDs changed during migration; new test freeze is valid; independent human review pending |
| Generation | Claude `claude-haiku-5-5`, unchanged prompt/settings |

The local preflight counted 684,492 passage-text tokens. API-reported usage is recorded as the actual embedding request usage. USD estimates remain null because pricing is not configured.

The new evaluation uses these fixed stages:

| Stage | B0 | B0-R paired comparison |
| --- | --- | --- |
| Fast retriever | Chroma cosine dense search using 2048-dimensional `voyage-4-large` query/document embeddings | Replay B0's exact saved candidate IDs, order and cosine scores |
| Candidate cap | Up to 20 | Same saved pool, up to 20 |
| Deduplication | Remove substantial source-span overlap | Same rule, before reranking |
| Evidence ordering | Dense cosine rank | `rerank-3` reorders every deduplicated candidate |
| Final evidence | Up to 5 chunks within 4,000 Voyage passage-text tokens | Same limits |
| Answer model and prompt | Claude Haiku 5.5; current saved prompt | Same model, settings and prompt |

Both five-question development answer runs are complete and their pre-reranking candidate pools are verified as exactly identical. Both fifteen-question held-out runs are complete with settings unchanged and exact shared pools. Report sparse gold-span diagnostics separately from adjudicated relevance/correctness/grounding. Keep the historical results below labeled with their original corpus and tokenizer.

## Current 40-paper paired development results

Run `640d302142b1483cb256139526f5a3bc` completed on 2026-10-17. Dataset SHA-256: `9318d9aa89601583ba6cb2237b97651133b885459db4a2383e1ab598f50f1ca3`. The unchanged answer prompt hash is `607d28b135416421a91808e91b058341946adeb6e30a7690a43dab74c1002d46`.

Every question retrieved 20 dense candidates; none were removed by source-overlap deduplication. Each answer received five evidence chunks totaling 2,999–3,000 Voyage tokens within the 4,000-token budget. The run made five successful query-embedding calls (80 API tokens) and received five Claude responses (31,365 input / 3,430 output tokens). Sum of per-question elapsed times: 23.67 seconds. The two providers' token counts use their own API accounting.

| Question | B0 span P@5 | B0-R span P@5 | B0 group recall@5 | B0-R group recall@5 | B0 complete | B0-R complete |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| dev01 | 0.20 | 0.20 | 1.00 | 1.00 | 1 | 1 |
| dev02 | 0.40 | 0.40 | 1.00 | 1.00 | 1 | 1 |
| dev03 | 0.00 | 0.20 | 0.00 | 1.00 | 0 | 1 |
| dev04 | 0.00 | 0.00 | 0.00 | 0.00 | 0 | 0 |
| dev05 | 0.20 | 0.60 | 0.33 | 1.00 | 0 | 1 |
| Macro mean (n=5) | 0.16 | 0.28 | 0.4667 | 0.80 | 0.40 | 0.80 |

The metric inputs are the `data/benchmarks/dev.jsonl` source annotations and each saved answer's five `evidence` items. At least 50% raw character-span coverage of an alternative annotated passage marks an evidence item relevant to a group. Unique relevant chunks by question are **[1, 2, 0, 0, 1]** for B0 and **[1, 2, 1, 0, 3]** for B0-R, giving P@5 macro means **(4/5)/5 = 0.16** and **(7/5)/5 = 0.28**. Required groups are **[1, 1, 1, 2, 3]**; covered groups are **[1, 1, 0, 0, 1]** versus **[1, 1, 1, 0, 3]**. Per-question recall averages are **(1 + 1 + 0 + 0 + 1/3)/5 = 0.4667** and **(1 + 1 + 1 + 0 + 1)/5 = 0.80**. Complete coverage averages are **(1 + 1 + 0 + 0 + 0)/5 = 0.40** and **(1 + 1 + 1 + 0 + 1)/5 = 0.80**. Two matching chunks can cover one group: dev02 E1 and E2 each cover all 349 annotated characters but the group counts only once. Full formulas and counts are also in [the evaluation protocol](../docs/evaluation.md).

Both runs passed the normal structured-answer and citation-ID/provenance checks for all five outputs. The sufficiency labels are model judgments, not independent accuracy scores. Gold annotations are sparse: dev03 cites SCAFFOLD's body/algorithm passages rather than its annotated abstract; dev04 cites explanations in other indexed papers and a SCAFFOLD body passage rather than the two annotated original passages. Zero gold-span overlap therefore does not establish that either answer is semantically irrelevant. B0 dev05 is marked partial and adds theory/derivation qualifications to an experiments question; required-fact and claim-support assessment is still pending. Labels, prompt and retrieval budgets were not changed in response to these results.

The shared evaluation command now supports `--candidate-source` for a controlled comparison. It checks the source index, dataset hash, split, questions, prompt and settings (only reranking enable may differ), then replays the exact saved dense candidate IDs/order/scores. Original run SHA-256: `966c549469de0f817a0fc9fa07ea6ed8aaf9b02f77cfad4af31daea813000dae`. A local replay reproduced all five B0 evidence lists exactly with zero query-embedding, reranking or generation calls. **50 offline tests passed**, including replay and incompatible-source checks.

```bash
HF_HOME=work/hf-cache uv run fedresearch evaluate \
  --config configs/experiments/b0_dense_rerank.yaml --split dev --with-answers \
  --candidate-source artifacts/runs/640d302142b1483cb256139526f5a3bc/run.json
```

Paired run `7cdba7ce2bb04c1aa1cf357c66bec81e` completed at `2026-10-17T18:07:33.096537+00:00`, SHA-256 `e60843ef2ccd497871eeaa40fbffe64efcf3e3f535b383dcc91579accce8aac0`. Its source-run hash, index, dataset and prompt were verified; all settings match B0 except `reranking.enabled`. Every saved candidate ID, original order and cosine score matches exactly. Each of the five reranker calls returned all 20 candidates reordered; the first five fit the 4,000-token budget (2,999–3,000 actual passage tokens). Recomputed source-overlap metrics match the saved scores, and final evidence/text/spans resolve to the indexed originals.

The paired run used **61,382 reranking tokens / five reranking calls**, **zero query-embedding calls**, and five Claude responses totaling **31,080 input / 3,563 output tokens**. Sum of per-question replay times: **25.48 seconds**. This excludes original query embedding/search and is not a full end-to-end retrieval time. Fresh Claude responses can vary even with the same model/prompt; candidate replay controls the retrieval pool, not generation randomness.

Both runs have four model-labeled sufficient answers and one partial answer, but the partial question changes from dev05 in B0 to dev04 in B0-R. Reranking covers the annotated SCAFFOLD mechanism in dev03 and all three dev05 groups. Dev04 still has no annotated-span credit; its response describes mechanisms from other indexed sources and adds caveats about missing full equations/formal convergence comparisons. No aggregate human answer accuracy or relevance improvement is claimed from these labels.

Source review found an actual answer issue in reranked **dev03, claim 2**: it prints the correct update `yi ← yi − ηl(gi(yi) − ci + c)` but then says the stochastic gradient is shifted by `ci − c`. The additive correction to that gradient is `c − ci`; the verbal description reverses the sign. Its cited E2 passage contains the correct algorithm on SCAFFOLD PDF page 4 (`scaffold:5698214a4f6e337e:c00007:b135d6af`). Citation-ID validity and gold-span retrieval coverage do not catch this semantic inconsistency. This is an observed model error, not an induced failure. Preserve the original output for evaluation; settings/prompt remain fixed for the current held-out comparison.

### Held-out protocol fixed before execution

The 15 test questions (13 answerable / 2 unanswerable) pass source validation and their freeze is unchanged: SHA-256 `38357d7d652df28e990a765917f926529dce3eb7360459f1e22ed05f4230b61f`. Current configurations match the development runs. B0 settings hash: `8a06a8c90ec0a1d0c3ca0600a21f0227195c7aa573ab5bc45b9096d8e114ccdc`; B0-R settings hash: `4cfccf96bc46c72774fad9f693cc95b37e5caef0473125dd07ec1e2ebebf0490`. Keep the same active index, tokenizer, prompt, generation settings, 20-candidate cap, deduplication, five-chunk/4,000-token budget and annotation-overlap rule. Execute B0 test answers first, then replay that test run's candidate pools for B0-R. Assess abstention separately on the two negatives; do not tune on held-out results. Both B0 and B0-R held-out executions completed under this protocol with unchanged configuration and frozen labels. No new hosted calls were made by the assistant while verifying the saved run and preparing the next step.

## Current 40-paper paired held-out results

Run `81929cc51c1e4dbfb8c747a7547bc416` completed at `2026-10-17T22:50:49.596467+00:00` (**2026-10-18 03:50:49 Asia/Tashkent**). All 15 questions completed without execution errors. Source-run SHA-256: `e0c0ba1d4cf24ec1cf7333bc2b05fd3540b1799f9661d5aa4535c87a91c6d18a`.

The dataset, index, full B0 settings and prompt hashes match the fixed protocol above. Canonical verification and recomputation of every saved metric passed. Each question retrieved 20 dense candidates, all survived source-overlap deduplication, and five chunks were sent to Claude (2,674–3,000 Voyage passage tokens, within the unchanged 4,000-token budget). No reranking was used.

| Question | B0 P@5 | B0-R P@5 | B0 group recall | B0-R group recall | Complete: B0 → B0-R |
| --- | ---: | ---: | ---: | ---: | ---: |
| test01 | 0.2000 | 0.2000 | 1.0000 | 1.0000 | 1 → 1 |
| test02 | 0.2000 | 0.2000 | 1.0000 | 1.0000 | 1 → 1 |
| test03 | 0.0000 | 0.4000 | 0.0000 | 1.0000 | 0 → 1 |
| test04 | 0.4000 | 0.4000 | 1.0000 | 1.0000 | 1 → 1 |
| test05 | 0.0000 | 0.2000 | 0.0000 | 0.5000 | 0 → 0 |
| test06 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0 → 0 |
| test07 | 0.2000 | 0.2000 | 1.0000 | 1.0000 | 1 → 1 |
| test08 | 0.0000 | 0.2000 | 0.0000 | 1.0000 | 0 → 1 |
| test09 | 0.0000 | 0.2000 | 0.0000 | 1.0000 | 0 → 1 |
| test10 | 0.0000 | 0.2000 | 0.0000 | 1.0000 | 0 → 1 |
| test11 | 0.0000 | 0.4000 | 0.0000 | 1.0000 | 0 → 1 |
| test12 | 0.2000 | 0.2000 | 1.0000 | 1.0000 | 1 → 1 |
| test13 | 0.2000 | 0.0000 | 0.3333 | 0.0000 | 0 → 0 |
| test14 | — | — | — | — | — |
| test15 | — | — | — | — | — |
| Macro mean: 13 answerables | 0.1077 | 0.2154 | 0.4103 | 0.8077 | 0.3846 → 0.7692 |

The denominator is **13 answerable questions**. The two unanswerables have null positive-retrieval metrics and are assessed separately. There are seven matching evidence chunks across 65 final answerable-query slots: P@5 = 7/65 = 0.1077. Per-question group-recall sum is 5 + 1/3, so macro recall = (5 + 1/3)/13 = 0.4103. Complete coverage occurs on test01, test02, test04, test07 and test12: 5/13 = 0.3846. Gold spans are sparse, so zero overlap does not establish semantic irrelevance.

Among the 13 answerables, the model marks ten sufficient and three partial (test05, test11, test13), with no full abstentions. These are model judgments, not independent correctness/relevance scores. Both designated unanswerables (test14 and test15) return **insufficient with zero claims**, matching the expected abstention behavior (2/2): no unsupported BLEU score or FedQuantum-X accuracy was invented. Full semantic claim/citation support review remains pending.

Usage: **15 query-embedding calls / 275 input tokens**, **15 Claude responses / 92,920 input and 8,210 output tokens**. Sum of per-question elapsed times: **64.46 seconds**, including retrieval and generation. All outputs passed the normal structured-answer/citation checks; no execution failures were discarded. API token counts belong to each provider's own accounting; nominal USD estimates remain null.

The paired run used the following command after all source questions, exact candidate pools, frozen test hash and comparison settings passed preflight:

```bash
HF_HOME=work/hf-cache uv run fedresearch evaluate \
  --config configs/experiments/b0_dense_rerank.yaml --split test --with-answers \
  --candidate-source artifacts/runs/81929cc51c1e4dbfb8c747a7547bc416/run.json
```

Paired run `31200136e531442788c1df1c0a21b052` completed at `2026-10-17T23:19:12.051558+00:00` (**2026-10-18 04:19:12 Asia/Tashkent**), SHA-256 `875acd3af3532077d6a119a5e0804456b1e97878aa6ff3639c8ac83ddedc1439`. The source-run hash matches `81929cc51c1e4dbfb8c747a7547bc416`. The index, test-label hash, prompt and full settings match the fixed development protocol, except reranking enable. All 15 original candidate pools match exactly, all 20 candidates per question were returned reordered, and all final text/spans and recomputed metrics validate. Each answer received five chunks totaling 2,674–3,000 Voyage tokens, under the unchanged 4,000-token cap. There were zero execution failures.

B0-R gold-span P@5 is **14/65 = 0.2154**. Group recall is **(10 + 1/2)/13 = 0.8077**; complete coverage occurs on ten of thirteen answerables (**0.7692**). Relative to B0, six questions gain group recall (test03, test05, test08–test11), one regresses (test13) and six stay equal. The designated unanswerables both remain insufficient with zero claims, so abstention matches the labels on **2/2** in both modes. The model's positive sufficiency counts are unchanged (ten sufficient, three partial); those labels are not answer correctness scores.

B0-R usage is **15 reranking calls / 181,734 input tokens**, **zero new query embeddings**, and **15 Claude responses / 93,760 input + 8,001 output tokens**. Sum of replay question runtimes is **58.41 seconds**. This excludes the source run's query embedding/search and therefore cannot be compared directly with B0's 64.46 seconds as an end-to-end speed result. Generation lengths and fresh responses also vary.

## Exploratory assistant answer review

All **40 saved answer texts** were read against the unchanged expected points. Selected cited passages were inspected for the substantive observations below. This is a post-run, non-blind **assistant review** with no additional Claude/Voyage requests, not an independent human assessment or exhaustive per-claim audit. No aggregate correctness, groundedness or citation-support ratio is invented.

The supplementary **relevance/required-point coverage rubric** is: **2** when the requested core facts are addressed, **1** when only part is addressed, and **0** when the requested facts are not addressed. Extra unrequested claims, factual errors and source risks are recorded separately: a relevance score of 2 does not certify correctness. Unanswerables have no relevance score; their abstention is assessed separately. These subjective scores supplement the fixed source-overlap metrics and were not used to alter any label, prompt or parameter.

| Question | B0 relevance / 2 | B0-R relevance / 2 | Reason for partial coverage or a material observation |
| --- | ---: | ---: | --- |
| dev01 | 2 | 2 | Both explain repeated local computation and weighted server model averaging; B0 adds an unrequested normalization discussion. |
| dev02 | 2 | 2 | Both state the statistical-heterogeneity and variable-local-work benefits. |
| dev03 | 2 | 2 | Both address control-variate correction. Reranked claim 2 has a verbal correction-sign error despite a correct equation; relevance is not correctness. |
| dev04 | 2 | 2 | Both explain the proximal penalty versus control variates. The reranked partial label reflects extra caveats rather than a missing requested mechanism. |
| dev05 | 1 | 1 | Both cover control variates, simulation and EMNIST, but omit part of the requested EMNIST factor list, especially varying participating-client count/local epochs. |
| test01 | 2 | 2 | Both list the four requested FedAvg properties. |
| test02 | 2 | 2 | Both specify label sorting, 200 shards of 300 examples, and two shards per client. |
| test03 | 2 | 2 | Both describe communicating locally computed model updates instead of local data; B0 uses an alternative algorithm passage. |
| test04 | 2 | 2 | Both explain variable local work and aggregation of partial straggler solutions; extra simulations are not needed for the requested answer. |
| test05 | 1 | 1 | Both describe FedBN feature shift but lack the original FedAvg description and omit the local-BN mechanism requested by the reference points. No FedAvg paper is present in the candidate pool. |
| test06 | 2 | 2 | Both state that client/Hessian similarity makes local steps useful for faster convergence or fewer communication rounds in the quadratic setting. |
| test07 | 2 | 2 | Both explain the mismatched objective and FedNova normalized averaging. |
| test08 | 2 | 2 | Both place client optimization on local losses and server optimization on the averaged client model difference/pseudo-gradient. |
| test09 | 2 | 2 | Both describe feature shift and keeping BN local; the reranked answer also gives the scanner/scenery examples. |
| test10 | 2 | 2 | Both distinguish representations from different models and the local/global positive pair. B0 adds an overly broad contrastive-learning scope statement copied from the paper's SimCLR discussion. |
| test11 | 1 | 2 | B0 has no FedMD evidence and only answers the pFedMe half. Reranking recovers the FedMD abstract plus pFedMe Moreau-envelope evidence and answers both requested forms of heterogeneity, despite a model partial label. |
| test12 | 2 | 2 | Both define across-device uniformity and connect fairness to poisoning robustness. |
| test13 | 1 | 1 | B0 discusses all three names but omits the AFL target-mixture formulation. Reranking drops Ditto entirely and also relies on a secondary AFL description; both answers remain partial. |
| test14 | — | — | Both abstain without inventing the unsupported BLEU result. |
| test15 | — | — | Both abstain without inventing the absent paper's quantum-hardware accuracy. |

Development relevance averages **1.80 / 2 in both modes** (four of five cover the requested points). Held-out relevance averages **23/13 = 1.77 / 2 for B0** and **24/13 = 1.85 / 2 for B0-R**; full requested-point coverage changes from ten to eleven of thirteen. This is a modest, exploratory answer-level difference, much smaller than the gold-span retrieval change. In particular, a retrieved supporting fact may never be verbalized: dev05 B0-R has complete annotated evidence coverage but still omits part of the requested EMNIST experiment-factor list.

### Source-based observations and limits

- **First-stage coverage, test05:** the shared 20-candidate pool contains 19 FedBN chunks and one `noniid_silos` chunk, with no FedAvg passage. Both final evidence sets contain five FedBN chunks and both answers acknowledge missing the original FedAvg description. The answers also omit local BN from the requested reference mechanism. Reranking cannot recover a missing candidate.
- **A recovered comparison, test11:** the initial pool has eight pFedMe and three FedMD chunks, plus surveys. Dense final evidence contains five pFedMe chunks; reranking retains one FedMD and four pFedMe chunks. The selected FedMD E1 abstract (PDF page 1) directly describes model heterogeneity, transfer learning and knowledge distillation; pFedMe E3 (page 1) describes statistical diversity and Moreau envelopes. The reranked answer addresses both requested mechanisms despite labeling itself partial over unrequested procedural detail.
- **A synthesis regression, test13:** the shared pool includes twelve q-FFL, five Ditto, one AFL and two survey/challenge chunks. B0 keeps three q-FFL and two Ditto passages; B0-R keeps five q-FFL passages. Reranking removes the Ditto coverage the synthesis needs. Both answers omit AFL's reference target-mixture formulation and instead use q-FFL's secondary worst-device description. This motivates testing bounded cross-paper coverage during future development, without retrospectively changing this baseline.
- **Answer completeness, dev05:** cited SCAFFOLD E3 on PDF page 7 explicitly lists local epochs, participating-client count and client similarity. The answers do not state the full requested factor list, even though B0-R retrieves it. A model sufficient/partial label is not a substitute for checking required points.
- **Answer correctness, dev03:** the reranked response's equation is correct but its verbal gradient-shift sign is reversed, as documented above. Provenance and retrieval-overlap checks cannot detect that semantic error.
- **Sparse gold labels:** B0 test03, test06, test08–test10 and dev03/dev04 can explain core requested facts from unannotated equivalent passages while receiving little or zero span credit. Annotation-overlap scores are therefore diagnostics, not semantic precision or answer accuracy. Conversely, dev02's two chunks can both cover the same annotated fact, so higher chunk precision does not necessarily add distinct facts.
- **Scope/calibration:** some answers add unrequested experiments, formal-equation caveats or broad contrastive-learning descriptions. The review keeps those observations separate from requested-point relevance and preserves all original outputs. A full claim-by-claim support audit and independent human grading have not been performed.

Across the four reported evaluation runs, successful recorded usage is **20 query embeddings / 355 tokens**, **20 reranking calls / 243,116 tokens**, and **40 Claude responses / 249,125 input + 23,204 output tokens**. The 40-paper index build separately used 683,346 embedding tokens over 37 calls. These counts exclude historical runs and account-wide usage; costs remain null because deployment pricing is not configured. No invoice/free-credit claim is made.

The corpus expansion, corrected parsing, indexing and controlled B0/B0-R evaluation are complete. Keep these run artifacts and frozen labels as the baseline. BM25/RRF and its separate controlled dev comparisons are complete; next is section-aware chunking with bounded hierarchy expansion. Corpus/model/prompt identities and both candidate pools were held fixed during the baseline comparison; the benchmark is small and the assistant review is exploratory.

## Historical 20-paper development results

Recorded 2026-10-15 (Asia/Tashkent). This is the Phase 2 baseline and an initial B0-R retrieval check, before hybrid/structural retrieval. The 15 held-out questions were not queried; their frozen hash is unchanged. No independent human answer scores are reported.

**Scope note:** the measurements in this historical section use the original 20-paper corpus and `cl100k_base` tokenizer. The corrected 40-paper / Voyage-tokenizer build and all four completed B0/B0-R runs are reported above. Preserve the original values here; corpus, parser and tokenizer changes prevent attributing cross-version differences to any single change.

### Configuration and artifacts

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

### Retrieval stages used in the comparison

| Stage | B0: reranking disabled | B0-R: reranking enabled |
| --- | --- | --- |
| Fast retriever | Chroma dense cosine search using `voyage-4-large` document/query embeddings, 2048 dimensions | Same retriever; this paired check reuses B0's saved candidates |
| Initial candidate cap | Up to 20 chunks | The same up to 20 chunks |
| Deduplication | Remove substantially overlapping source passages | Identical deduplication before reranking |
| Ranking for evidence selection | Dense cosine similarity | Atlas `rerank-3` scores every remaining candidate and returns all of them reordered |
| Final evidence | Up to 5 chunks within 4,000 passage-text tokens | Up to 5 chunks within the same budget |
| Tokenizer for the recorded results | `cl100k_base` | `cl100k_base` |

Deduplication and evidence budgeting can reduce the final count below five. The reranker itself does not return only five results; `pack_evidence` applies that limit afterwards. Text-token budgets exclude citation labels and prompt formatting, and generation usage comes from Claude's API. Future reports must include this stage table with their actual corpus/index, tokenizer revision, models and budgets. The next runs will use Voyage token counts for chunking, query limits and evidence text; `rerank-3` and Claude still report their own API usage.

### Retrieval diagnostics

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

### Answer and source checks

All five B0 responses passed structured-answer and citation-ID validation. The model marked dev01/dev02/dev03/dev05 sufficient and dev04 partial; these labels are model judgments, not human accuracy scores. Selected cited text was inspected against the indexed original passages. Required-fact and claim-support adjudication remains to be completed for final evaluation.

A separate, unscored smoke question asked for kilograms of CO2 measured in the original FedAvg experiments, with a FedAvg paper filter. The assistant returned insufficient evidence and zero claims instead of inventing a number. This successful abstention check is outside the frozen benchmark and did not alter its labels.

The answer prompt was refined once on development questions to reduce unrelated theory/results and to judge sufficiency against the information actually requested. The original answer run (`ab7a8f3ca04d46deba9b8bd862b537c9`) is retained. The final run above uses the refined prompt; retrieval settings and labels were unchanged.

Observed limitations:

- The B0 dev04 final evidence lacks the FedProx mechanism, so the answer cannot provide the full requested mechanistic comparison. The candidate pool contains more relevant source material than the final dense top 5. This is a real retrieval limitation to assess in the next phases.
- Dev03 receives zero gold-span credit although its answer cites SCAFFOLD's control-variate update description on PDF pages 4–5. Sparse gold spans therefore require semantic adjudication before treating overlap scores as relevance scores.
- Some responses still add unnecessary formula/proof qualifications. The free-text limitations field is not semantically validated; dev04's caveat names the missing proximal mechanism. Valid citation IDs alone do not prove that every sentence is supported by its packed evidence.
- Fixed chunks can cross sections/pages and contain fragmentary equations. No changes were made to invent failures or satisfy a reporting quota.
- USD costs remain null because prices/free-credit balances were not configured or queried. Reported token usage is not an invoice or account-credit measurement.

### Reproduction and next work

The default configuration has changed since these historical measurements. The expanded parse, verified annotation migration, new freeze, new index and B0 development answers are complete. Use the paired replay command in the current 40-paper section above for the next comparison. The B0-R config enables reranking for normal use. For a strict paired comparison, replay the saved B0 `trace.retrieval.candidates` through `deduplicate_candidates`, `VoyageReranker.rerank` and `pack_evidence` under the same budgets; a fresh retrieval call is not an exact replay.

The 40-paper Voyage-tokenizer baseline is established. BM25/RRF and its controlled dev answer comparisons/targeted assistant review are complete; section-aware retrieval is next. Keep corpus, models, prompt, development/test split and final evidence budgets fixed within each comparison. Leave further held-out execution until methods/settings are fixed. Review semantic support and sample answers before making final quality claims.
