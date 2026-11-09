# Data Model — ETACH

| | |
|---|---|
| Version | **v1.35.3** (2026-11-09) |
| Companion to | [`PRD.md`](PRD.md), [`llm-design.md`](llm-design.md), [`initial-plan/plan.md`](initial-plan/plan.md). Each plan pins the versions it builds on in its "Based on" line |
| Where it lives | Python **pydantic** classes in the sidecar (the source of truth), **SQLite** tables owned by the sidecar, and TypeScript types for the React frontend **generated** from the pydantic JSON Schema |

### Changelog
| Version | Date | Change |
|---|---|---|
| **v1.35.3** | 2026-11-09 | Patch, teacher (maintenance): the changelog rows of the initial plan moved to `initial-plan/changelogs.md` |
| v1.35.2 | 2026-11-09 | Patch, teacher: the code names follow the app's name (`etach` package and CLI). No class or table change |
| v1.35.1 | 2026-11-03 | Patch, after the initial plan: the title and §5's folder layout no longer name the old app; the finished initial plan moved to `docs/initial-plan/`. No class or table change |

Earlier rows (2026-09-28 to 2026-10-31, the initial plan) are in [`initial-plan/changelogs.md`](initial-plan/changelogs.md).

---

## 1. The big picture

```
                           ┌──────────────┐
                           │   Student    │ light profile
                           └──────┬───────┘
                                  │ 0..n
┌──────────┐ 1   0..n ┌───────────┴──────┐ n..1 ┌────────────────────┐ 1..n ┌──────────────┐
│  Thread  ├──────────┤     Attempt      ├──────┤    Test (bank)     ├──────┤  AnswerKey   │ per question
│ test_id ─┼──────────┼──────────────────┼─────►│ metadata + content │      └──────────────┘
└────┬─────┘          │ superseded_by    │      │ merged_into        ├──────┬─ TestPage (bank photos)
     │ 1..n           └──┬─────┬─────┬───┘      └─────────┬──────────┘      ├─ QuestionTag
┌────┴─────┐             │     │     │                    │                 └─ Explanation (cache)
│   Run    │   Answer ───┘     │     └── GradeReport      │
│extract / │   (1 per q.)  AttemptPage (student's photos) │
│ grade    │                                              │
└────┬─────┘                                              │
┌────┴─────┐ 1..n ┌───────────┐                           │
│   Step   ├──────┤  LlmCall  │ every model request/response (+thinking, logprobs)
└──────────┘      └───────────┘
ReviewItem ──► test / attempt / question (typed columns) · File ──► content-addressed images
```

- A **Test** is the paper, stored once in the bank.
- An **Attempt** is one student's filling-in of that paper.
- A **Thread** is where the teacher dropped the photos: one test, and 0 or 1 *current* attempt. A re-extraction can supersede an attempt.
- A **Run** is one execution of a LangGraph workflow in a thread, made of **Steps**.
- A **GradeReport** holds the Grade button's narrative output for one attempt.

---

## 2. Classes (pydantic, abbreviated)

### 2.1 Student
```python
class Student(BaseModel):
    id: str                      # "S-0007"
    full_name: str               # "Ngô Thị Mỹ Hòa"
    name_search: str             # lowercase, accents removed (used for matching names read from paper)
    class_name: str | None       # "8TC11"
    school: str | None
    grade: int | None
    notes: str = ""
    created_at: datetime
```
There are no weak-point fields: weak points are **computed** (§4).

### 2.2 Test (the bank)
```python
class Test(BaseModel):
    id: str                      # "T-0042"
    meta: TestMetadata
    content: TestContent
    content_schema_version: int  # the only place the content version is stored
    fingerprint: str             # normalized printed text for duplicate comparison
    points_possible: float       # listening excluded, e.g. 9.0
    source_run_id: str | None    # UNIQUE: the extract run that created it (idempotent save)
    merged_into: str | None      # set when merged; merged tests are hidden from search and comparison
    created_at: datetime; updated_at: datetime

class TestMetadata(BaseModel):
    # the fields the teacher asked for
    occasion: str                # MidTerm | FinalTerm | NationalExam | EntranceExam | GiftedExam | UnitTest
                                 # | FifteenMinuteTest | GrammarPractice | TopicPractice | Placement | "Other:<text>"
    grade: int | None
    year: str | None             # "2025-2026" or "2026"
    school: str | None
    created_by_ai: bool = False
    # extras
    term: int | None             # 1 | 2
    test_number: str | None      # "1" (also from file names like "De1")
    variant: str | None          # "K"
    test_code: str | None        # mã đề
    region: str | None
    source: str | None           # author/publisher of mock tests
    textbook: str | None
    units: list[str] = []
    duration_minutes: int | None
    exam_format: str | None      # picks the prompt profile for calls after transcription (llm-design §4, §8)
    omitted_sections: list[OmittedSection] = []   # listening (not stored) and writing (stored, graded=False):
                                                  # title, printed question range, points; excluded from points_possible
                                                  # v1.25: kind = listening | writing (None = stored before; such a
                                                  # section is listening when none of its numbers is a stored question);
                                                  # GET /attempts/{id} carries listening_skipped {first, last} | null
    tags: list[str] = []
    parent_test_id: str | None   # for generated tests (later)
    extra: dict[str, str | int | float | bool] = {}
    edited_fields: list[str] = []   # fields the teacher changed by hand; extraction never overwrites these

    def display_name(self) -> str: ...   # v1.11: "Grade 8 - Final Term 1 - <school or source> - 2025 - Test 7"
                                         # v1.13: "Unit Test", "15-minute Test"; an unknown occasion is left out;
                                         # a teacher-set name (`display_name` in edited_fields) is kept, never remade;
                                         # v1.13.1: stored in extra["display_name"]; an emptied name = automatic again;
                                         # v1.13.2: no parts at all -> "Untitled test" (teacher)
                                         # (grade - occasion + term - school, else source - year - test_number),
                                         # English, " - " between parts, empty parts left out

```
**Difficulty notes dropped** (v1.23, step 22.5.4, decision D10): `test_difficulty_notice_comment_by_ai` (and its `DifficultyNotes`, `SectionDifficulty`, `TrapItem` classes) is gone; no screen, report or Word file showed it. Migration `0013_drop_difficulty_notes` adds the guard table `difficulty_notes_pending` with one row (§3); while it is there, the first start removes that one key from every stored test's `meta` in one transaction (raw JSON, `store/repos/difficulty_pass.py`) and deletes the row in the same transaction, so it runs once. Nothing else changes: not the other meta fields, `updated_at`, the columns, the search rows or any other table. It runs first, before the passes that read tests through the models.

**Where metadata comes from**, in priority order:
1. the teacher's edits on the test panel (recorded in `edited_fields`);
2. the printed header (patterns in code);
3. the file name;
4. empty.

Only `occasion` is required. If it's unknown it becomes `Other:unknown` plus an `unknown_occasion` Review item.

**All metadata writes go through one function, `write_test_meta()`**, which updates `meta`, the denormalized columns, `display_name` and the search index together (§5).

### 2.3 Test content
```python
class TestContent(BaseModel):
    sections: list[Section]      # (the version lives in Test.content_schema_version)

class Section(BaseModel):
    id: str; number: int         # canonical I, II, …
    printed_title: str; title: str; instructions: str
    # v1.21 (D2): an untitled section (printed_title and title empty, or only a numeral such as "I." / "1.")
    # takes its title from `skill` in English capitals, at extraction and once for stored tests at first
    # start: "I." + pronunciation → "I. PRONUNCIATION", word_form → "WORD FORM". `mixed` (or an unknown skill)
    # stays untitled. A title with words is never changed (content edits are not recorded per field, so a
    # title with words counts as typed). Option labels: v1.21 also cleans "A..", a fullwidth or look-alike
    # Cyrillic/Greek capital and invisible characters to the bare letter (merge, test text, first start)
    points: float; points_source: Literal["printed", "assumed", "equal"]   # v1.19: always "equal" = the
    # section's graded questions × (10 ÷ graded questions in the test) (PRD D13 v8.0), recomputed on every
    # content save; "printed"/"assumed" only in rows written before v1.19 (rewritten at first start)
    skill: str                   # pronunciation | stress | grammar | vocabulary | communication | signs
                                 # | reading | word_form | rewrite | writing | mixed
    graded: bool = True          # False for writing sections (PRD D12): the prompt is kept for printing,
                                 # but it has no answers, no key, no grading, and its points are in omitted_sections
    groups: list[QuestionGroup]

class QuestionGroup(BaseModel):
    id: str
    stimulus: RichText | None    # passage / dialogue / dictionary entry; cloze blanks "(17) ____"
    pictures: list[PictureRef]   # rendered as "[Hình: files/ab/ab12….jpg · trang 3]"
    questions: list[Question]

class Question(BaseModel):
    id: str                      # stable, e.g. "q-7f3a"
    number: int                  # canonical
    printed_number: int          # as on the paper (can repeat on sloppy papers; never used as a key)
    page_no: int                 # page of the bank test it is printed on (v1.25: a typed-PDF question's text may
                                 # run over a page break; page_no = the page its text starts on: merge_pages(placed=…), PiecePages)
    answer_form: Literal["choice", "word", "sentence", "writing"]   # v1.22 (D9): replaces the 11-value `type`;
                                 # chosen by the model from the printed layout (§2.3b)
    context: Literal["single", "paragraph"] | None = None   # v1.22: set by code, never by the model: `paragraph`
                                 # when the group has a `stimulus`, else `single`; None for `writing`
    stem: RichText | None        # None for cloze items whose blank lives in the group stimulus
    options: list[Option] | None
    cue: str | None
    answer_start: str | None = None   # v1.16: a `sentence` question (v1.22; was rewrite/combine): the words the
                                 # paper prints to start the answer ("My brother …"); the sentence key forms (§2.4)
                                 # use it before guessing from stem/cue
    points: float
    old_type: str | None = None  # v1.22: read-only; the question's `type` before step 22.5.3 (mcq, gap_fill, …),
                                 # kept by the first-start pass so a revert loses nothing. Read only by a revert;
                                 # None for questions made later
    old_options: list[Option] | None = None  # v1.22.2: read-only; a True/False choice's options before the
                                 # first-start pass or an extraction relabelled them T/F (e.g. A. FALSE, B. TRUE). Read by a
                                 # revert, and (v1.30) to map a key-photo or student letter to T/F
                                 # and (v1.29) a `key_unmapped` Fix onto the question (§5.3)
    # skill tags are NOT stored here: they live only in question_tags (§3)

class PictureRef(BaseModel):
    file_id: str; page_no: int

RichText = str   # Markdown subset: **bold**, <u>underline</u>, line breaks
```

### 2.3b Answer form (v1.22, step 22.5.3, decision D9)
The answer form is the shape of the student's answer: `choice` (a letter, or True/False), `word` (one word or a short phrase in a blank), `sentence` (a whole sentence), `writing` (a paragraph or essay, not graded). The page prompts ask the model for it from the printed layout (llm-design §4); `context` is never asked for: code sets it from the group's `stimulus` whenever a `QuestionGroup` is built.

- **True/False** is a `choice`. When the model gives a `choice` without options and the section instructions or the stem say True/False (`True … False`, `T/F`, `(T) … (F)`), code adds the two options `T. True` and `F. False` (`renumber.choice_options`). A `choice` whose options were lost for another reason (e.g. at a page break) gets none, so it still fails the option check. **v1.22.2 (G1):** a `choice` the model gave exactly two options whose texts, trimmed, case-folded and without trailing punctuation, are `true` and `false` in either order (also `đúng` and `sai`, NFC) gets the same two options `T. True`, `F. False` in that order (`models.true_false_letters`; e.g. `A. FALSE`, `B. TRUE`); a two-option choice with other texts, or a choice with 3–4 options, is unchanged. Answer reading then offers `T`/`F`, and the test text and the Word export show them.
- **Validators** go by form: the blank check applies to a `word` question with no `cue` and no options (what a `gap_fill` was); a `word` question with a cue (a former `word_form` / `verb_form`) or with printed options is not blank-checked, as those types were not. The option check applies to `choice` questions (2–4 options labelled A, B, (C, (D)) in order, or the `T`/`F` pair). Their IDs stay `gap_fill_blank` and `mcq_options`, because stored review items carry them.
- **Sentence keys** (§2.4) are written for `sentence` questions.
- **Grading** (llm-design §5 `grade`; plan Appendix B.5 by form): `choice` → exact match; `word` → exact match after normalising, a 1–2 letter difference is a spelling near miss; `sentence` → exact match after normalising, else the AI judge (one judge rule for every sentence: combine's separate rule is gone); `writing` → not graded (no answer row). B.5 rows 12 (ordering/matching) and 13 (combine) are retired: a former ordering question is a `sentence`, matching a `choice`, combine a `sentence`.
- **Stored tests: the first-start pass.** Migration `0012_answer_form` adds the guard table `answer_form_pending` with one row (§3). While the row is there, the first start maps every question of every stored test in one transaction and deletes the row in the same transaction, so it runs once; it runs before the other first-start passes, which read tests through the models (`store/repos/answer_form_pass.py`). The map: mcq, true_false, matching → `choice`; gap_fill, word_form, verb_form → `word`; rewrite, combine, ordering, short_answer → `sentence`; writing → `writing`. The old value goes to `old_type`; a `true_false` question without options gets the `T`/`F` options; `context` is set from the stimulus; a `choice` whose two options read True/False (v1.22.2) gets the `T`/`F` options, its stored options go to `old_options`, and in the same transaction its key (`answer_keys.accepted`), its student answers (`answers.value`, `value_norm`, `alt_value`, `teacher_override`), `explanations.wrong_answer_norm` and the letters in the `proposal` of its **open** Review items (v1.22.3: `uncertain_answer` `value` / `alt_value`, `box_inline_conflict` `box_value` / `inline_value`, `uncertain_key` `accepted`, so an Accept stores the new letter) are relabelled: the letter whose text meant True → `T`, False → `F` (the meaning is the same, so verdicts and grade reports stay; resolved Review items are history and keep their letters; swapped labels such as `T. False`, `F. True` are safe, the explanation rows go through a temporary value so no primary key collides; v1.23: a question with explanation rows for both an old letter and the T/F letter it maps to, such as rows `a` and `f` on `A. FALSE` / `B. TRUE`, keeps one row, the one already holding the T/F letter, and the other is dropped, so the pass cannot abort). Apart from that, only `tests.content` changes: not `updated_at`, the points or the fingerprint, and no other student answer, key, verdict, grade report, review item or `regrade_pending` row; graded attempts are not marked for re-grade. A question or page transcript written before the upgrade (a run paused across it) is mapped the same way when it is read.
- **Revert.** `revert_question_data` / `revert_content_data` (same module) give the old shape back, for a revert of step 22.5.3 only: `type` = `old_type` (a question made later gets the first old type of its form: choice → mcq, word → gap_fill, sentence → rewrite, writing → writing), and the True/False options the pass added are removed; a relabelled True/False choice gets its `old_options` back (a revert of its key and student answers maps `T`/`F` back to those labels the same way).

### 2.3a The test as text (v1.9, PRD D27)
The test page in the app is the test's **text form**: `render(content) → text` and `read(text, previous_content) → content | errors` in the sidecar (`domain/test_text.py`). Rules:
- **Round trip:** `read(render(c), c) == c` for every valid `TestContent`.
- **Identity:** a question that is still there after an edit (same section, same canonical number, or the closest match when numbers shift) keeps its `id`, so its key, answers, tags and explanations stay attached. New questions get new ids.
- **What is in the text:** section headings (no points since v1.21), instructions, group stimuli (passages, dialogues), pictures as their D11 placeholder line, question stems with numbers, options, cues. Metadata (occasion, grade, …) stays on the chips. Keys and answers are not in the test text.
- **Errors:** text that cannot be read gives errors with line numbers; nothing is saved. A read result goes through the same validation as any content edit (`write_test_meta`'s content path).
- **Dropping a question** that has a key row or answers needs the teacher's confirmation; then its key, answers, tags and explanations are deleted, and graded attempts follow the §5.3 follow-up rule.
- DOCX export (step 22.1.6) uses the same structure.

**Grammar (v1.9.1).** The text looks like the printed paper. Each line is one of these, tried in this order; the first form that fits wins:

| Line | Example | Meaning |
|---|---|---|
| Escaped | `\12. not a question` | A leading `\` makes the rest plain text (only odd content needs it; `render` adds it). |
| Passage | `[Passage]` … `[End of passage]` | The group's `stimulus`, kept exactly as typed, blank lines included. A passage or a picture starts a new group. |
| Picture | `[Hình: files/ab/<id>.jpg · trang 3]` | A `PictureRef` (D11); the file id is the path's file name. |
| Page | `— Page 2 —` (or `-- page 2 --`) | The paper page of the questions below it (`page_no`). |
| Section heading | `# II. WORD FORM` | **v1.21 (D7):** `#`, then the `printed_title`; no points. A bracket at the end may say `not graded` (a writing section: `# VI. WRITING  [not graded]`) and `title: <title>` (when `title` differs); a bracket that says anything else is part of the title (a title that ends in a bracket of its own gets an empty `[]` after it). Each question's value is not in the text: `GET /tests/{id}` gives `points_each` (10 ÷ graded questions) for the line under the title. The older form below still reads as a heading, and its points are ignored. **Before v1.21:** `II.  [2.5 points]`: the `printed_title`, then the points in brackets at the end of the line. Forms: `[2 points]` (split evenly), `[0.25 points each]`, `[3 points: 1 / 1 / 0.5 / 0.5]` (per question); then optional parts after commas: `assumed` (`points_source`), `not graded` (a writing section), `title: <title>` (when `title` differs). Changing the points makes them `printed`. **v1.19:** the points are written from the equal rule (PRD D13 v8.0) and a typed value is ignored on save (the text still reads back with or without the bracket); `assumed` is no longer written. |
| Question | `12. She ____ to school.` | A question with its `printed_number` and the first line of its `stem`. `12.` alone: the stem starts on the next line (or there is none). Printed numbers may skip (a left-out listening part, a deleted question): gaps are not an error (v1.11). |
| Option | `   A. goes`, or `   A. go    B. goes` | Options (label A–H or `???`); several may share a line, two or more spaces apart. |
| Cue | `   Cue: (consume)` | The question's `cue`. |
| Start | `   Start: My brother` | The question's `answer_start` (v1.16). |
| Text | anything else | More lines of what is above: the section's `instructions`, the stem, an option's text or the cue. Blank lines are spacing; at the ends of a field they are dropped. |

Section and question `number`s are not in the text: they stay as they were while the order of sections and questions is unchanged, else they are recounted (graded sections first, D10). `id`, `skill`, `type` and `None` versus `""` come from the previous content for an item that matches one there; a new section gets `skill` `mixed` (`writing` when not graded), a new question an inferred `answer_form` (v1.22: `writing` in an ungraded section; options → `choice`; a `Start:` line → `sentence`; a `____` blank or a cue → `word`; else `sentence`; the text shows no form) and a `q-` id like the extract run's. Questions match by identical text and number, then identical text, then the closest text in order. Groups without a passage or pictures are kept by that matching and have no line of their own.

**Errors** name their line: text before the first heading, an option or cue with no question above it, a `[Passage]` with no end, a heading whose brackets cannot be read, a per-question list of the wrong length. A save that adds a content-check failure (`validators`) is refused at the question's line; failures that were already there do not block it.

### 2.4 Answer key
```python
class AnswerKey(BaseModel):
    test_id: str; question_id: str
    accepted: list[str]          # first = canonical; others = accepted variants
                                 # v1.15: for a `sentence` question (v1.22; was rewrite / combine), every key write (key photo, AI, teacher)
                                 # adds the forms: full; full without the final "."; without the opening words the
                                 # paper already prints for the answer (from the question's stem/cue); without both.
                                 # Kept unique, canonical first; a teacher edit can remove any of them.
    reason_vi: str | None
    source: Literal["from_key_photo", "ai", "teacher_edit"]
    status: Literal["ai_unverified", "ai_verified", "ai_uncertain", "teacher_verified", "from_key_photo"]  # v1.25
    confidence: float | None     # logprob-based (AI and key photo)
    updated_at: datetime
    checker: KeyCheck | None = None   # v1.24 (step 22.5.5): what verify_key said when it did not confirm the key; v1.24.1: cleared when the key becomes teacher_verified

class KeyCheck(BaseModel):       # v1.24; stored as JSON in answer_keys.checker; the Key read carries it
    status: Literal["disagreed", "unsure", "did_not_finish"]   # unsure (v1.32): the checker answered `?`, reasoning only; did_not_finish: cut off or failed twice
    answer: str | None = None    # the checker's own key (disagreed only)
    reasoning: str | None = None
```
**Lifecycle and precedence:**
- `teacher_edit` / `teacher_verified` beats `from_key_photo`, which beats `ai`. A write never replaces a higher-precedence row (a guarded upsert).
- A key-photo reading at or above the confidence threshold (0.7) is stored as `from_key_photo` (v1.25; it keeps its confidence and is never `ai_verified` without a second call). Below the threshold it is stored as `ai_unverified`, so it gets checked like an AI key. `ai_verified` means a second call (`verify_key`) agreed.
- **Key-photo pass (v1.25, migration `0015_key_photo_status`).** Before v1.25 a confident key-photo key was stored as `ai_verified`. A one-time first-start pass (guarded by `key_photo_pending`, one transaction, like the answer-form pass) moves the rows with source `from_key_photo`, status `ai_verified` and confidence ≥ 0.7 to `from_key_photo`. They are told apart reliably: `verify_key` checks only `ai_unverified` keys, and a key-photo key is `ai_unverified` only below 0.7 (the threshold is unchanged since step 9A), so a key-photo key a check verified has a lower confidence and stays. Nothing else changes (confidence, `accepted`, `updated_at`, explanations).
- The AI fast pass writes `ai_unverified`. Verification turns it into `ai_verified` or `ai_uncertain`.
- **When a key row changes, that question's explanations are deleted** (they described the old key).

### 2.5 Attempt, AttemptPage, Answer, GradeReport
```python
class Attempt(BaseModel):
    id: str                      # "A-0103"
    test_id: str
    thread_id: str
    student_id: str | None       # None = "Chưa rõ" (plus an unknown_student Review item)
    student_name_read: str | None  # as read from the paper ("Ngô Thị Mỹ Hòa")
    class_read: str | None         # "8TC11"
    source_run_id: str           # UNIQUE: the extract run that created it
    superseded_by: str | None    # a newer attempt that replaced this one (re-extraction)
    status: Literal["extracted", "graded", "reviewed"]   # reviewed = all its Review items resolved
    version: int                 # +1 on every teacher change (override, student, merge); checked by Grade's save
    score_earned: float | None; score_possible: float | None   # snapshot at grading, e.g. 7.5 / 9.0
    created_at: datetime
    taken_on: date               # v1.24 (D11a): the date the student sat the test; default today (local); set at the
                                 # photo check (ExtractInput.taken_on) or by PATCH /attempts/{id}; a NULL (rows before
                                 # migration 0014 got their created_at date) reads as the created_at date. The trajectory
                                 # orders by taken_on, then created_at

class AttemptPage(BaseModel):    # the student's own photos (Review shows these)
    attempt_id: str; page_no: int
    file_id: str                 # the prepared (rotated/resized) image
    source_file_id: str          # the original upload
    rotation: int

class Answer(BaseModel):         # exactly one row per GRADED question of the test (value None = left blank)
    attempt_id: str; question_id: str
    printed_number: int          # what the paper showed (display only; never used to match)
    page_no: int | None          # attempt page where the answer was read
    value: str | None
    value_norm: str | None       # normalize(the effective value: teacher_override if not None, so "" is a blank, else value): lowercase, trim, collapse spaces,
                                 # curly → straight quotes. The single normalization used by grading,
                                 # the explanation cache and the weak-point view. Recomputed on override
    location: Literal["circled_option", "written_in_blank", "answer_box", "margin", "none"]
    confidence: float            # logprob-based (D20)
    low_trust: bool = False      # confidence came from a fallback, not logprobs (llm-design §6)
    reading_unsure: bool         # confidence below threshold (set at extraction); always true when value
                                 # contains "???" (unreadable, PRD D25; value kept as read)
    alt_value: str | None
    alt_question_id: str | None
    verdict: Literal["correct", "incorrect", "uncertain", "ungraded"] = "ungraded"
    near_miss: bool = False
    points_awarded: float | None # full points or 0, no partial credit (PRD D24); None while "?"
    teacher_override: str | None # counts as fully confident when set; "" = the teacher confirmed "no answer" (graded as blank)

class GradeReport(BaseModel):    # the Grade button's narrative output (card + print)
    attempt_id: str; run_id: str
    weak_points: list[WeakPoint] # basics first (§4): {skill_tag, wrong, seen, gap_errors, note_vi,
                                 #   label, level, held_back}; v1.24: label = slipped | consistently_weak |
                                 #   inconsistent | this_paper_only; level A1–B2 or None; held_back = above the
                                 #   lowest weak level. Reports saved before read as None / None / false
    careless_notes: list[str]    # careless / spelling mistakes, listed separately
    summary_vi: str              # 4–6 lines for the teacher
    teacher_questions: list[TeacherQuestion]   # {question_vi, what_answers_mean_vi}
    uncertain_points: float      # points on "?" items (so the print shows "7.5/9, 0.5 unsure")
    created_at: datetime
```

### 2.6 Explanation cache
```python
class Explanation(BaseModel):
    test_id: str; question_id: str
    wrong_answer_norm: str       # = Answer.value_norm (same normalization); cache key together with question_id
    error_type: Literal["gap", "careless", "spelling", "misread_question", "unknown"]
    text_vi: str
    status: Literal["ai", "teacher_edited"]
    llm_call_id: str | None      # v1.24.1: NULL once a thread delete removes the call (v1.10.1)
```
The skill comes from `question_tags`, so it isn't stored here. Explanations are deleted when the question's key changes (§2.4).

### 2.7 Thread, Message, run inputs, Run, Step, LlmCall
```python
class Thread(BaseModel):
    id: str; title: str
    test_id: str | None          # rule: equals the current attempt's test_id; updated inside the merge transaction
    kind: Literal["filled", "blank", "pending"]   # the sidebar groups blank threads under "Blank tests"
    created_at: datetime
    # student and attempt are derived: the current attempt = attempts where thread_id = id and superseded_by is null

class Message(BaseModel):
    id: str; thread_id: str
    role: Literal["teacher", "app"]
    kind: Literal["text", "photo_check", "run_card", "grade_card", "notice"]
    body: dict; created_at: datetime

class PageInput(BaseModel):
    file_id: str
    rotation: Literal[0, 90, 180, 270]
    is_key: bool                 # 🔑 marked at the photo check (D19)
    text_file_id: str | None     # a text page: a PDF text layer or DOCX text stored as a File (kind="text");
                                 # sent to the vision model as text (PRD §11). For a text-only page, file_id = text_file_id.
                                 # A DOCX text over 6 000 characters becomes several text pages, split at a section
                                 # heading or question start, never inside a question (MAX_TEXT_PAGE_CHARS)

class ExtractInput(BaseModel):   # what the teacher confirmed at the photo check
    pages: list[PageInput]       # in the teacher's order
    existing_test_id: str | None # picked through the name search (D1)
    supersedes_attempt_id: str | None   # set when a Review action re-extracts without the pick
    series_from_test_id: str | None = None   # v1.14: "same series as…": the new test starts with that test's occasion,
                                 # term, school, source and year (teacher-set, in edited_fields); the AI fills the rest
                                 # (kept for runs saved before v1.21; the new-thread screen sends series_name)
    series_name: str | None = None   # v1.21 (D5): "same series as <name>": source = the name, and grade, occasion,
                                 # term, year of the newest (created_at) not merged test whose source is that name
                                 # (Unicode case-insensitive), as teacher writes; school not copied; with no such
                                 # test only source. The name joins the series list. Not applied on "replace"
    taken_on: date | None = None # v1.24 (D11a): the date taken from the photo check card; None = today
    again_test_id: str | None = None   # v1.21 (D8): Extract again: the test the photos were read for before;
                                 # compare_bank leaves it out (a new reading of the same photos looks like it)
    again_mode: Literal["replace", "copy"] | None = None   # "replace": save into again_test_id (§5.8);
                                 # "copy": a new test for this thread, as before v1.21

class GradeInput(BaseModel):
    test_id: str
    attempt_id: str | None       # None = key + skill tags only (Make the key, or the key run)
    reason: Literal["button", "key_verified", "merge", "review_fix", "points_fix", "after_extract"]
                                 # v1.33 (step 22.6.4, D4): "after_extract" = the key run every extract
                                 # save queues (§5.2), always with attempt_id None

class Run(BaseModel):
    id: str                      # also the LangGraph checkpoint thread_id
    thread_id: str
    kind: Literal["extract", "grade"]
    input: ExtractInput | GradeInput
    status: Literal["queued", "running", "stopping", "stopped", "interrupted", "failed", "discarded", "done"]
    started_at: datetime | None; finished_at: datetime | None
    error: str | None
    # the current step is derived: the latest steps row with status "running"

class Step(BaseModel):
    id: str; run_id: str
    node: str; item: str | None  # e.g. "page 2"
    try_no: int                  # 1, 2, … (a restart after Stop gets a new row)
    status: Literal["running", "done", "incomplete", "failed", "skipped"]
    started_at: datetime; finished_at: datetime | None

class LlmCall(BaseModel):
    id: str; step_id: str
    role: Literal["vision", "reasoning", "grading_check", "extraction_check", "ocr"]; model: str; prompt_hash: str   # v1.23, v1.26 (ocr): TEXT column, no migration
    request: dict                # image file_ids instead of base64
    response_text: str; thinking_text: str; logprobs: list | None
    status: Literal["streaming", "complete", "invalid", "incomplete", "cancelled", "error"]
    # invalid = finished but failed schema validation
    tokens_in: int | None; tokens_out: int | None; ms: int | None
    created_at: datetime
```

### 2.8 Review item, File
```python
class ReviewItem(BaseModel):
    id: str
    kind: Literal["uncertain_answer", "box_inline_conflict", "uncertain_key", "key_unmapped",
                  "possible_duplicate", "picked_test_mismatch", "unknown_student", "unknown_occasion",
                  "points_assumed", "validator_failed", "merge_unaligned", "unreadable_text"]
    owner: Literal["extract", "grade"]   # which graph creates it (and makes it obsolete on re-run)
    test_id: str | None; attempt_id: str | None; question_id: str | None
    dedupe_key: str              # UNIQUE, e.g. "uncertain_key:T-0042:q-7f3a"
    proposal: dict               # what the app decided (duplicate: includes the question alignment)
    resolution: dict | None      # what the teacher decided
    followup_run_id: str | None  # the run the resolution triggered
    status: Literal["open", "accepted", "fixed", "skipped", "obsolete"]
    created_at: datetime; resolved_at: datetime | None

class File(BaseModel):
    id: str                      # sha256
    path: str                    # "files/ab/ab12….jpg"
    kind: Literal["upload", "derived", "text", "export"]
    derived_from: str | None     # original file for derived (rotated/resized) images
    mime: str; width: int | None; height: int | None
    created_at: datetime
    original_name: str | None    # the dropped file's name for uploads ("Lop8-HKI-De1 (1).jpg"); None otherwise.
                                 # Metadata reads test numbers from it (§2.2 priority 3). Identical bytes keep the first name
```
**`unreadable_text`** (v1.6, PRD D25). One item per test page whose transcription contains `???`.
- Refs: `test_id` set; `attempt_id` and `question_id` None. `owner = "extract"`.
- `dedupe_key = "unreadable_text:<test_id>:p<page_no>"`.
- `proposal = {page_no, file_id, spans: [{path, question_id, text}]}`:
  - `page_no`: the bank test page;
  - `file_id`: that page's image (`test_pages.file_id`), shown in the Review panel;
  - `spans`: one entry per content field that contains `???`. `path` points to the field in `TestContent` (e.g. `sections[2].groups[0].questions[3].stem`); `question_id` is None for section or group text; `text` is the field's full text with the `???` spans.
- The Fix value is `{spans: [{path, text}]}`: the new text of each field (§5.3).

### 2.9 Working types (graph state only, not stored)
```python
class PreparedPage(BaseModel):   page_no: int; file_id: str; source_file_id: str; rotation: int; text_layer: str | None
class PageTranscript(BaseModel): page_no: int; header_text: str | None; sections: list[dict]; llm_call_id: str
class TestDraft(BaseModel):      meta: TestMetadata; content: TestContent; fingerprint: str; points_possible: float
                                 # also: validator failures to report
class PageHeader(BaseModel):     header_text: str; first_stems: list[str]   # picked-test sanity check
class KeyEntry(BaseModel):       question_id: str; accepted: list[str]; confidence: float
class PageAnswers(BaseModel):    page_no: int; answers: list[dict]; student_name: str | None; class_name: str | None
class CompareResult(BaseModel):  best_test_id: str | None; similarity: float
                                 question_alignment: dict[str, str]   # new question_id → bank question_id
class PendingReview(BaseModel):  kind: str; dedupe_key: str; refs: dict; proposal: dict   # written by save
class SavedIds(BaseModel):       test_id: str; attempt_id: str | None
```

---

## 3. SQLite tables

`PRAGMA foreign_keys = ON` and `PRAGMA journal_mode = WAL` are set at every connection.

```sql
-- people & tests
CREATE TABLE students (id TEXT PRIMARY KEY, full_name TEXT NOT NULL, name_search TEXT NOT NULL,
  class_name TEXT, school TEXT, grade INTEGER, notes TEXT DEFAULT '', created_at TEXT NOT NULL);
CREATE INDEX students_name ON students(name_search);

CREATE TABLE tests (id TEXT PRIMARY KEY, display_name TEXT NOT NULL,
  occasion TEXT NOT NULL, grade INTEGER, year TEXT, school TEXT, term INTEGER, test_number TEXT,
  created_by_ai INTEGER NOT NULL DEFAULT 0, parent_test_id TEXT REFERENCES tests(id),
  meta JSON NOT NULL, content JSON NOT NULL, content_schema_version INTEGER NOT NULL,
  fingerprint TEXT NOT NULL, points_possible REAL NOT NULL,
  source_run_id TEXT UNIQUE, merged_into TEXT REFERENCES tests(id),
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX tests_grade ON tests(grade) WHERE merged_into IS NULL;

CREATE TABLE test_key_pages (test_id TEXT NOT NULL REFERENCES tests(id), page_no INTEGER NOT NULL,
  file_id TEXT NOT NULL REFERENCES files(id), PRIMARY KEY (test_id, page_no));   -- v1.12: the key photos, kept
  -- (written by the extract run's save; a merge moves them to the surviving test when it has none)
CREATE TABLE test_pages (test_id TEXT NOT NULL REFERENCES tests(id), page_no INTEGER NOT NULL,
  file_id TEXT NOT NULL REFERENCES files(id), PRIMARY KEY (test_id, page_no));
  -- question ranges per page are derived from Question.page_no

CREATE TABLE occasions (code TEXT PRIMARY KEY, label TEXT NOT NULL, short_name TEXT NOT NULL,
  position INTEGER NOT NULL, builtin INTEGER NOT NULL);   -- v1.17: the ten built-ins seeded by migration; teacher codes
  -- are "Custom:<id>"; TestMetadata.occasion stores the code; a renamed label/short_name remakes automatic Test names
  -- (display_name not in edited_fields); a code used by a test cannot be deleted; built-ins cannot be deleted
CREATE TABLE schools (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE,
  position INTEGER NOT NULL);   -- v1.18: seeded by migration from the distinct trimmed non-empty tests.school and
  -- students.school (case-insensitive with Unicode case folding, so "LÊ LỢI" = "Lê Lợi"; first spelling kept); tests.school / students.school keep the name as text;
  -- a rename updates both and remakes automatic Test names (display_name not in edited_fields) and their search rows;
  -- a name typed on a test or student that is not in the list is added at the end; delete only when unused
CREATE TABLE series (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE,
  position INTEGER NOT NULL);   -- v1.21 (D5): like schools. Seeded by migration 0011 from the distinct trimmed
  -- non-empty meta.source of tests, oldest first (Unicode case folding: "Đề…" = "đề…", first spelling kept);
  -- tests keep the name in meta.source; a rename updates them and remakes automatic Test names and search rows;
  -- a series typed on a test (PATCH meta.source, copy details, series_name) joins the list; delete only when no
  -- (not merged) test uses it
CREATE TABLE test_text_pending (id INTEGER PRIMARY KEY CHECK (id = 1));   -- v1.21: one row until the first-start
  -- pass has run: every stored test gets clean option labels and its untitled sections titled (D2); a test that
  -- changed is saved with equal points, and its open validator_failed items are closed when it now validates
CREATE TABLE answer_form_pending (id INTEGER PRIMARY KEY CHECK (id = 1));   -- v1.22 (migration 0012, D9): one row
  -- until the first-start pass (§2.3b) has mapped every stored question to its answer_form; the pass deletes it in
  -- the same transaction, so it runs once
CREATE TABLE difficulty_notes_pending (id INTEGER PRIMARY KEY CHECK (id = 1));   -- v1.23 (migration 0013, D10): one
  -- row until the first-start pass (§2.2) has removed `test_difficulty_notice_comment_by_ai` from every stored test's
  -- meta; the pass deletes it in the same transaction, so it runs once
CREATE TABLE regrade_pending (test_id TEXT PRIMARY KEY REFERENCES tests(id) ON DELETE CASCADE,
  since TEXT NOT NULL);   -- v1.20: a teacher key change on a test with graded attempts adds the row instead of
  -- queueing key_verified runs; POST /tests/{id}/regrade queues 1 run per graded attempt and deletes the row
CREATE TABLE key_forms_pending (test_id TEXT PRIMARY KEY);   -- v1.15.1: tests whose keys still need the sentence forms
  -- (migration 0006 fills it; list_keys adds the forms once and removes the row; updated_at kept)
CREATE TABLE answer_keys (test_id TEXT NOT NULL REFERENCES tests(id), question_id TEXT NOT NULL,
  accepted JSON NOT NULL, reason_vi TEXT, source TEXT NOT NULL, status TEXT NOT NULL,
  confidence REAL, updated_at TEXT NOT NULL, PRIMARY KEY (test_id, question_id));

CREATE TABLE question_tags (test_id TEXT NOT NULL REFERENCES tests(id), question_id TEXT NOT NULL,
  tag TEXT NOT NULL, PRIMARY KEY (test_id, question_id, tag));
CREATE INDEX question_tags_tag ON question_tags(tag);
-- v1.24 (0014): question_tags.level TEXT (A1|A2|B1|B2|NULL): the question's level from tag_skills, kept on each
-- of its tag rows (and on a merge). A tag's effective level = that level when given, else the skill's base level
-- (grammar: the end of the ID; sections: the last column of sections.txt). answer_keys.checker JSON (KeyCheck);
-- attempts.taken_on TEXT (stored rows got date(created_at, 'localtime')).

-- attempts
CREATE TABLE attempts (id TEXT PRIMARY KEY, test_id TEXT NOT NULL REFERENCES tests(id),
  thread_id TEXT NOT NULL REFERENCES threads(id), student_id TEXT REFERENCES students(id),
  student_name_read TEXT, class_read TEXT, source_run_id TEXT NOT NULL UNIQUE,
  superseded_by TEXT REFERENCES attempts(id), status TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1,
  score_earned REAL, score_possible REAL, created_at TEXT NOT NULL);
CREATE INDEX attempts_test ON attempts(test_id);
CREATE INDEX attempts_student ON attempts(student_id);
CREATE INDEX attempts_thread ON attempts(thread_id);

CREATE TABLE attempt_pages (attempt_id TEXT NOT NULL REFERENCES attempts(id), page_no INTEGER NOT NULL,
  file_id TEXT NOT NULL REFERENCES files(id), source_file_id TEXT NOT NULL REFERENCES files(id),
  rotation INTEGER NOT NULL, PRIMARY KEY (attempt_id, page_no));

CREATE TABLE answers (attempt_id TEXT NOT NULL REFERENCES attempts(id), question_id TEXT NOT NULL,
  printed_number INTEGER, page_no INTEGER, value TEXT, value_norm TEXT, location TEXT NOT NULL,
  confidence REAL NOT NULL, low_trust INTEGER NOT NULL DEFAULT 0, reading_unsure INTEGER NOT NULL DEFAULT 0,
  alt_value TEXT, alt_question_id TEXT, verdict TEXT NOT NULL DEFAULT 'ungraded',
  near_miss INTEGER NOT NULL DEFAULT 0, points_awarded REAL, teacher_override TEXT,
  PRIMARY KEY (attempt_id, question_id));

CREATE TABLE grade_reports (attempt_id TEXT PRIMARY KEY REFERENCES attempts(id),
  run_id TEXT NOT NULL REFERENCES runs(id), weak_points JSON NOT NULL, careless_notes JSON NOT NULL,
  summary_vi TEXT NOT NULL, teacher_questions JSON NOT NULL, uncertain_points REAL NOT NULL,
  created_at TEXT NOT NULL);           -- one current report per attempt; re-grade replaces it

CREATE TABLE explanations (test_id TEXT NOT NULL REFERENCES tests(id), question_id TEXT NOT NULL,
  wrong_answer_norm TEXT NOT NULL, error_type TEXT NOT NULL, text_vi TEXT NOT NULL,
  status TEXT NOT NULL, llm_call_id TEXT REFERENCES llm_calls(id),
  PRIMARY KEY (test_id, question_id, wrong_answer_norm));

-- conversation & workflow
CREATE TABLE threads (id TEXT PRIMARY KEY, title TEXT, test_id TEXT REFERENCES tests(id),
  kind TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL);
CREATE TABLE messages (id TEXT PRIMARY KEY, thread_id TEXT NOT NULL REFERENCES threads(id),
  role TEXT NOT NULL, kind TEXT NOT NULL, body JSON, created_at TEXT NOT NULL);
CREATE INDEX messages_thread ON messages(thread_id, created_at);

CREATE TABLE runs (id TEXT PRIMARY KEY, thread_id TEXT NOT NULL REFERENCES threads(id),
  kind TEXT NOT NULL, input JSON NOT NULL, status TEXT NOT NULL,
  started_at TEXT, finished_at TEXT, error TEXT);
CREATE INDEX runs_status ON runs(status);
CREATE TABLE steps (id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id), node TEXT NOT NULL,
  item TEXT, try_no INTEGER NOT NULL, status TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT);
CREATE INDEX steps_run ON steps(run_id, started_at);
CREATE TABLE llm_calls (id TEXT PRIMARY KEY, step_id TEXT NOT NULL REFERENCES steps(id), role TEXT, model TEXT,
  prompt_hash TEXT, request JSON, response_text TEXT, thinking_text TEXT, logprobs JSON, status TEXT NOT NULL,
  tokens_in INTEGER, tokens_out INTEGER, ms INTEGER, created_at TEXT NOT NULL);
CREATE INDEX llm_calls_step ON llm_calls(step_id);
-- LangGraph's SqliteSaver creates its own checkpoint tables in the same file.

-- misc
CREATE TABLE review_items (id TEXT PRIMARY KEY, kind TEXT NOT NULL, owner TEXT NOT NULL,
  test_id TEXT REFERENCES tests(id), attempt_id TEXT REFERENCES attempts(id), question_id TEXT,
  dedupe_key TEXT NOT NULL UNIQUE, proposal JSON NOT NULL, resolution JSON,
  followup_run_id TEXT REFERENCES runs(id), status TEXT NOT NULL,
  created_at TEXT NOT NULL, resolved_at TEXT);
CREATE INDEX review_open ON review_items(status, created_at);
CREATE INDEX review_attempt ON review_items(attempt_id);

CREATE TABLE files (id TEXT PRIMARY KEY, path TEXT NOT NULL, kind TEXT NOT NULL,
  derived_from TEXT REFERENCES files(id), mime TEXT, width INTEGER, height INTEGER, created_at TEXT NOT NULL,
  original_name TEXT);                 -- added by migration 0002
CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);

-- search: English display names for now; accent removal via remove_diacritics
-- (Vietnamese search words and the đ→d fold are deferred, PRD §2)
CREATE VIRTUAL TABLE tests_fts USING fts5(test_id UNINDEXED, display_name, meta_text,
  tokenize = 'unicode61 remove_diacritics 2');
-- queries use per-token prefix matching: "grade 8 final test 1" → grade* 8* final* test* 1*,
-- so "final" finds "FinalTerm"
```

---

## 4. Derived view: weak points

```sql
CREATE VIEW student_skill_stats AS
SELECT a.student_id, qt.tag AS skill_tag,
       SUM(ans.verdict IN ('correct','incorrect'))              AS seen,      -- "?" answers don't count
       SUM(ans.verdict = 'incorrect')                           AS wrong,
       SUM(ans.verdict = 'incorrect' AND e.error_type = 'gap')  AS gap_errors,
       MAX(a.created_at)                                        AS last_seen
FROM answers ans
JOIN attempts a       ON a.id = ans.attempt_id AND a.superseded_by IS NULL
JOIN question_tags qt ON qt.test_id = a.test_id AND qt.question_id = ans.question_id
LEFT JOIN explanations e ON e.test_id = a.test_id AND e.question_id = ans.question_id
                        AND e.wrong_answer_norm = ans.value_norm
WHERE a.student_id IS NOT NULL
GROUP BY a.student_id, qt.tag;
```
The Grade run combines this view (the history) with **the current attempt's verdicts, still in graph state**, before it saves (llm-design §5 `weak_points`). The ranking (recent attempts weigh more) is done in Python.

**v1.24 (step 22.5.5, D11, D11b–e): the trajectory.** `domain/weakpoints.py` lines up, per student and skill, the
student's current papers by `taken_on`, then `created_at`, then id. Per paper the **share right** over a **guessing
baseline** (v1.24.1, D11f): each counted question has a chance level (a `choice` with k options: 1/k, so 0.25 for A–D
and 0.5 for True/False; a `choice` without stored options: 0.25; any other form: 0), and the share is
max(0, right − Σ chance) / (counted − Σ chance), so all right = 100 % and chance level = 0 % (a paper where
counted − Σ chance is 0 is not counted for that skill); careless and spelling mistakes are left out; "?" answers are
not counted; each paper weighs the same. On a test's first grade the report uses the question levels `tag_skills`
just returned (graph state), the same ones `save` stores. Fewer than 3 papers → `not_enough_evidence`. Otherwise "recent" = the last 2 papers and the label is
the first that applies: `improved` (mean of the earlier shares < 0.5, both recent ≥ 0.5), `slipped` (earlier ≥ 0.5, both
recent < 0.5), `consistently_weak` (< 0.5 on at least 2/3 of the papers), `inconsistent` (mean share 35–65 %),
else `solid`. A skill's level on a paper is the lowest effective level of its questions there.

**The report's weak points:** each skill missed on this paper (wrong minus careless > 0), with its label when it has
one, else `this_paper_only`; `improved` and `solid` are not weak points. Counts are this paper's. Ordered by level
(A1 first; unknown last), vocabulary (`VOC-*`) first within a level, then the label, then the tag; when any weak point
is at level L, those above L are `held_back` ("Later, after the basics"). The summary call gets the skill names and
only the weak points not held back. `GET /students/{id}` lists every skill with its label, level and per-paper
results (date taken, share) for the Students tab.

---

## 5. Rules

### 5.1 Writing
- **One writer:** only the Python sidecar writes. The frontend goes through the sidecar API.
- **IDs:** prefixed and readable (`T-`, `S-`, `A-`) for things the teacher sees; ULIDs for internal rows.
- **Files are never modified.** Rotation is stored on `PageInput`/`AttemptPage`; derived images are new `files` rows (`kind=derived`, `derived_from`).
- **`write_test_meta(test_id, changes, by_teacher)`** is the only way to change metadata. It updates `meta`, the columns, `display_name`, `edited_fields` (if `by_teacher`) and the `tests_fts` row, all in one transaction. Extraction never overwrites fields listed in `edited_fields`.

### 5.2 Idempotent saves (both graphs)
- Extract `save`:
  0. **If `runs.status` is already `done`, return immediately.** This also covers blank picked runs, which write no rows.
  1. Look up `tests`/`attempts` by `source_run_id`. If found, reuse them and skip the inserts.
  2. Insert in one transaction: the test and its pages, the attempt with `attempt_pages` and one answer per graded question, and the key rows.
  3. Upsert Review items by `dedupe_key`.
  4. **v1.33 (step 22.6.4, D4):** queue the **key run**: a `queued` grade run on the same thread with
     `GradeInput(test_id, attempt_id=None, reason="after_extract")`, for every save (a new test, Extract again,
     a picked test, a blank test, typed or photo input). At most one per extract run: a retried save finds the
     `after_extract` run created after this extract run on the thread and writes none. The run manager loads it
     after the extract run is `done` and runs it next (FIFO). It never grades; keys that exist (a key photo's, the
     teacher's) stay, since the grade graph keys only the questions without a key row.
  5. Set `runs.status = 'done'`, **in the same transaction**.
- Grade `save`:
  - **v1.34 (step 22.6.6, step22.6-plan D15):** first check the test's `content` against the content loaded at the
    start; when it changed (a test-text save, a points save or Extract again while the run was queued behind
    another, running, stopped or interrupted), write nothing and go back to `load_context`, which loads the test,
    keys and answers again. The keys, skill tags and explanations the run made for questions whose text is
    unchanged are kept; those of deleted or changed questions are dropped, and no Review item is written for a
    question the test no longer has. **v1.35:** a stored key that outranks the run's own unsaved key (a
    teacher key written while the run was stopped; the guarded upsert's order) wins and is graded with; the run's
    pending Review items are kept only for the keys it keeps, the reloaded pass makes its own for the others;
    graded questions without skill tags after the reload (added or changed by the edit) are tagged, and only
    their tags are written. So an attempt's first grade ends against the saved test; a text save still
    queues runs only for graded attempts (§5.3);
  - check `attempts.version` against the version loaded at the start; on a mismatch, reload and recompute `grade`→`weak_points` (cheap, because keys and explanations are cached);
  - **guarded upserts**: never downgrade `teacher_*` keys; never touch `teacher_override`;
  - replace `grade_reports`;
  - mark this graph's older Review items for the attempt `obsolete`;
  - set the run to `done`, all in one transaction.

### 5.3 What a Review resolution triggers
**Follow-up rule:** grade runs are only queued for attempts that are **already graded and not superseded**. A Review action never starts the reasoning model on an attempt the teacher hasn't graded yet (PRD D16). The per-action database post-conditions are listed in plan.md Appendix E.

| Kind | Accept | Fix | Follow-up (graded attempts only) |
|---|---|---|---|
| `uncertain_answer` | Keep the value read; `teacher_override` = that value (now confident) | `teacher_override` = the typed value | `version += 1`; 1 grade run (`review_fix`) |
| `box_inline_conflict` | `teacher_override` = the box value | `teacher_override` = the typed value | Same as above |
| `uncertain_key` | Key unchanged, status → `teacher_verified` | Key replaced (`teacher_edit`, `teacher_verified`); that question's explanations deleted | 1 grade run per graded attempt on the test (`key_verified`); **v1.20:** deferred: the test goes to `regrade_pending` and the runs start with `POST /tests/{id}/regrade` |
| `key_unmapped` | Discard the unmapped key entry | Attach it to a chosen question (`teacher_edit`). **v1.29:** onto a True/False choice the first-start pass relabelled (options `T`/`F`, the stored ones in `old_options`), a letter that is an old label is mapped through the same relabel map (the letter whose text meant True → `T`, False → `F`); any other answer is stored as read | As `uncertain_key` (only for Fix) |
| `possible_duplicate` | Merge (§5.4) | – | 1 grade run per moved attempt (`merge`) |
| `merge_unaligned` | Leave the answer `ungraded` on the old question | Move it to a chosen question of the survivor | 1 grade run (`merge`) for that attempt, only for Fix |
| `picked_test_mismatch` | A new extract run without the pick, `supersedes_attempt_id` set | – | That extract run; the old attempt gets `superseded_by` |
| `unknown_student` | Create a student from `student_name_read` (invalid if none was read) | Pick an existing student or type a new one | `version += 1`; no run |
| `unknown_occasion` | Keep `Other:unknown` | `write_test_meta(by_teacher)` | None |
| `points_assumed` | Keep 0.25 per question | Edit the points → recompute `points_possible` | 1 grade run per graded attempt (`points_fix`), only for Fix. **v1.19:** no longer created; open items are closed (`obsolete`) at first start or by a text save; a leftover Fix saves equal points and queues no run. **v1.19.1:** every content save re-scores the test's graded attempts from their stored verdicts at once, with no model call |
| `validator_failed` | Keep the content as is | Edit the content (re-validated) | None, unless keys changed (then as `uncertain_key`) |
| `unreadable_text` | Close it with no change; the `???` spans stay (the paper may be gone) | Each listed field gets the typed text, through the content edit of `write_test_meta` (re-validated; an invalid edit is rejected and nothing changes). Text left as `???` stays | None (keys are not changed) |
| any | **Skip** → status `skipped`, nothing else changes | | |

**Where each kind is shown (v1.9, PRD D27).** The queue screen is gone; the same items and actions are reached in place. `unreadable_text`, `validator_failed`, `points_assumed`: marked on the test page (a `validator_failed` item for an answers page: in the Answers panel, v1.9.2). `uncertain_answer`, `box_inline_conflict`: at the question in the Answers panel. `uncertain_key`, `key_unmapped`: in the Key panel. `possible_duplicate`, `picked_test_mismatch`, `merge_unaligned`: on the extraction card. `unknown_student`, `unknown_occasion`: on their chips. Accept, Fix and Skip keep the meaning in the table above; editing the value in place is the Fix.

**A key photo settles unsure keys (v1.28).** When the extract `save` writes a key-photo key that replaces a question's
key (an AI key, or none because `ai_key_fast` failed), in the same run as an Extract again or on a later key-photo read,
that question's open `uncertain_key` items become `fixed` with resolution `{"action": "fix", "value": {"by":
"key_photo"}}`, as a test-text save settles items. The photo's key is kept; no run is queued by this close.

**A test-text save adds (v1.11).** A question that is new in the text gets an answer row in every attempt of the test (no value, `status` blank/unread as for an unanswered question), and a graded attempt gets the follow-up re-grade of an edited key. A `???` the teacher types creates or updates that page's `unreadable_text` item, like one from the run.

**A test-text save settles items (v1.9).** After a saved text edit: an `unreadable_text` item whose fields no longer contain `???` becomes `fixed`; if some `???` remain on that page it stays `open` with its spans updated; `validator_failed` items on the test become `fixed` when the saved content validates; a `points_assumed` item becomes `obsolete` (v1.35: the points are the equal ones; `points.save_content` re-scores the graded attempts at once, so no path queues a `points_fix` run). Items for dropped questions become `obsolete`.

An attempt becomes `reviewed` once it has no `open` items. When an open item is added to (or reopened on) a `reviewed` attempt, the attempt returns to `graded` if `score_earned` is set, otherwise to `extracted`.

### 5.4 Merge (duplicate → surviving test), one transaction
1. Take `question_alignment` from the Review item's proposal (computed by `compare_bank` from canonical numbers and stem similarity). Never use printed numbers to match.
2. Remap the moved attempts' `answers.question_id`. A collision or an unaligned question → a new **`merge_unaligned`** Review item, and that answer is kept on the old question as `ungraded`.
3. Update `attempts.test_id` and `threads.test_id`.
4. Copy the merged test's key rows and `question_tags` where the survivor has none, respecting precedence.
5. Set `tests.merged_into` and remove the merged test's `tests_fts` row. Merged tests are excluded from search and comparison, and are never deleted.
6. Queue the grade runs (§5.3).

### 5.5 Housekeeping
- **Migrations:** numbered SQL files applied at startup, recorded in `schema_migrations`. JSON columns are upgraded by pydantic upgrade functions keyed on `content_schema_version`, applied on read and written back.
- **Cleanup:**
  - finished runs have their LangGraph checkpoints purged;
  - a periodic sweep deletes `files` rows (and files on disk) that no test page, attempt page, picture or pending run references;
  - `llm_calls` older than the retention period (`settings.json` `log_retention_days`, **default 45**) are **deleted automatically** by the daily maintenance run, and can be cleared now from Settings, **except calls still referenced by `explanations.llm_call_id`**.
- **Backup:** `VACUUM INTO` + the `files/` folder, zipped into `data\backups\` (not encrypted in this version).
- **Folder layout (PRD §11, one app folder):**
  ```
  D:\ETACH\                     default (v1.31); chosen in the installer
    <program files>             Tauri exe, frozen sidecar folder, resources
    settings.json               log_retention_days (default 45), UI prefs (the data folder is always .\data)
    data\                       app.db (+ WAL), files\, models\ (OLLAMA_MODELS), models.toml, backups\
    webview\                    WebView2 user data folder
  ```
  Every path is resolved relative to the app folder, so copying the folder moves the whole app. **Nothing is written to AppData.** Development uses `etach serve --data <repo>\.devdata`.
- **Deferred tables:** `exposures` (items a student has already seen, for retest generation) and `school_aliases`.
- **Deleting a student:** see §5.7 (v1.14, decision D1).

### 5.6 Denormalized copies and the rule that keeps each in sync
| Copy | Owner / rule |
|---|---|
| `threads.test_id` | Equals the current attempt's `test_id`; set by extract `save` and updated by merge |
| `tests` columns + `display_name` + FTS row | Written only by `write_test_meta()` |
| `attempts.score_possible` | A snapshot of `tests.points_possible` at grading; every grade run recomputes it |
| `answers.printed_number` | Display only; never used for matching |
| `question_tags` | The **only** place skill tags live |
| `students.name_search` | Recomputed from `full_name` on every write, create or edit (v1.8) |
| A thread's shown title | `threads.title` once the teacher renames the thread. While it is the default "New thread", it is made on read from the current attempt's student name and the test's `display_name`, and is not stored (v1.8). A title the teacher types as exactly "New thread" is kept as typed (stored with an invisible U+2060 marker so it differs from the default; v1.9.2). "Use automatic name" stores the default again, so the title is made on read (v1.9.3) |

### 5.7 Deleting a thread or a test (v1.10, teacher's decisions B1, B2)

One transaction each, permanent (no recycle bin; the daily backup is the way back). Refused (409) while a run of the
thread, or a run on the test, is running or stopped-resumable; the teacher stops or finishes it first.
- **Thread:** the thread, its messages/cards, its attempts and everything that belongs to an attempt (attempt pages,
  answers, verdicts, explanations, grade reports, weak points, Review items of those attempts), and its runs'
  checkpoints. The test and its keys stay. The student stays (they may have other threads).
- **Test:** every thread whose attempts use the test (deleted as above; an attempt on this test inside a thread that
  also has attempts on other tests is deleted alone and the thread kept), then the test, its pages, keys, pictures,
  skill tags and Review items, and the tests merged into it (`merged_into` = this test).
- Files on disk are not deleted in the transaction: the existing sweep (§5.5) removes `files` rows and files no one
  references any more. A deleted thread's runs take their steps and `llm_calls` with them (the foreign keys chain
  `llm_calls` → `steps` → `runs` → `threads`); a kept explanation that pointed at one gets `llm_call_id` = NULL (v1.10.1).
- Pointers on kept rows are cleared, not followed (v1.10.1): another test's `parent_test_id`, a test-level Review item's
  `followup_run_id`, another attempt's `superseded_by`. A kept thread that had attempts on two tests gets its
  `test_id` set to the remaining test. Threads on a blank test (no attempt yet) go with that test.
- After the delete, `open_review_count` and the sidebar lists no longer include the removed rows.
- **Student (v1.14, decision D1):** every thread with an attempt of that student (deleted as a thread above), then the
  student. Same transaction and 409 rule. A thread whose attempts belong to several students loses only this student's
  attempts. Tests stay.

**Copying series details (v1.14, decision D3).** "Copy details from" and "same series as" copy exactly `occasion`, `term`,
`school`, `source` and `year` — only those that have a value in the source test (v1.14.1) — through `write_test_meta(by_teacher=True)`, so they go into `edited_fields` and an
extraction never overwrites them; `grade` and `test_number` are not copied. Extract again keeps the earlier run's
`series_from_test_id` (v1.14.1).

**Same series as a name (v1.21, decision D5).** The new-thread screen picks a series name from the `series` list
(`ExtractInput.series_name`). At save the new test's `source` is that name, and `grade`, `occasion`, `term` and `year`
come from the newest test of that series (by `created_at`, not merged, `source` equal ignoring case) — only those with
a value; the unknown occasion counts as none. All are teacher writes. `school` is not copied. "Copy details from" is
unchanged.

### 5.8 Extract again into the same test (v1.21, decision D8)
`POST /threads/{id}/extract-again` with `mode: "replace"` (the default when no other thread uses the test) reads the
thread's photos again and saves the reading into the thread's test, in the extract `save` transaction:
1. **Match** the new questions to the old ones: same printed number and same text first (markup, punctuation and
   numbering do not count; a question with no text of its own pairs by its number), then `similarity.align_questions`.
   A pair of the first kind is *exact*.
2. **Keys:** every key on an exact pair stays, with its explanations: a key the teacher typed or verified, and an AI
   (or key-photo) key with its unsure state (source, status, confidence; v1.21.1, D8 addition). The key rows and
   explanations of the other questions are deleted: changed and new questions are keyed again from the key photo (this
   run) or by the AI at grading. A kept AI key that this run's key photo replaces has its open `uncertain_key` items
   settled (§5.3 v1.28).
3. **Tags** move with every matched question; tags of removed questions are deleted.
4. **Student answers** of every attempt on the test (superseded ones too) move to the matched new question; an answer
   on a removed question is deleted; a current attempt gets an empty answer row for each new graded question. Changed
   attempts get `version += 1`.
5. **Review items** (open): on a removed question, or an `uncertain_key` whose key was deleted → `obsolete`; on a
   matched question → the new id (also in `dedupe_key`; closed instead if that key is taken). The old reading's
   test-level extract items are closed; the run writes its own.
6. **The test:** the same id; the content is saved with equal points (graded attempts re-scored from their verdicts),
   the new fingerprint, the read metadata as an AI write (fields in `edited_fields` stay), `test_pages` replaced. The
   thread's own attempt is superseded by the new one; the test goes to `regrade_pending` when another thread's attempt is
   graded. No grade run starts.

`mode: "copy"` makes a new test for this thread, as before. Either way `compare_bank` leaves the old test out, so no
`possible_duplicate` points at it. The teacher's text edits to the old content are not carried over (the reading
replaces it).
