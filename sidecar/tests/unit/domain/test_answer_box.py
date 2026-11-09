"""Step 22.6.1 (a): answer boxes out of a photo page's OCR text (R22.6.1.1). Made-up texts only."""

from __future__ import annotations

import pytest

from etach.domain.answer_box import strip_answer_boxes


@pytest.mark.parametrize(
    "heading",
    [
        "Phần trả lời:",
        "Phan tra loi:",
        "PHẦN TRẢ LỜI",
        "Phàn trả lối: Thí sinh chỉ ghi mẫu tự A, B, C, hoặc D vào ô trả lời",
        "Phàn trà lòi:",
    ],
)
def test_r22_6_1_1_heading_and_its_blank_rows_go(heading: str) -> None:
    question = "4. A. apply B. degree C. award D. pension"
    text = f"{question}\n{heading}\n1. ____ 2. ____\n3. ____ 4. ____\nII. Look"
    assert strip_answer_boxes(text) == f"{question}\nII. Look"


def test_r22_6_1_1_blanks_on_the_heading_line_go() -> None:
    text = "22. How?\nPhàn trả lối: 17. ____ 18. ____ 19. ____\nIV. Choose"
    assert strip_answer_boxes(text) == "22. How?\nIV. Choose"


def test_r22_6_1_1_dots_and_empty_lines_inside_the_box() -> None:
    question, after = "36. Linh decided to ..... and record.", "Rewrite each sentence."
    text = f"{question}\n\nPhàn trà lòi:\n\n35. ...\n\n36. …\n\n{after}"
    assert strip_answer_boxes(text) == f"{question}\n\n\n{after}"


def test_r22_6_1_1_the_first_other_line_ends_the_box() -> None:
    text = "Phần trả lời:\n15. ____ 16. ____\n17. The girl ____ a book.\n18. ____"
    assert strip_answer_boxes(text) == "17. The girl ____ a book.\n18. ____"


def test_r22_6_1_1_single_blanks_without_a_heading_stay() -> None:
    text = "V. Fill in.\n29. ____\n30. ____"
    assert strip_answer_boxes(text) == text


def test_r22_6_1_1_a_row_of_blanks_without_a_heading_goes() -> None:
    row1 = "1. ____ 2. ____ 3. ____ 4. ____ 5. ____ 6. ____ 7. ____"
    row2 = "8. ____ 9. ____ 10. ____ 11. ____ 12. ____ 13. ____ 14. ____"
    text = f"D. Why do you enjoy science?\n\n{row1}\n\n{row2}\n\nII. Look at the sign."
    assert strip_answer_boxes(text) == "D. Why do you enjoy science?\n\n\nII. Look at the sign."


@pytest.mark.parametrize(
    ("box", "rows"),
    [
        ("ANSWER 17. ____ 18. ____ 19. ____", ""),
        ("ANSWER", "\n29. 30. 31.\n32. 33. 34."),
        ("ANSWERS:", "\n1. ____"),
        ("Answer: 5. ____ 6. ____", ""),
    ],
)
def test_r22_6_1_1_an_english_answer_heading(box: str, rows: str) -> None:
    question, after = "34. My sister is preparing a speech. (graduate)", "IV. Choose the word."
    text = f"{question}\n{box}{rows}\n{after}"
    assert strip_answer_boxes(text) == f"{question}\n{after}"


@pytest.mark.parametrize(
    "line", ["Answer: 1. He goes to school", "ANSWERS 5 points", "ANSWER: 3. ____ (2 points)"]
)
def test_r22_6_6_4_an_english_heading_with_words_after_it_stays(line: str) -> None:
    text = f"IV. Write.\n{line}\n35. Why?"
    assert strip_answer_boxes(text) is text


def test_r22_6_1_1_answer_instructions_stay() -> None:
    text = "VI. Answer the questions.\nAnswer these questions about the text:\n35. Why?"
    assert strip_answer_boxes(text) is text


def test_r22_6_1_1_text_without_a_box_comes_back_unchanged() -> None:
    text = "I. PRONUNCIATION\r\n1. A. cat B. hat C. map D. late\n\nTrả lời các câu hỏi sau."
    assert strip_answer_boxes(text) is text
