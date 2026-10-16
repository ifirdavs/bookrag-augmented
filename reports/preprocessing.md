# Preprocessing verification

## 40-paper Voyage-tokenizer run, 2026-10-17

The corrected full run processed all **40 PDFs / 937 pages** with parser `pymupdf-columns-v4` and the pinned Voyage 4 Large tokenizer. Local validation confirmed **47,592 blocks, 955 sections and 1,158 chunks**, with a maximum of **600 Voyage tokens per chunk**. There were no failed documents, serious warnings, structural warnings, empty-page warnings or source-span/cleaning-map errors. The parser excluded 3,876 detected table blocks and 1,841 margin blocks. Configuration hash: `baf452973284cf1d2b4d4941a248d0710108e7f05b5a837a98d7b64b64485f96`.

The first v3 attempt produced 47,565 blocks, 886 sections and 1,160 chunks and reported six `few_detected_headings` warnings. Inspection identified missed IEEE Roman-numbered small-cap headings and journal headings sharing blocks with subsequent prose. Parser v4 handles these patterns while preserving section numbers/titles on the same line. Regression checks reject author initials/formula fragments and keep detected bibliography text out of chunks. The six affected PDFs and two controls passed targeted checks; all 40 active parses now use v4. **43 offline tests passed** for the implementation, along with lint/format checks.

The benchmark migration verified all 26 original gold passages against unchanged PDF hashes/versions and unique current blocks with identical raw text, page, bounding box and quote offsets. The user applied the migration, validated both splits (5 dev / 15 test) and recorded a valid new held-out freeze. Independent comparison confirms that only parse/block IDs changed; questions, groups, quotes, offsets, expected points and annotation statuses are unchanged. Originals remain backed up. The user subsequently built the new index: 1,158 vectors, 683,346 API-reported embedding tokens over 37 calls in 34.77 seconds. Index/source/fingerprint/vector checks passed; both subsequent five-question B0/B0-R development runs passed with exact shared dense candidates; the dense held-out run subsequently completed all 15 questions with zero execution errors and abstained on both designated unanswerables; paired reranked held-out evaluation also completed with zero errors and the same successful abstentions. All four reported evaluation runs use the same corpus/parser/tokenizer/index.

New layout sampling used bundled Poppler to render the original PDFs; reviewed PNGs are in `work/pdf-review-40/`.

| Paper | Reviewed 1-based PDF page | Check |
| --- | ---: | --- |
| FL with differential privacy | 2 | Two-column reading order and Roman-numbered section heading |
| Federated learning in medicine | 7 | Single-column prose and standalone Discussion title merged by extraction |
| Secure Aggregation | 2 | Two-column prose and numbered section/subsection labels |

This is representative sampling, not a complete visual audit. Some wrapped headings remain partial, and heading hierarchy/table/equation handling remains heuristic. The corrected statistics above describe preprocessing, not a completed embedding index or retrieval-quality result. Benchmark source references have been migrated/validated and test labels refrozen. Independent human review is still pending.

## Historical 20-paper baseline

Recorded 2026-10-12 (Asia/Tashkent). All 20 source PDFs were acquired with pinned versions and checksums and parsed into 657 fixed chunks. This verifies local preprocessing; it does not measure hosted embedding or answer quality.

The remaining section records historical `cl100k_base` results. Current defaults use the pinned official Voyage 4 Large tokenizer and parser v4; the old counts/source IDs must not be assumed to describe the new parse.

Acquisition update (2026-10-17): all **40 PDFs / 937 pages** are present, checksums pass and the original 20 manifest entries are unchanged. The user completed all 20 new downloads with no failures. The current parsing results and required v4 rerun are documented above.

| Representative | Visually reviewed 1-based PDF pages | Observations |
| --- | --- | --- |
| FedAvg | 1, 2, 5, 7, 9 | Title/abstract and two columns match extraction; MNIST partition prose resolves to page 5; figures remain uninterpreted; references are excluded. |
| FedProx | 1, 2, 6, 8, 11 | Title/abstract and two columns match extraction; proximal mechanism and systems experiment prose is available; dataset table cells are conservatively excluded; references retain original blocks. |
| SCAFFOLD | 1, 2, 6, 7, 9 | Title/abstract, two columns, headings and experiments match extraction; control-variate source and EMNIST setup are traceable; table/equation limits remain explicit. |
| FedOpt (additional layout check) | 2 | Small-cap section heading is correctly detected despite absence of a bold flag. |

Source block text and bounding boxes were checked against rendered original pages. Poppler was unavailable in the host/bundled paths checked; review PNGs were rendered using the installed PyMuPDF renderer and kept in ignored `work/pdf-review/`.

Observed parser corrections:

1. The author's initial “H.” on FedAvg's first page was initially mistaken for an appendix heading. Alphabetic headings now require a later page; a regression test covers the example.
2. Rotated arXiv margin text and small standalone mathematical fragments initially entered fixed chunks. Rotated margins and equation-like fragments are excluded while original text remains stored.
3. PyMuPDF's default table detector missed tables with only horizontal rules, including the SCAFFOLD notation table and FedProx dataset table. Caption-associated horizontal-rule regions now flag these cells for exclusion. A synthetic table regression test verifies the region detection.
4. ICLR small-cap headings were initially missed because they are smaller than body text and lack a bold font flag. Numbered uppercase headings now support that layout. Appendix boundaries are restored, preventing appendices from being absorbed into the references region.

Acceptance evidence: corpus checksum validation passed; every source span, cleaning map, page range and section membership passed canonical validation; all documents had no serious warnings. Structural inspection is representative sampling, not an exhaustive visual audit of all 614 pages. Footnotes can interrupt the prose stream, ligatures are retained, and complex/undetected tables or equations can still require manual review. Docling was not evaluated because the reviewed core prose layout became usable with the documented parser corrections; it remains a fallback if later questions expose material layout failures.

## Corpus acquisition and provenance notes

The final 40-paper inventory preserves the original 20 and adds 18 versioned arXiv papers, the published CCS Secure Aggregation PDF and the published Scientific Reports medical-collaboration PDF. Original PDF hashes/versions are unchanged. All sources and seven-field metadata are in [the manifest](../data/corpus_manifest.jsonl). The permanent acquisition helper is [download_corpus.py](../scripts/download_corpus.py); it checks exact pinned bytes and leaves the manifest unchanged. It reports a manual source URL when access is blocked. Acquisition of every remote endpoint was not repeated during delivery; all 40 local files passed integrity checks.

The completed tokenizer migration verified all 26 benchmark passages against unchanged PDF versions, pages, raw block text, coordinates, exact quotes and offsets before replacing parse/block IDs. Current setup no longer depends on the old ignored acquisition/migration helpers. Both splits validate; the source-verified test freeze retains `human_review_complete: false`. The final source audit and comparison are in [the final report](final_evaluation.md).
