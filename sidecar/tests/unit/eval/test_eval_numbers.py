"""R22.5.7.3: answer-number errors, split into renumbering and reading errors."""

from pathlib import Path

from etach.eval.harness import (
    COLUMNS,
    GRADE_COLUMNS,
    NUMBER_COLUMNS,
    FixtureResult,
    aggregate_row,
    pad_history,
)
from etach.eval.metrics import (
    SimpleQuestion,
    SimpleSection,
    canonical_numbers,
    number_counts,
)


def _q(printed: int, stem: str, number: int | None = None) -> SimpleQuestion:
    return SimpleQuestion(printed_number=printed, answer_form="word", stem=stem, number=number)


STEMS = [
    "She ____ to school every day.",
    "They have lived here ____ 2010.",
    "If I were you, I ____ go.",
    "The book ____ by my uncle.",
]


def _expected() -> list[SimpleSection]:
    return [
        SimpleSection.flat("I", [_q(5, STEMS[0]), _q(6, STEMS[1])]),
        SimpleSection.flat("II", [_q(7, STEMS[2]), _q(8, STEMS[3])]),
    ]


def test_canonical_numbers_follow_renumber() -> None:
    writing = SimpleSection.flat("W", [_q(9, "Write a letter.")])
    writing.graded = False
    sections = [writing, *_expected()]
    assert canonical_numbers(sections) == [5, 1, 2, 3, 4]


def test_one_renumbering_and_one_reading_error_r22_5_7_3() -> None:
    # the model misread printed 7 as 1 (reading error), and the code numbered the questions so
    # that the last one sits on canonical 5 instead of 4 (renumbering error)
    actual = [
        SimpleSection.flat("I", [_q(5, STEMS[0], 1), _q(6, STEMS[1], 2)]),
        SimpleSection.flat("II", [_q(1, "If I were you, I ____ go!", 3), _q(8, STEMS[3], 5)]),
    ]
    n = number_counts(_expected(), actual)
    assert (n.reading.hits, n.reading.total) == (1, 4)
    assert (n.renumbering.hits, n.renumbering.total) == (1, 4)


def test_a_missed_question_shifts_the_numbers_after_it() -> None:
    actual = [  # question 6 not read: the next ones keep their printed numbers, numbers shift
        SimpleSection.flat("I", [_q(5, STEMS[0], 1)]),
        SimpleSection.flat("II", [_q(7, STEMS[2], 2), _q(8, STEMS[3], 3)]),
    ]
    n = number_counts(_expected(), actual)
    assert (n.reading.hits, n.reading.total) == (0, 3)
    assert (n.renumbering.hits, n.renumbering.total) == (2, 3)


def test_no_errors_and_unaligned_text() -> None:
    same = [
        SimpleSection.flat("I", [_q(5, STEMS[0], 1), _q(6, STEMS[1], 2)]),
        SimpleSection.flat("II", [_q(7, STEMS[2], 3), _q(8, "Something else entirely.", 4)]),
    ]
    n = number_counts(_expected(), same)
    assert (n.reading.hits, n.reading.total) == (0, 3)  # the unlike text is not aligned
    assert (n.renumbering.hits, n.renumbering.total) == (0, 3)


def test_the_history_row_has_both_columns_appended() -> None:
    assert NUMBER_COLUMNS == ("number_renumbering_errors", "number_reading_errors")
    assert COLUMNS[-len(NUMBER_COLUMNS) :] == NUMBER_COLUMNS
    assert COLUMNS.index(GRADE_COLUMNS[-1]) + 1 == COLUMNS.index(NUMBER_COLUMNS[0])
    r = FixtureResult(status="done")
    actual = [
        SimpleSection.flat("I", [_q(5, STEMS[0], 1), _q(6, STEMS[1], 2)]),
        SimpleSection.flat("II", [_q(1, STEMS[2], 3), _q(8, STEMS[3], 5)]),
    ]
    r.numbers = number_counts(_expected(), actual)
    row = aggregate_row([r], graph="extract", set_name="t", mode="replay", models={}, commit="c")
    assert row["number_renumbering_errors"] == "0.2500"
    assert row["number_reading_errors"] == "0.2500"
    empty = aggregate_row([], graph="extract", set_name="t", mode="x", models={}, commit="c")
    assert empty["number_reading_errors"] == ""


def test_pad_history_from_the_header_before_the_number_columns(tmp_path: Path) -> None:
    old = COLUMNS[: -len(NUMBER_COLUMNS)]
    path = tmp_path / "h.csv"
    row = ",".join(f"v{j}" for j in range(len(old)))
    path.write_text(",".join(old) + "\n" + row + "\n", encoding="utf-8")
    assert pad_history(path) == 1
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines == [",".join(COLUMNS), row + "," * len(NUMBER_COLUMNS)]
