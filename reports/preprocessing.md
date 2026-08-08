# Phase 1 verification

Recorded 2026-10-12 (Asia/Tashkent). All 20 source PDFs were acquired with pinned versions and checksums and parsed into 657 fixed chunks. This verifies local preprocessing; it does not measure hosted embedding or answer quality.

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
