# Corpus and preprocessing

Current inventory, 2026-10-17 (Asia/Tashkent): **40 PDFs and 937 PDF pages**, with all source checksums valid and no duplicate IDs, versions or file hashes. The corrected Voyage-tokenizer/v4 parse produced **47,592 blocks, 955 sections and 1,158 chunks** (600-token maximum), with no serious or structural warnings. The original 20 manifest entries are unchanged. Every PDF has a pinned source version and SHA-256 in `data/corpus_manifest.jsonl`. `year` is the arXiv citation/submission year for preprints and the publication year for the two published-only copies.

The original selection covers methods, optimization/heterogeneity, personalization, fairness, and one survey. On 2026-10-16 the user agreed to preserve these 20 and add 20 selected papers covering surveys, privacy, systems, communication efficiency and applications. Acquisition is complete; processing continues interactively. The historical table below describes the original 20-paper `cl100k_base` parse: 614 pages, 34,577 blocks, 628 section/fallback records and 657 chunks. This collection is not an exhaustive representation of federated-learning research.

All 40 PDFs are present as `data/raw/<paper_id>.pdf`. The application CLI has no download or metadata-search commands. PDFs remain in ignored `data/raw/`; generated canonical documents remain in ignored `data/processed/<paper-id>/<parse-id>.json`. The corpus metadata and benchmark annotations are tracked. Do not redistribute PDFs without checking their licenses.

Expansion completed (2026-10-17): source metadata and PDF/title identity were checked for all 20 additions. Eighteen use explicitly versioned arXiv PDFs; Secure Aggregation uses the CCS conference copy and the medical-collaboration paper uses the published Scientific Reports PDF. The user ran `work/download_corpus_additions.py` successfully: 20 downloaded, 40 total, empty download/integrity failure lists. The helper remains outside the application CLI in ignored `work/`. It computes SHA-256 and registers only the existing seven manifest fields. The original manifest is backed up; original benchmark files are also preserved in `work/benchmarks_before_voyage/` for the completed source-reference migration. The corrected full parse and all 26 benchmark source references are verified; only parse/block IDs changed, both splits validate and the new test freeze is valid. The new index `6f8ba8be92dcc84b51a5514f` contains all 1,158 chunks and passed vector/source/fingerprint checks; both five-question development answer runs passed with identical dense candidates; the dense held-out run completed all 15 questions and abstained on both designated unanswerables; paired reranked held-out evaluation also completed all 15 questions with no errors and correct abstention on both designated unanswerables. The corpus/tokenizer remained fixed throughout all four reported runs.

| Paper ID | arXiv version | PDF pages | Sections | Fixed chunks |
| --- | --- | ---: | ---: | ---: |
| `fedavg` | arxiv:1602.05629v4 | 11 | 8 | 18 |
| `fedprox` | arxiv:1812.06127v5 | 22 | 25 | 33 |
| `scaffold` | arxiv:1910.06378v4 | 41 | 33 | 43 |
| `fednova` | arxiv:2007.07481v1 | 34 | 36 | 34 |
| `feddyn` | arxiv:2111.04263v2 | 43 | 26 | 36 |
| `fedopt` | arxiv:2003.00295v5 | 38 | 40 | 39 |
| `mime` | arxiv:2008.03606v2 | 40 | 47 | 40 |
| `local_sgd` | arxiv:1805.09767v3 | 19 | 21 | 19 |
| `fedavg_convergence` | arxiv:1907.02189v4 | 26 | 34 | 31 |
| `noniid` | arxiv:1806.00582v2 | 12 | 21 | 15 |
| `fedbn` | arxiv:2102.07623v2 | 27 | 35 | 27 |
| `moon` | arxiv:2103.16257v1 | 12 | 33 | 18 |
| `pfedme` | arxiv:2006.08848v3 | 23 | 23 | 21 |
| `ditto` | arxiv:2012.04221v3 | 32 | 32 | 40 |
| `perfedavg` | arxiv:2002.07948v4 | 29 | 24 | 27 |
| `multitask` | arxiv:1705.10467v2 | 19 | 36 | 27 |
| `fedmd` | arxiv:1910.03581v1 | 8 | 11 | 6 |
| `qffl` | arxiv:1905.10497v2 | 27 | 24 | 30 |
| `agnostic` | arxiv:1902.00146v1 | 30 | 25 | 28 |
| `survey` | arxiv:1912.04977v3 | 121 | 94 | 125 |

Historical parser: PyMuPDF 1.28.2, `pymupdf-columns-v3`; the statistics above used `cl100k_base`, 600 tokens and 100-token overlap. Current defaults use the official `voyageai/voyage-4-large` tokenizer, pinned to revision `bb931c2635a93efe400c24741363d8ff61d7bb32`, with a 600-token cap and 100-token overlap target. Whole-character boundaries and recounting keep source text intact and each chunk within the cap. The corrected full run and its current statistics are recorded above and in [preprocessing checks](../reports/preprocessing.md). References, detected table cells, equation-like fragments, and repeated/rotated margins are excluded from chunks; originals remain in canonical blocks. Fixed chunks may cross sections and pages. Every chunk retains raw character spans and all contributing section/page identities.

Current parser v4 recognizes Roman-numbered small-cap headings and separates standalone named heading lines from adjacent prose while keeping same-line section numbers/titles together. The full corrected run has no serious or structural warnings. All 26 benchmark source passages have been migrated and validated against their unchanged source text, coordinates and quote offsets; the new test freeze is valid. See [preprocessing checks](../reports/preprocessing.md).

All documents passed schema, source-span, cleaning-map, page-range, and section-membership checks. There were zero failed papers, zero empty/image-only pages, and zero replacement-character warnings. The current 40-paper parser excluded 3,876 detected table blocks and 1,841 margin blocks. These counts are diagnostics, not proof that every table or equation was detected.

Representative visual review covered title/abstract, body reading order, experiments, and references in FedAvg, FedProx, and SCAFFOLD. See `reports/preprocessing.md` for reviewed PDF pages and corrections. Headings and columns remain heuristic; arithmetic results and chart pixels are outside this phase's reliable scope. No document with a serious parse warning is accepted by the index builder without fixing/reviewing its parse.

The manifest stores seven fields: `paper_id`, `title`, `year`, `source_url`, `document_version`, `sha256` and `methods`. IDs locate files, titles/URLs support citations, versions/checksums pin sources, and year/method names support retrieval filters. Author lists, download URLs, abstracts, acquisition timestamps and representative flags are not stored.

Parse the existing corpus:

```bash
HF_HOME=work/hf-cache uv run fedresearch preprocess
# For the tokenizer migration, verify/rebind benchmark source IDs before validating.
uv run fedresearch benchmark validate
```

For a targeted parser check, pass `--paper-id fedavg --paper-id fedprox --paper-id scaffold`. Index building validates that all manifest PDFs exist and match their pinned checksums. To add a paper, place its PDF in `data/raw/`, add these seven metadata fields, and preprocess it before rebuilding the index.

`data/processed/diagnostics.json` records every page's text count, dimensions, detected columns/tables, image count, and document-level warnings. Failed papers appear explicitly and produce a nonzero CLI exit. Later index building requires all manifest entries to have a compatible, usable parse.
