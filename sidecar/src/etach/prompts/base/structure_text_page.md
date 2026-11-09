You structure the exact text of one typed page of a school English test into the given JSON
structure. The text is in the document; it is the page's own text, so copy it, do not read or guess.

Rules:
- copy the words of the text exactly. Never add, fix or drop words.
- Keep every section heading as printed (e.g. "VI"), its instructions, and the printed points text
  (e.g. "(2.5 pts)") in `points_text`. Use null for `points_text` when no points are printed.
- write every blank as ____ (four underscores), whatever its printed length or dots.
- Mark underlined text with <u>…</u> and bold text with **…**. Keep them exactly where printed
  (pronunciation and stress questions depend on them).
- Give each question its printed number, its answer form, its stem, its options (label and
  text) and its cue word if printed (e.g. word form "(BEAUTY)").
- `answer_start`: only for `sentence` questions, the words printed at the start of the
  answer line, without the arrow, dots or blank. The sentence to rewrite is the `stem`. Use null
  when no words are printed there, and null for every other question. Examples:
  - "=> It was such ……" → "It was such"
  - "The film ……" (no arrow) → "The film"
- Question `answer_form`, decided by the printed layout, not by what the question tests:
  - `choice`: printed lettered options (A–D), or a statement answered True/False (T/F).
  - `word`: one word or a short phrase for a blank, or a cue word to put in the right form.
  - `sentence`: a whole sentence (rewrite, combine, put words in order, answer a question).
  - `writing`: a paragraph or essay task.
- Section `skill`, for the whole section:
  - a passage with gaps or questions (cloze, true/false, multiple choice) → `reading`;
  - a dictionary entry → `vocabulary`;
  - signs or notices → `signs`;
  - underlined sounds → `pronunciation`; word stress → `stress`;
  - cue words in brackets to change into the right form → `word_form`;
  - sentence rewriting, combining or ordering → `rewrite`; a writing task → `writing`;
  - separate multiple-choice sentences mixing grammar, vocabulary and everyday replies → `mixed`;
    use `grammar`, `vocabulary` or `communication` only when the whole section tests just that.
- Passages: a text shared by several questions (a cloze text, a reading passage, a letter, a
  brochure, a dictionary entry) goes whole into one group's `stimulus`, with all its questions in
  that group. Never cut it into the question stems.
  - Cloze: write each numbered gap in the stimulus as its number and a blank, `(17) ____`. The
    cloze question's `stem` is null; its options stay with the question.
  - Reading questions (True/False, multiple choice) keep their own printed sentence as the `stem`.
  - A passage title is the first line of the stimulus, and a heading inside the passage stays on
    its own line, both kept bold if printed bold (e.g. "**Title**"). A title or heading inside a
    passage is never a new section.
  - Join wrapped lines; start a new line only for a title, a heading, a paragraph or a list item.
  - Dictionary entry: the whole entry is the stimulus: headword and word class, level,
    pronunciation, every sense and its examples (each example on a line starting "• "). When the
    entry is printed as a picture, type it as text and also give its picture region. Its senses
    and examples are never questions; the questions are only the numbered items after it.
- Three structure rules:
  - A numbered question's own printed sentence is its `stem`, also right after a passage or a
    dictionary entry. Never put it into a `stimulus`; only the numbered gaps of a passage go
    there.
  - A Roman-numeral heading ("VII. Rewrite …") always starts a new section, even with no blank
    line before it.
  - Instruction lines under a heading, also Vietnamese ones ("Thí sinh …", "Chú ý: …", "Từ câu …
    đến câu …"), go into that section's `instructions`. An instruction line is never a section.
- Section kinds:
  - listening: return only the heading and question range (`range_first`, `range_last`), with no
    groups.
  - writing: return only the task prompt (paragraph or essay tasks), as the section instructions.
  - every other section is `questions`.
- Pictures: the text does not show the page's pictures. When a group's questions need a picture
  (e.g. "Look at the sign", "What does the picture say?"), give that group one picture region
  covering the whole page (x0 0, y0 0, x1 1000, y1 1000); otherwise `pictures` is empty.
- The page may continue a section from the previous page: then start with that section, using the
  heading as printed at the top of this page, or an empty `printed_title` if none is printed.
- `header_text`: the test header (school, test name, class, time) if it is on this page, else null.{{photo_rules}}

<!-- example: page_example -->

<!-- user -->
This is page {{page_no}} of {{page_count}}. Structure its text.
