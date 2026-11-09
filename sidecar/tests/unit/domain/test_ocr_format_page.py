"""Step 22.6.5 (2a): a photo page that GLM-OCR wrote in the test-text format, read by
``test_text.read_ocr_page`` (R22.6.5.4). Made-up texts only."""

from __future__ import annotations

from etach.domain.test_text import read, read_ocr_page

PAGE = """ĐỀ KIỂM TRA GIỮA KỲ - LỚP 8
# I. Choose the best answer.
1. She ____ to school every day.
A. go  B. goes  C. going  D. gone
2. I am interested ____ music. A. in B. on C. at D. of
# II. Give the correct form of the word.
3. He is a very ____ driver.
Cue: (care)
# III. Rewrite the sentences.
4. It is a pity I can't swim.
Start: I wish
5. He is too young to drive.
=> He is not old ......
"""


def test_r22_6_5_4_format_page_becomes_sections_and_questions() -> None:
    got = read_ocr_page(PAGE)
    assert got.problem is None
    out = got.out
    assert out.header_text == "ĐỀ KIỂM TRA GIỮA KỲ - LỚP 8"
    assert [s.printed_title for s in out.sections] == ["I", "II", "III"]
    assert out.sections[0].instructions == "Choose the best answer."
    q1, q2 = out.sections[0].groups[0].questions
    assert (q1.printed_number, q1.answer_form, q1.stem) == (
        1,
        "choice",
        "She ____ to school every day.",
    )
    assert [(o.label, o.text) for o in q1.options or []] == [
        ("A", "go"),
        ("B", "goes"),
        ("C", "going"),
        ("D", "gone"),
    ]
    # options on the question's line, one space apart (GLM-OCR's habit), are split too
    assert q2.stem == "I am interested ____ music."
    assert [o.text for o in q2.options or []] == ["in", "on", "at", "of"]
    (q3,) = out.sections[1].groups[0].questions
    assert (q3.answer_form, q3.cue, q3.options) == ("word", "(care)", None)
    q4, q5 = out.sections[2].groups[0].questions
    assert (q4.answer_form, q4.answer_start) == ("sentence", "I wish")
    assert (q5.answer_form, q5.answer_start) == ("sentence", "He is not old")


def test_r22_6_5_4_passage_is_the_group_stimulus() -> None:
    text = (
        "# IV. Read the passage and answer the questions.\n"
        "[Passage]\nTom lives in Hue.\nHe likes fishing.\n[End of passage]\n"
        "6. Where does Tom live?\n7. What does he like?\n"
    )
    got = read_ocr_page(text)
    assert got.problem is None
    (group,) = got.out.sections[0].groups
    assert group.stimulus == "Tom lives in Hue.\nHe likes fishing."
    assert [q.printed_number for q in group.questions] == [6, 7]


def test_r22_6_5_4_continuation_page_starts_untitled() -> None:
    """A page that goes on from the previous one (questions before any heading) starts with an
    untitled section, which the merge joins to the previous page's last section (as in 2b)."""
    text = "8. They have lived here ____ 2010.\nA. for  B. since  C. in  D. at\n# V. Write.\n"
    got = read_ocr_page(text)
    assert got.problem is None
    first, second = got.out.sections
    assert first.printed_title == "" and first.kind == "questions"
    assert [q.printed_number for q in first.groups[0].questions] == [8]
    assert (second.printed_title, second.kind) == ("V", "writing")


def test_r22_6_5_4_continuation_options_before_any_question_are_kept_and_flagged() -> None:
    text = "C. going  D. gone\n9. I ____ my homework yesterday.\nA. do  B. did\n"
    got = read_ocr_page(text)
    assert got.problem is not None and "option line" in got.problem
    (section,) = got.out.sections
    assert section.printed_title == ""
    (group,) = section.groups
    assert group.stimulus == "C. going  D. gone"  # kept, not dropped
    assert [q.printed_number for q in group.questions] == [9]


def test_r22_6_5_4_unreadable_page_keeps_its_text() -> None:
    text = "# I. Read.\n1. A question\nA. a  B. b\n[End of passage]\n"
    got = read_ocr_page(text)
    assert got.problem is not None
    assert "[End of passage] has no [Passage] above it" in got.problem
    (section,) = got.out.sections
    (group,) = section.groups
    assert group.stimulus == text.strip() and group.questions == []


def test_r22_6_5_4_plain_text_with_no_structure_is_kept() -> None:
    got = read_ocr_page("Some text GLM-OCR wrote without the format.\nMore text.\n")
    assert got.problem is not None
    assert "Some text GLM-OCR wrote" in (got.out.sections[0].groups[0].stimulus or "")


def test_r22_6_5_4_listening_section_has_its_range_only() -> None:
    text = "# I. Listen and choose the right answer.\n1. A. red  B. blue\n2. A. one  B. two\n"
    (section,) = read_ocr_page(text).out.sections
    assert (section.kind, section.range_first, section.range_last) == ("listening", 1, 2)
    assert section.groups == []


def test_r22_6_5_4_read_accepts_what_it_did_before() -> None:
    """``read`` itself is unchanged: a page with no heading is still an error there."""
    assert read("1. A question\n").content is None
    assert read("# I. Choose.\n1. A question\n   A. a  B. b\n").content is not None
