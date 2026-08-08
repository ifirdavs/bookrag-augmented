# Model setup

Generation uses **Claude Haiku 5.5** (`claude-haiku-5-5`) through the official Anthropic SDK. Embeddings use **Voyage 4 Large** (`voyage-4-large`) through the official Voyage SDK, with **2048-dimensional float vectors** for both document chunks and questions. Optional reranking uses **`rerank-3`**. The same embedding/generation models stay fixed across controlled retrieval comparisons.

Set both keys in the ignored project `.env`:

```dotenv
ANTHROPIC_API_KEY=your-claude-key
VOYAGE_API_KEY=your-voyage-key
```

`FEDRESEARCH_GENERATION_MODEL` and `FEDRESEARCH_EMBEDDING_MODEL` optionally override YAML model names. Dimensions, batch size, timeouts and SDK retries are in `configs/default.yaml`. `doctor` reports configuration/key presence without sending requests; `doctor --live` makes small embedding, reranking and structured-generation calls. Both keys are now present. Atlas embedding and reranking calls succeeded; the current key routes to `https://ai.mongodb.com/v1` automatically through the official SDK.

Voyage embeds passages with `input_type="document"` and questions with `input_type="query"`. Silent truncation is disabled, and vector count, dimensions and finite/nonzero values are checked. The API enforces its 32,000-token per-input and 120,000-token per-request limits. The default batches contain 32 short chunks. `cl100k_base` remains the chunk/evidence counting convention; actual Voyage and Claude usage comes from their APIs.

For `voyage-4-large`, the **first 200 million document/query tokens are free per account**, then the standard endpoint costs **$0.12 per million tokens**, checked 2026-10-15. The integration uses the standard embedding endpoint; Voyage's separate asynchronous Batch API does not apply free credits. This does not establish any particular account's remaining balance. [Pricing](https://docs.voyageai.com/docs/pricing)

Local Voyage tokenization of all 657 chunks counted **393,449 document-text tokens**, excluding input-type prompts; the largest chunk was 682 tokens and the largest default batch 19,832. This is a preflight estimate, not billed usage. The full 2048-dimensional index now contains all 657 chunks. Atlas reported 392,830 embedding tokens for the build; the local tokenizer figure is an estimate and differs from server usage. Optional `FEDRESEARCH_EMBEDDING_INPUT_PRICE`, `FEDRESEARCH_RERANKING_INPUT_PRICE` and generation input/output prices give nominal USD estimates; they do not account for free credits or discounts. Estimates remain null when prices are unset.

Claude requests the `GeneratedAnswer` Pydantic schema with `messages.parse()`. Refusals, incomplete outputs and unknown citation IDs are rejected. The live CLI check on 2026-10-15 returned a valid insufficient-evidence answer: 551 input tokens and 70 output tokens. This verifies generation access/schema parsing, not corpus retrieval quality. Both adapters sanitize provider errors to type/status.

References: [Haiku 5.5](https://platform.claude.com/docs/en/models/haiku-5-5/overview), [structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs), [Voyage embeddings](https://docs.voyageai.com/docs/embeddings), [Voyage tokenization](https://docs.voyageai.com/docs/tokenization).

Reranking is off in `configs/default.yaml` and `b0_dense.yaml`. `b0_dense_rerank.yaml` enables it on the same dense candidates. The existing `retrieval.candidate_limit` bounds both modes (20 by default). Both modes deduplicate original source spans before the optional ranking stage and share the final item/token budgets. The trace preserves original/reranked ranks and scores, source IDs, latency and token usage; provider failures remain failures. Truncation is disabled. [Atlas reranker documentation](https://www.mongodb.com/docs/voyageai/models/rerankers/?client=python)

**Throughput check resolved (2026-10-15):** The earlier default batch received HTTP 429 under the trial limits of 3 RPM / 10,000 TPM. After the user added a payment method, all 21 normal index batches succeeded and the full index built in 20.21 seconds. Saved-index reuse requires no new embedding calls. The exact new account RPM/TPM limits were not queried; this verifies the required workload rather than unlimited access. Live baseline answers, reranking and an abstention check also completed. See [initial development results](../reports/evaluation.md).
