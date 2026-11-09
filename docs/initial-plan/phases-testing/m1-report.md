# M1 report: extraction quality

- **Date:** 2026-10-11
- **Code:** held-out run on `6dd2d47` (code = main `41209fd`; the commits after it touch docs only). Final tuning code: `59a22be` (p1 + p2); the listening safety net (llm-design v4.16) came after baseline4 and is in the held-out code.
- **Models:** vision `numind/nuextract3:Q6_K`, reasoning `qwen3.5:4b` (placeholder until M2). Options `num_ctx` 16384, `temperature` 0, `seed` 42; 1 run per change (structure §7).
- **Fixtures:** 19, all `verified_by: teacher` in `fixtures/MANIFEST.sha256`.
  - Tuning (14): `L12-TS12-D1-2025-docx`, `L8-GK2-DG-2025-photo`, `L8-GK2-DL-2025-photo`, `L8-GK2-DM-2025-photo`, `L8-HK1-NHT-D4-2025-photo`, `L8-HK1-NHT-D6-2026-photo`, `L9-T01-book-lop9-50de`, `L9-T08-book-lop9-50de`, `L9-T23-book-lop9-50de`, `L9-T29-book-lop9-50de`, `L9-T36-book-lop9-50de`, `L9-TS10-D4-2025-pdf`, `L9-TS10-D5-2025-pdf`, `lop8-hk1-de1`.
  - Held-out (5): `L8-GK2-DK-2025-photo`, `L8-HK1-NHT-D2-2025-photo` (photos); `L9-T15-book-lop9-50de`, `L9-T43-book-lop9-50de`, `L9-TS10-D6-2025-pdf` (typed PDFs).
- **Scope:** minimal M1 (teacher, structure §7): p1 and p2 kept; p3, p4 and further refinement wait until after step 22.

Row numbers below are line numbers in the committed `eval-history.csv` (line 1 is the header).

## 1. Held-out metrics (CSV row 9)

All llm-design §8 extraction metrics. Held-out run: 5 fixtures, 0 failed, 29 calls, 31 min.

| Metric | Held-out (row 9) | PRD §12 target | Met? |
|---|---|---|---|
| CER (question text) | 0.3916 | — (see transcription goal) | — |
| Stimulus CER | 0.2030 | — | — |
| Structure overall | 0.6664 | — | — |
| · section count | 0.9000 | — | — |
| · question count | 0.8571 | — | — |
| · question match | 0.8010 | ≥ 0.98 questions correct without edits (proxy) | not met |
| · groups | 0.7222 | — | — |
| · skill | 0.7500 | — | — |
| · types | 0.8662 | — | — |
| · option count | 0.9108 | — | — |
| · option text | 0.7647 | — | — |
| · blanks | 0.7580 | — | — |
| · underline | 0.0000 | — | — |
| · bold | 0.0000 | — | — |
| Meta accuracy | 0.1765 | — | — |
| Answer-reading accuracy | 0.8367 (n = 196) | ≥ 0.95 | not met |
| Calibration (wrong readings flagged) | 0.2500 (8 of 32; Wilson 0.1325–0.4211) | ≥ 0.90 | not met |
| Flagged-correct rate | 0.0427 | — | — |
| Key accuracy | blank (`key_n` 0) | high accuracy | not measured |
| Key mapping accuracy | blank (`key_mapping_n` 0) | — | not measured |
| Verdict accuracy, exact score match | blank | — | grade-graph metrics (M2), not extraction |
| Time, tokens, VRAM per node | §3 below | measured, no target | reported |

Notes:
- **Printed transcription:** §8 has no metric for "questions correct without edits". The nearest is `structure_question_match` (0.801); CER 0.392 also says the goal is far off.
- **Answer accuracy:** 0.837 includes the 3 typed PDFs, which score 1.0 because D26 reads no answers on typed files (120 of 120). On the 2 photo papers it is 44 of 76 = 0.579 (DK 26/40, NHT-D2 18/36).
- **Calibration:** all 32 wrong readings come from the 2 photo papers (DK 6/14, NHT-D2 2/18). NHT-D2 lost 10 of 36 questions (question count 26/36), and answers with no row count as wrong and never flagged (caveat B2, §5).
- **Key metrics** are blank because no held-out (or tuning) fixture has a key page (`is_key` false on every page).
- **Other PRD §12 rows:** stop/resume is covered by the Phase 0 stop/resume tests, not by M1; the fixture set is 19 (14 + 5) on the way to 30+.

## 2. Tuning progression (tuning set, 14 papers)

| CSV row | Run | Code | CER | Stimulus CER | Structure | Types | Answer acc. | Calibration | s / paper |
|---|---|---|---|---|---|---|---|---|---|
| 3–5 | baseline (3 identical runs) | 719d0f1 | 0.4465 | 0.4014 | 0.6153 | 0.6719 | invalid (B1) | invalid (B1) | 447 |
| 6 | baseline2 | 9d8a4e2 | 0.4473 | 0.4014 | 0.6150 | 0.6765 | 0.6716 | 0.7921 | 733 |
| 7 | baseline3 | f0291a7 | 0.3033 | 0.2875 | 0.6290 | 0.6119 | 0.7970 | 0.6273 | 386 |
| 8 | baseline4 | 59a22be | 0.3169 | 0.2800 | 0.6685 | 0.8822 | 0.7657 | 0.6535 | 359 |

Changes:
- **Row 3–5 → 6, the fixes:** answer-prompt bug B1 (the `alt_question_id` enum overflowed `num_ctx`, so the instructions were dropped) and B4 (prompt-truncation checks); the DOCX text-page fix.
- **Row 6 → 7, long-DOCX fix:** a DOCX splits into text pages at question starts (DOCX CER 1.00 → 0.32).
- **Row 6 → 7, speed bundle 1 (llm-design v4.14):** tile re-read off by default; no retry of a capped vision output. Calls 140 → 66.
- **Row 6 → 7, D26 (PRD v4.8, llm-design v4.15):** typed files (PDF text layer, DOCX) skip answer reading. This lifts answer accuracy on typed papers to 1.0; over the 6 photo papers it went 0.47 → 0.50 (structure §7, history log 2026-10-11).
- **Row 7 → 8, p1 (question types and skills):** types 0.61 → 0.88.
- **Row 7 → 8, p2 (passages into `stimulus`):** structure 0.629 → 0.669, stimulus CER 0.288 → 0.280. CER rose 0.303 → 0.317 from questions lost at section boundaries (§5).
- **After row 8, the listening safety net (llm-design v4.16):** a "listening" section with real questions is kept and flagged for Review. Offline on baseline4's pages, NHT-D4 went 12 → 28 questions; the other 13 papers were unchanged.

## 3. Speed, VRAM and tokens per node

| | baseline4 (row 8, 14 tuning) | held-out (row 9, 5 held-out) |
|---|---|---|
| Wall time | 5023.6 s | 1892.0 s |
| Time per paper | 358.8 s | 378.4 s |
| Peak VRAM | 4357 MB | 4357 MB |
| Calls | 66 | 29 |
| Tokens in / out | 260 593 / 71 763 | 113 837 / 26 311 |
| `transcribe_page`: calls, tokens in / out, time | 49, 144 579 / 54 858, 3381.5 s | 21, 61 735 / 18 869, 1177.4 s |
| `read_answers_page`: calls, tokens in / out, time | 17, 116 014 / 16 905, 1608.8 s | 8, 52 102 / 7 442, 700.9 s |
| `retranscribe_tiles` | 0 (off) | 0 (off) |
| `prepare_pages` time | 8.4 s | 3.8 s |
| Other nodes (no LLM calls) | < 0.2 s each | < 0.1 s each |

Held-out time per paper: the photo papers took 544.8 s (DK) and 662.5 s (NHT-D2), and the typed PDFs 215–244 s, because they skip answer reading (D26). `read_header`, `sanity_check`, `read_key_pages` and `map_key` made no calls (no key pages, no picked test).

## 4. Decisions

Decision: tiles=off

The tile re-read pass is off by default (`[extract] retranscribe_tiles = false`, speed bundle 1, llm-design v4.14). Neither full nor half tiles are used: offline it measured worse (tuning CER 0.341 with tiles vs 0.287 without, history log 2026-10-10T18-05-37), and it took 27% of node time in the first baseline (`fixtures/_runs/2026-10-08T10-22-baseline/ANALYSIS.md` §4) and about 19% in baseline2 (CSV row 6: 1916.8 of 10231.5 s).

Decision: vision=numind/nuextract3:Q6_K

This is unchanged from Phase 0. No candidate model was tried under minimal M1 (waiver).

Thresholds (fitted read-only on baseline4's 6 photo papers, `fixtures/_runs/2026-10-11T11-25-baseline4/THRESHOLDS.md`):

| Threshold | Value | Set in | Status |
|---|---|---|---|
| `reading` | 0.7 | `graphs/extract.py` `ExtractThresholds` | the teacher kept 0.7 (the analysis recommended 0.9) |
| `key_photo` | 0.7 | `graphs/extract.py` `ExtractThresholds` | not fittable (no key-photo fixture) |
| `looks_like` | 0.85 | `ExtractThresholds` → `domain/similarity.py` `LOOKS_LIKE` | kept; not fitted on true duplicates |
| `possibly` | 0.5 | `ExtractThresholds` → `domain/similarity.py` `POSSIBLY` | kept; separates the measured pairs cleanly |
| `sanity` | 0.5 | `ExtractThresholds` | unchanged (not in the M1 list) |
| `key_margin` | 0.7 | `graphs/grade.py` | M2, not M1 |

Config defaults (for R-M1.4 / R21.4):
- The thresholds have no TOML surface. They are the `ExtractThresholds` dataclass defaults, and `ExtractDeps` is built without thresholds. The defaults equal the table above, so no code changed.
- The tiles and vision decisions match `llm/defaults.py` (`DEFAULT_EXTRACT["retranscribe_tiles"] = False`; `DEFAULT_ROLES["vision"]["model"]`).

## 5. Known limits

Details for each are in structure §7 (the M1 entries).
- **Lost questions at section boundaries:** T23 and TS10-D4 lose 8 each in baseline4; on held-out, NHT-D2 has 26 of 36 questions and T15/T43 have 35 and 34 of 40. This waits for parked p3 (headings and page continuation).
- **Listening safety net:** only a "listening" section holding real questions is rescued, and a Review item is raised. Other wrongly merged sections still lose questions.
- **Metric caveats:**
  - B2: calibration and answer accuracy are dominated by answers with no row and by blank papers. A no-row answer counts as wrong and is never flagged.
  - B3: stimulus CER skips groups whose questions are all missing.
  - Answer accuracy on typed papers is 1.0 by D26.
  - With 1 held-out run and 32 wrong readings, the intervals are wide.
- **Signs and notices:** the prompt transcribes a sign as text, but the fixtures give a sign group `stimulus` null with the sign only as a picture. Parked.
- **DOCX formatting:** a DOCX without pictures becomes text pages and loses bold and underline (`L12-TS12-D1-2025-docx`). The fix is decided after M1.
- **PDF text layer:** typed PDFs are read from the text layer, which has no underline. `structure_underline` and `structure_bold` are 0 on every row.
- **Parked until after step 22:** p3, p4, change 4 (a smaller photo answer prompt), the NHT-D4 answer drop, and the `-Check` default failing with `-Set heldout`.

Gaps against PRD §12 and the M1 checklist are listed in `docs/initial-plan/waivers/M1.md` (draft, to be signed by the teacher).
