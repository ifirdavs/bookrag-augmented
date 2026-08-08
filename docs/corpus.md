# Corpus and preprocessing

Recorded 2026-10-12 (Asia/Tashkent). The confirmed corpus contains **20 PDFs, 614 PDF pages, 34,577 canonical blocks, 628 section/fallback records, and 657 fixed baseline chunks**. Every PDF has a pinned arXiv version and SHA-256 in `data/corpus_manifest.jsonl`. No duplicate IDs, versions, or file hashes were detected. `year` is the arXiv citation/submission year, which may differ from the eventual conference year.

The selection covers original methods, optimization/heterogeneity, personalization, fairness, and one survey. The user confirmed this corpus. Expand it only when relevant questions demonstrate a coverage gap. This collection is not an exhaustive representation of federated-learning research.

The 20 PDFs are already present as `data/raw/<paper_id>.pdf`. No download or metadata-search commands are included. They remain in ignored `data/raw/`; generated canonical documents remain in ignored `data/processed/<paper-id>/<parse-id>.json`. The corpus metadata and benchmark annotations are tracked. Do not redistribute PDFs without checking their licenses.

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

Parser: PyMuPDF 1.28.2, `pymupdf-columns-v3`. B0 uses `cl100k_base`, 600 tokens, 100-token overlap. References, detected table cells, equation-like fragments, and repeated/rotated margins are excluded from chunks; originals remain in canonical blocks. Fixed chunks may cross sections and pages. Every chunk retains raw character spans and all contributing section/page identities.

All documents passed schema, source-span, cleaning-map, page-range, and section-membership checks. There were zero failed papers, zero empty/image-only pages, and zero replacement-character warnings. The parser excluded 2,561 detected table blocks and 1123 margin blocks. These counts are diagnostics, not proof that every table or equation was detected.

Representative visual review covered title/abstract, body reading order, experiments, and references in FedAvg, FedProx, and SCAFFOLD. See `reports/preprocessing.md` for reviewed PDF pages and corrections. Headings and columns remain heuristic; arithmetic results and chart pixels are outside this phase's reliable scope. No document with a serious parse warning is accepted by the index builder without fixing/reviewing its parse.

The manifest stores seven fields: `paper_id`, `title`, `year`, `source_url`, `document_version`, `sha256` and `methods`. IDs locate files, titles/URLs support citations, versions/checksums pin sources, and year/method names support retrieval filters. Author lists, download URLs, abstracts, acquisition timestamps and representative flags are not stored.

Parse the existing corpus:

```bash
uv run fedresearch preprocess
uv run fedresearch benchmark validate
```

For a targeted parser check, pass `--paper-id fedavg --paper-id fedprox --paper-id scaffold`. Index building validates that all manifest PDFs exist and match their pinned checksums. To add a paper, place its PDF in `data/raw/`, add these seven metadata fields, and preprocess it before rebuilding the index.

`data/processed/diagnostics.json` records every page's text count, dimensions, detected columns/tables, image count, and document-level warnings. Failed papers appear explicitly and produce a nonzero CLI exit. Later index building requires all manifest entries to have a compatible, usable parse.
