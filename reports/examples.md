# CLI demonstration examples

These are unchanged saved outputs from the final frozen evaluation, selected to show useful answers and actual evidence limits. Inspecting them makes no API calls. Running a command generates a fresh answer and trace; it can differ from the saved output. The default remains dense-20; each example explicitly chooses its measured configuration. Restore the nine raw runs with the archive command in the [README](../README.md#inspect-saved-results-without-model-calls) when needed.

## 1. Method explanation

```bash
HF_HOME=work/hf-cache uv run fedresearch ask "What four properties make federated optimization different in the original FedAvg paper?" --config configs/experiments/b1_hybrid_rerank.yaml --json
```

Saved result: **sufficient**, B1-R, `test01` in [original run](../artifacts/runs/b34ebe340a77429889e77c38d18137c1/run.json), under `records` → `question_id` → `answer`.

Verbatim saved answer:

> The original FedAvg paper lists four properties that differentiate federated optimization from typical distributed optimization: non-IID data, unbalanced data, massively distributed clients (the number of clients is much larger than the average number of examples per client), and limited communication. [E1]

| Citation | Original source | PDF pages |
| --- | --- | --- |
| E1 | [Communication-Efficient Learning of Deep Networks from Decentralized Data](https://arxiv.org/abs/1602.05629v4) | [2, 3](../data/raw/fedavg.pdf#page=2) |

## 2. Two-paper comparison

```bash
HF_HOME=work/hf-cache uv run fedresearch ask "How do pFedMe and FedMD address different forms of client heterogeneity?" --config configs/experiments/b1_hybrid_rerank.yaml --json
```

Saved result: **partial**, B1-R, `test11` in [original run](../artifacts/runs/b34ebe340a77429889e77c38d18137c1/run.json), under `records` → `question_id` → `answer`.

Verbatim saved answer:

> pFedMe targets statistical heterogeneity, where clients have non-i.i.d. data distributions. It adds a per-client regularized loss built on Moreau envelopes, so each client learns a personalized model while staying tied to a shared global reference model. [E3] [E2] [E5]
>
> FedMD targets heterogeneity in the local models themselves, where each participant independently designs its own model. It uses transfer learning and knowledge distillation so that federated learning can still proceed across these different models. [E1]
>
> The excerpts for FedMD come only from its abstract and introduction, so the specific distillation procedure and any treatment of statistical heterogeneity in FedMD are not described. The answer for FedMD is therefore high-level, and its mechanism cannot be fully explained from this evidence.

| Citation | Original source | PDF pages |
| --- | --- | --- |
| E1 | [FedMD: Heterogenous Federated Learning via Model Distillation](https://arxiv.org/abs/1910.03581v1) | [1](../data/raw/fedmd.pdf#page=1) |
| E2 | [Personalized Federated Learning with Moreau Envelopes](https://arxiv.org/abs/2006.08848v3) | [1, 2](../data/raw/pfedme.pdf#page=1) |
| E3 | [Personalized Federated Learning with Moreau Envelopes](https://arxiv.org/abs/2006.08848v3) | [1](../data/raw/pfedme.pdf#page=1) |
| E5 | [Personalized Federated Learning with Moreau Envelopes](https://arxiv.org/abs/2006.08848v3) | [2, 3](../data/raw/pfedme.pdf#page=2) |

The high-level contrast is supported, while the saved answer explicitly limits its explanation of FedMD to the available abstract/introduction.

## 3. Bounded synthesis with an explicit gap

```bash
HF_HOME=work/hf-cache uv run fedresearch ask "Using only q-FFL, Ditto, and Agnostic Federated Learning in this corpus, summarize three ways fairness enters their problem formulations." --config configs/experiments/b3_graph.yaml --json
```

Saved result: **partial**, B3, `test13` in [original run](../artifacts/runs/84a5e1f05cf348aeaa58709714a72b3f/run.json), under `records` → `question_id` → `answer`.

Verbatim saved answer:

> In q-FFL, fairness enters by raising each device's local loss to the power q+1 in the objective, which emphasizes devices with higher losses. The parameter q tunes the amount of fairness, and q=0 gives no fairness beyond the classical federated learning objective. [E1] [E4]
>
> In Ditto, fairness is framed as uniformity of performance across devices within a simple, general personalized federated learning framework. It is treated as a constraint that competes with robustness to data and model poisoning attacks. [E3]
>
> AFL is the prior fair federated learning objective that q-FFL generalizes. With a large enough q, q-FFL reduces to classical minimax fairness, where the device with the largest loss dominates the objective. [E1]
>
> The excerpts do not give AFL's own objective, only its relation to q-FFL and minimax fairness, so AFL's formulation is only partly covered. For Ditto, the evidence is limited to the abstract, which does not show the fairness term in its formulation; the abstract also says its theoretical analysis covers only a class of linear problems. The displayed q-FFL objective is incomplete in the evidence, so the exact form of the objective is not stated here.

| Citation | Original source | PDF pages |
| --- | --- | --- |
| E1 | [Fair Resource Allocation in Federated Learning](https://arxiv.org/abs/1905.10497v2) | [4, 5](../data/raw/qffl.pdf#page=4) |
| E3 | [Ditto: Fair and Robust Federated Learning Through Personalization](https://arxiv.org/abs/2012.04221v3) | [1](../data/raw/ditto.pdf#page=1) |
| E4 | [Fair Resource Allocation in Federated Learning](https://arxiv.org/abs/1905.10497v2) | [4](../data/raw/qffl.pdf#page=4) |

The original AFL mixture-distribution formulation is missing; this is an incomplete synthesis, not a successful exhaustive three-way account. The output is preserved without rewriting it.

## 4. Unsupported premise and abstention

```bash
HF_HOME=work/hf-cache uv run fedresearch ask "What BLEU score does the original SCAFFOLD paper report for English–Uzbek translation?" --config configs/experiments/b1_hybrid_rerank.yaml --json
```

Saved result: **insufficient**, B1-R, `test14` in [original run](../artifacts/runs/b34ebe340a77429889e77c38d18137c1/run.json), under `records` → `question_id` → `answer`.

Verbatim saved answer:

> The supplied evidence from the original SCAFFOLD paper (E1, E4) covers EMNIST logistic regression and non-convex experiments, communication rounds, and convergence conclusions; it does not report any BLEU score or English–Uzbek translation experiment. The other excerpts (E2, E3, E5) are from different papers (FedDyn, Adaptive Federated Optimization) and likewise contain no BLEU or translation results. The question's premise therefore has no support in the supplied evidence, and no BLEU value can be attributed to the SCAFFOLD paper from this corpus.

There are no structured claims or citations. The supplied SCAFFOLD excerpts concern EMNIST/convergence rather than the requested translation result. Successful abstention avoids inventing a BLEU score. The raw run retains all provided evidence for inspection.

## Read the workflow in a trace

The service searches dense and local BM25 candidates, combines ranks with RRF, optionally expands hierarchy/graph links, deduplicates source overlap, optionally reranks, packs up to five passages within 4,000 Voyage tokens, then calls Claude.

In the B3 synthesis trace, inspect `answer.trace.retrieval.structural_expansion` and `graph_expansion` for seed/base candidates, matched entities, assertions, original support IDs, reasons and dropped candidates. `candidates` is the final merged pre-deduplication pool; `deduplicated_candidates` is the input to optional reranking; `answer.evidence` is the final context. `rankings` preserves dense/BM25 components; `reranking.results` maps input indices/original ranks to reranker scores.

B1-R has the strongest final span coverage (11/13) in the full matrix. Expansion and reranking can also demote useful evidence: B3-R moves test11's annotated FedMD source from rank 3 to 35 while preserving the candidate pool. See [final analysis](final_evaluation.md) for alternative supporting sources, sparse-span limits, assistant-review caveats, usage and replay timing scopes.
