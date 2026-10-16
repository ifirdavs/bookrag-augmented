# Delivery verification and demonstration

**Complete — 2026-10-26.** Evaluation was committed first as `75ffd4c` with the requested author/committer dates, `2026-10-16T23:40:51+05:00`. Delivery changes are prepared separately from the evaluation commit. Application code, experiment configurations, prompts, labels and original measurements remain unchanged. A root-anchored `.env.example` ignore exception fixes a packaging-only issue found below. No new Typer commands were added.

The [structured delivery record](delivery.json) and [saved live smoke](delivery_smoke.json) supplement the original [final evaluation](final_evaluation.md). The [README](../README.md) is the current setup guide and [examples](examples.md) provides four unchanged source-linked outputs.

## Delivered contents and cleanup

- Rewritten current README, including provider/tokenizer setup, build order, retrieval mental model, experiment selection, final results, provenance, file guide and troubleshooting.
- Standalone [corpus acquisition](../scripts/download_corpus.py) and [result integrity](../scripts/verify_delivery.py) helpers; no new application commands or framework.
- Four CLI examples: explanation, comparison, bounded synthesis with an evidence gap, and abstention. Saved outputs/pages remain visible without API calls.
- Useful content from all five temporary notes migrated into the README, preprocessing/baseline/final reports. Incoming links were rewritten and `docs/` removed.
- Nine final test runs retained under `artifacts/runs/`, including reused B0/B0-R controls; **14 older development/exploratory runs removed**. The retained original bytes are in [final_runs.zip](final_runs.zip), with [archive checksum](final_runs.sha256) and run hashes in the existing final summary. Historical reports/metrics remain, with pruning notices. The temporary removed-run backup remains outside delivery in ignored `work/`.

## Environment and installation

Tested: macOS arm64, Python 3.13.1, uv 0.11.24, SQLite 3.45.3. Other declared Python versions/platforms were not tested. A source-only checkout under ignored `work/delivery/checkout` had its own virtual environment, with no copied credentials or generated artifacts during installation.

```bash
# This command was run by the user; it installed 109 locked packages:
UV_CACHE_DIR="$PWD/work/uv-cache" uv sync --locked --project work/delivery/checkout
# Build and install the wheel in that environment, without changing the primary .venv:
UV_CACHE_DIR="$PWD/work/uv-cache" uv build --offline --out-dir work/delivery/dist
UV_CACHE_DIR="$PWD/work/uv-cache" uv pip install --python work/delivery/checkout/.venv/bin/python --offline --no-deps --reinstall work/delivery/dist/fedresearch-0.1.0-py3-none-any.whl
```

The first offline sync lacked NetworkX 3.7 in the available cache; the user's terminal completed installation. The `VIRTUAL_ENV` mismatch warning correctly selected the separate environment. Import verification confirmed the installed module came from `site-packages`, and the packaged `llm/prompts/answer.md` was accessible. CLI help and `doctor` worked without credentials/model calls. The wheel contains application code/prompt; the project checkout supplies configs, metadata, graph inputs and evaluation materials. Final source-distribution inspection caught an extra `work/delivery/checkout/.env.example`: the unanchored `.gitignore` exception had included a nested example file. Anchoring the exception to `!/.env.example` excludes temporary checkout contents while retaining the root template. No populated credentials were present in that source distribution. The corrected distribution includes only the intended source/config/data/report inputs, including the portable runs archive.

## Local source, index and evaluation checks

All 40 locally available PDFs pass pinned SHA-256 checks. Those verified PDFs were copied into the isolated checkout, and the tokenizer cache was explicitly reused. A fresh full parse rebuilt **all 40 canonical documents identically**, including source IDs/text/spans; there were zero failures or serious/structural warnings. Both benchmark splits validate (5 dev / 15 test), and the existing source-verified freeze remains unchanged.

Full fixed/section indexes were copied into the isolated checkout for reload/reuse checks; their vectors were not re-embedded. From the fresh parses, `build_index` reused both completed indexes with zero provider calls and rebuilt compatible BM25 sidecars. Local lexical queries succeeded. The section graph rebuilt/reloaded with 36 entities / 29 assertions / 14 papers and valid original spans.

Using the installed wheel and these isolated indexes, all **135 final evidence lists** reproduce exactly from the nine saved candidate pools with embedding requests blocked and recorded reranker results replayed locally. This is evidence-selection verification, not a fresh reranker response or generation run. Original final-run hashes, all 55 frozen input hashes, final retrieval arithmetic and 279-claim/517-citation audit counts validate. The delivered verifier performs archive/hash/final-score/audit-arithmetic checks without requiring indexes or hosted models; it does not independently regrade semantics.

The existing 81 tests passed in the new environment. Three added acquisition tests check exact-byte download/reuse, refusal to overwrite a mismatched local PDF and cleanup after mismatched server content. The final suite contains **84 passing tests**. Ruff lint/format, whitespace and local documentation links pass. PyMuPDF emits its existing layout suggestion and upstream SWIG deprecation warnings; these did not indicate failed parsing or suppress diagnostics.

## Isolated live smoke check

A temporary one-paper project used the original FedAvg PDF, default parser/models and the installed wheel. It created **18 chunks**, a new dense/BM25 index and two real answers. Successful document indexing used **10,692 Voyage input tokens / one request**.

The initial temporary harness completed both model checks but failed while saving nested `Answer` objects. Explicit JSON-mode conversion and per-answer checkpoints repaired that harness. Application serialization/answer code was unchanged. A local mocked save/resume check passed before the retry. The first two query embeddings and two Claude responses were not retained in the failed save, so their answer-token totals are unavailable; they are not silently included in the saved retry usage.

The retry reused the completed index with **zero new document embeddings**, made two query embeddings (**34 tokens**) and two Claude calls (**11,975 input / 536 output tokens**), and made no reranking calls. The positive answer correctly lists the four FedAvg properties and cites original PDF pages 2–3. The unsupported FedQuantum-X question returns `insufficient` with zero structured claims. Its contextual prose is not a separately graded benchmark answer. Full saved texts, source passages and usage are in [delivery_smoke.json](delivery_smoke.json).

Including the first unsuccessful save attempt, this smoke involved one document batch, four query-embedding requests and four Claude responses. No full-corpus embeddings or benchmark generations were repeated. Costs remain unconfigured. Smoke outputs stay outside `artifacts/runs/` and are excluded from the original 135 benchmark executions.

### Repeat a small workflow if desired

The main README works with the full pinned corpus. To exercise a separate one-paper project through the public CLI, prepare a temporary subset as follows; the local `.env` copy stays in ignored `work/`.

```bash
uv run python - <<'PYCODE'
import json
import shutil
from pathlib import Path

folder = Path("work/smoke")
for name in ("configs", "data/raw"):
    (folder / name).mkdir(parents=True, exist_ok=True)
shutil.copy2("configs/default.yaml", folder / "configs/default.yaml")
shutil.copy2(".env", folder / ".env")
shutil.copy2("data/raw/fedavg.pdf", folder / "data/raw/fedavg.pdf")
rows = [json.loads(line) for line in Path("data/corpus_manifest.jsonl").read_text().splitlines()]
paper = next(row for row in rows if row["paper_id"] == "fedavg")
(folder / "data/corpus_manifest.jsonl").write_text(json.dumps(paper) + "\n")
PYCODE
HF_HOME=work/hf-cache uv run fedresearch preprocess --config work/smoke/configs/default.yaml
HF_HOME=work/hf-cache uv run fedresearch index --config work/smoke/configs/default.yaml
HF_HOME=work/hf-cache uv run fedresearch ask "What four properties make federated optimization different in the original FedAvg paper?" --config work/smoke/configs/default.yaml --json
HF_HOME=work/hf-cache uv run fedresearch ask "What test accuracy does the indexed 2026 FedQuantum-X paper report on quantum hardware?" --config work/smoke/configs/default.yaml --json
```

This optional repeat makes new model calls and saves new traces beneath the temporary project's own artifact path. A subset cannot validate the full benchmark or curated full graph. Use the complete corpus/indexes for those modes. Do not change the main manifest, frozen labels or active pointers to perform this check.

## Scope of completion

Delivery verifies the tested environment, pinned local inputs, build/import/resource handling, source/index reload and representative real-provider use. Acquisition of every remote endpoint, empty-cache re-embedding of both full indexes, other platforms and independent human answer grading remain outside these checks. Blocked or changed publisher PDFs produce a visible failure/manual-download URL rather than an altered manifest. The documented setup and evaluation procedures are reproducible, while remote model answers and availability can change.

The BookRAG paper/repository and SQLite/Atlas references were checked during consolidation; references remain next to the relevant README claims. No upstream code or new service was imported. No pushes or external publication occurred. The temporary `work/delivery/checkout` and its virtual environment were removed after verification. Built packages, smoke evidence and verification outputs remain separately under `work/delivery/`; the primary environment, corpus, indexes and nine final runs are preserved. The user requested a separate delivery commit with author/committer date `2026-10-17T01:23:43+05:00`.
