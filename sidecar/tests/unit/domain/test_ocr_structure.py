"""Step 22.6.5 (2b): plain OCR text of one page → ``TranscribeOut`` by code (R22.6.5.2).
Made-up papers only."""

from __future__ import annotations

from etach.domain.ocr_structure import structure_ocr_page

PAPER = """\
I. Choose the word whose underlined part is pronounced differently. (0.5 pt)
Thí sinh chỉ ghi mẫu tự A, B, C hoặc D.
1. A. lamp B. gate C. cake D. late
2. A have to B. had C. has D. having
II. Read the passage and choose the best answer. (1.5 pts)
**The Goat Farm**
Brindo keeps goats on a hill. Every (3) ____ he
milks them before school.
3. A. morning B. night C. noon D. week
Question 4. Why does Brindo keep goats?
A. To sell milk
B. To play
C. To ride D. To paint
III. Use the correct form of the word given. (1 pt)
5. The goats are very ..... today. (HAPPINESS)
IV. Rewrite the sentences.
6. Brindo began to keep goats in 2019. (SINCE)
=> Brindo has ……
7. Nobody has fed the goats today.
The goats .....
"""


def _all(text: str):  # type: ignore[no-untyped-def]
    r = structure_ocr_page(text)
    qs = {q.printed_number: q for s in r.out.sections for g in s.groups for q in g.questions}
    return r, qs


def test_r22_6_5_2_roman_headings_start_sections_with_instructions_and_points() -> None:
    r, _ = _all(PAPER)
    titles = [s.printed_title for s in r.out.sections]
    assert titles == ["I", "II", "III", "IV"]
    first = r.out.sections[0]
    assert first.points_text == "(0.5 pt)"
    assert first.instructions.splitlines() == [
        "Choose the word whose underlined part is pronounced differently.",
        "Thí sinh chỉ ghi mẫu tự A, B, C hoặc D.",
    ]
    assert first.skill == "pronunciation"
    assert r.unplaced == []


def test_r22_6_5_2_options_on_one_line_several_lines_and_without_the_first_dot() -> None:
    _, qs = _all(PAPER)
    assert [o.text for o in qs[1].options or []] == ["lamp", "gate", "cake", "late"]
    assert [o.label for o in qs[2].options or []] == ["A", "B", "C", "D"]
    assert (qs[2].options or [])[0].text == "have to"
    assert [o.text for o in qs[4].options or []] == [
        "To sell milk",
        "To play",
        "To ride",
        "To paint",
    ]
    assert qs[1].stem is None and qs[1].answer_form == "choice"


def test_r22_6_5_2_passage_and_cloze_gap_in_the_stimulus() -> None:
    r, qs = _all(PAPER)
    group = r.out.sections[1].groups[0]
    assert group.stimulus == (
        "**The Goat Farm**\n"
        "Brindo keeps goats on a hill. Every (3) ____ he milks them before school."
    )
    assert r.out.sections[1].skill == "reading"
    assert qs[3].stem is None
    assert qs[4].stem == "Why does Brindo keep goats?"  # "Question N." starts a question


def test_r22_6_5_2_word_form_cue_and_blank() -> None:
    r, qs = _all(PAPER)
    assert qs[5].answer_form == "word"
    assert qs[5].cue == "HAPPINESS"
    assert qs[5].stem == "The goats are very ____ today."
    assert r.out.sections[2].skill == "word_form"


def test_r22_6_5_2_rewrite_answer_start_with_and_without_arrow() -> None:
    r, qs = _all(PAPER)
    assert (qs[6].answer_form, qs[6].stem, qs[6].cue, qs[6].answer_start) == (
        "sentence",
        "Brindo began to keep goats in 2019.",
        "SINCE",
        "Brindo has",
    )
    assert qs[7].answer_start == "The goats"
    assert r.out.sections[3].skill == "rewrite"


def test_r22_6_5_2_true_false_statements_are_choice_without_options() -> None:
    text = (
        "III. Read the passage. Decide if the statements are True or False.\n"
        "Nan has a lamp.\n17. Nan has a lamp.\n18. Nan has no lamp."
    )
    _, qs = _all(text)
    assert qs[17].answer_form == "choice" and qs[17].options is None
    lone = "17 Nan has a lamp. ____"
    _, qs = _all(f"16. A. a B. b C. c D. d\n{lone}")  # no dot: the next number
    assert qs[17].answer_form == "choice" and qs[17].stem == "Nan has a lamp. ____"


def test_r22_6_5_2_page_continuing_a_section_starts_untitled() -> None:
    r, _ = _all("23. A. at B. in C. on D. for\nV. Use the correct form of the word.")
    assert r.out.sections[0].printed_title == ""
    assert r.out.sections[1].printed_title == "V"


def test_r22_6_5_2_heading_read_as_a_digit() -> None:
    text = "1. Choose the correct answer:\nChoose the word.\n1. A. a B. b C. c D. d"
    r, qs = _all(text)
    assert [s.printed_title for s in r.out.sections] == ["1"]
    assert r.out.sections[0].instructions == "Choose the correct answer:\nChoose the word."
    assert list(qs) == [1]


def test_r22_6_5_2_sub_instruction_stays_new_form_starts_a_section() -> None:
    text = (
        "I. Choose the best answer.\n1. A. a B. b C. c D. d\nChoose the correct answer:\n"
        "2. A. a B. b C. c D. d\n3. Nan is ____. (HAPPY)\n"
        "Rewrite each of the following sentences.\n4. Nan is tall.\n=> Nan has ...."
    )
    r, qs = _all(text)
    assert [s.printed_title for s in r.out.sections] == ["I", ""]
    assert "Choose the correct answer:" in r.out.sections[0].instructions
    assert r.out.sections[1].skill == "rewrite" and qs[4].answer_start == "Nan has"


def test_r22_6_5_2_number_without_dot_out_of_order_is_text() -> None:
    text = "VI. Look at the dictionary entry.\nglimber (verb)\n1 to rub a lamp\n33. Todd ____ it."
    r, qs = _all(text)
    assert list(qs) == [33]
    assert r.out.sections[0].groups[0].stimulus == "glimber (verb)\n1 to rub a lamp"
    assert r.out.sections[0].skill == "vocabulary"


def test_r22_6_5_2_unplaced_lines_are_kept_and_listed() -> None:
    text = "II. Look at the signs.\n15. What does it say?\nA. a B. b C. c D. d\nNo dogs here."
    r, qs = _all(text)
    assert "No dogs here." in (qs[15].stem or "")
    assert r.unplaced == ["No dogs here."]
    assert r.out.sections[0].skill == "signs"
    assert r.out.sections[0].groups[0].pictures  # the page's picture for a sign


def test_r22_6_5_2_options_out_of_order_are_kept_and_flagged() -> None:
    r, qs = _all("28. A. so B. and D. but D. that")
    assert [o.label for o in qs[28].options or []] == ["A", "B"]
    assert "but" in (qs[28].options or [])[1].text
    assert r.unplaced == ["28. A. so B. and D. but D. that"]


def test_r22_6_5_2_options_before_any_question_are_kept_and_flagged() -> None:
    r, _ = _all("A. To x B. To y\n22. How? A. a B. b C. c D. d")
    assert r.unplaced == ["A. To x B. To y"]
    assert "A. To x" in (r.out.sections[0].groups[0].stimulus or "")


def test_r22_6_5_2_header_text() -> None:
    r, _ = _all("TRƯỜNG THCS NAN\nKIỂM TRA CUỐI KÌ\nI. Choose.\n1. A. a B. b C. c D. d")
    assert r.out.header_text == "TRƯỜNG THCS NAN\nKIỂM TRA CUỐI KÌ"


def _numbers(text: str) -> list[list[int]]:
    r = structure_ocr_page(text)
    return [[q.printed_number for g in s.groups for q in g.questions] for s in r.out.sections]


RUN = "1. A. a B. b C. c D. d\n2. A. a B. b C. c D. d"
STRAY = """\
8. PRACTICE 3 MT2 (K)
Choose the word (A, B, C or D) that best fits the sentence. (3.5 pts)

1. Which word is different?
A. lamp B. gate C. cake D. late
2. Nan ____ a lamp.
A. has
B. have
C. having D. had
3. A. a B. b C. c D. d
4. A. a B. b C. c D. d
5. A. a B. b C. c D. d
6. A. a B. b C. c D. d
7. A. a B. b C. c D. d
8. A. a B. b C. c D. d
9. A. a B. b C. c D. d
II. Read the passage.
10. A. a B. b C. c D. d
"""


def test_r2_1_a_run_from_1_beats_a_stray_first_number() -> None:
    r, qs = _all(STRAY)
    assert _numbers(STRAY) == [[1, 2, 3, 4, 5, 6, 7, 8, 9], [10]]
    assert qs[1].stem == "Which word is different?"
    assert [o.text for o in qs[8].options or []] == ["a", "b", "c", "d"]  # the real 8
    first = r.out.sections[0]
    assert first.printed_title == ""
    assert first.points_text == "(3.5 pts)"
    assert first.instructions.splitlines()[0] == "8. PRACTICE 3 MT2 (K)"  # kept, and flagged
    assert r.unplaced == ["8. PRACTICE 3 MT2 (K)"]


def test_r2_1_the_stray_line_stays_in_its_section_also_across_a_heading() -> None:
    r, _ = _all(f"I. Choose.\n8. PRACTICE\n{RUN}")
    assert [s.printed_title for s in r.out.sections] == ["I"]
    assert r.out.sections[0].instructions.splitlines() == ["Choose.", "8. PRACTICE"]
    assert r.unplaced == ["8. PRACTICE"]
    r, _ = _all(f"8. PRACTICE\nII. Choose.\n{RUN}")
    assert _numbers(f"8. PRACTICE\nII. Choose.\n{RUN}") == [[], [1, 2]]
    assert r.out.sections[0].instructions == "8. PRACTICE"
    assert r.unplaced == ["8. PRACTICE"]


def test_r2_2_a_section_restarting_at_1_after_real_questions_stays_text() -> None:
    text = f"33. A. a B. b C. c D. d\n34. A. a B. b C. c D. d\nVII. Choose.\n{RUN}"
    assert _numbers(text)[0] == [33, 34]
    assert _numbers(text)[-1] == []


def test_r2_2_a_lone_first_number_followed_by_higher_numbers_is_unchanged() -> None:
    r, qs = _all("8. Nan is tall.\n9. A. a B. b C. c D. d\n10. A. a B. b C. c D. d")
    assert list(qs) == [8, 9, 10]
    assert qs[8].stem == "Nan is tall."
    assert r.unplaced == []


def test_r2_2_a_real_question_with_options_keeps_a_following_1_as_text() -> None:
    r, qs = _all(f"8. Nan ____ a lamp.\nA. has B. had C. have D. having\n{RUN}")
    assert list(qs) == [8]
    assert r.unplaced == RUN.splitlines()


def test_r2_2_a_1_alone_or_without_a_full_run_stays_text() -> None:
    _, qs = _all("8. Nan is tall.\n1. Something else.")
    assert list(qs) == [8] and qs[8].stem == "Nan is tall. 1. Something else."
    _, qs = _all("8. REVISION\n1 to rub a lamp\n2 to shine")  # no dot
    assert list(qs) == [8]
    _, qs = _all("8. REVISION\n1. A. a B. b C. c D. d\n2. Nan is tall.")  # 2 has no options
    assert list(qs) == [8]
    _, qs = _all("8. REVISION\n1. A. a B. b\n2. A. a B. b")  # not A to D
    assert list(qs) == [8]
    _, qs = _all("8. REVISION\n1. Choose the answer:\n1. A. a B. b C. c D. d")
    assert list(qs) == [8]


def test_r2_2_a_lone_number_that_reads_as_a_question_stays() -> None:
    text = "34. Nan is tall.\n=> Nan has ....\nVII. Rewrite the sentences.\n"
    assert _numbers(f"{text}1. Nan is short.\n2. Nan is old.") == [[34], []]
    assert _numbers(f"{text}{RUN}") == [[34], []]  # an answer start, even before a real run
    blank_cue = "30. She is very ____. (beauty)\nVII. Choose.\n"
    assert _numbers(f"{blank_cue}1. Nan is short.\n2. Nan is old.") == [[30], []]
    assert _numbers(f"{blank_cue}{RUN}") == [[30], []]
    assert _numbers(f"6. He began in 2019. (SINCE)\nVII. Choose.\n{RUN}") == [[6], []]  # cue only


def test_r2_2_a_lone_line_ending_in_a_question_mark_stays() -> None:
    for line in (
        "20. Why does Nan keep goats?",
        "20. Why does Nan keep goats?  ",
        '20. Nan said, "Why goats?"',
        "20. Nan said, “Why goats?”",
    ):
        r, _ = _all(f"{line}\nII. Choose.\n{RUN}")
        assert _numbers(f"{line}\nII. Choose.\n{RUN}") == [[20], []]
        assert r.out.sections[-1].groups[0].stimulus == RUN  # the run stays text, as before
        assert r.unplaced == []
    assert _numbers(f"20. Why does Nan\nkeep goats?\n{RUN}") == [[20]]  # a wrapped question
    assert _numbers(f"8. WHY? PRACTICE\n{RUN}") == [[1, 2]]  # not at the end: still stray


def test_r2_2_numbered_lines_in_a_dictionary_entry_or_passage_stay_text() -> None:
    _, qs = _all("33. Todd ____ it.\nglimber (v)\n1. to rub\n2. to shine")
    assert list(qs) == [33]
    _, qs = _all("VI. Choose the meaning.\n33. Which one?\nglimber\n1. to rub\n2. to shine")
    assert list(qs) == [33]
    assert qs[33].stem == "Which one? glimber 1. to rub 2. to shine"
    _, qs = _all("20. Why does Nan keep goats?\n1. They are small.\n2. They are cheap.")
    assert list(qs) == [20]
    _, qs = _all("VIII. Write a paragraph.\n40. Write about your school.\n1. Name\n2. Place")
    assert list(qs) == [40]


def test_r2_2_no_text_is_lost_when_the_number_stays() -> None:
    text = f"8. REVISION\n=> Unless\nextra line here\n{RUN}"
    r, qs = _all(text)
    assert list(qs) == [8]
    kept = " ".join([qs[8].stem or "", *r.unplaced])
    assert all(word in kept for word in ("REVISION", "Unless", "extra line here", "1.", "2."))
