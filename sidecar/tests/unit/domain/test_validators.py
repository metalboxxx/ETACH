"""validators: R8.1.5 (one passing and one failing case each). Pure (no_io)."""

from __future__ import annotations

from typing import Any

import pytest
from support.guards import assert_pure, no_io  # noqa: F401

from etach.domain.models import OmittedSection, Option, Question, QuestionGroup
from etach.domain.validators import (
    failing_pages,
    validate_choice,
    validate_numbering,
    validate_word_blank,
)

pytestmark = pytest.mark.usefixtures("no_io")

LISTENING = [OmittedSection(title="I", questions=[1, 2, 3, 4], points=1.0)]


def question(n: int, page: int = 1, **kw: Any) -> Question:
    base: dict[str, Any] = {
        "id": f"q-{n:08x}",
        "number": n,
        "printed_number": n,
        "page_no": page,
        "answer_form": "sentence",
        "stem": "x",
        "options": None,
        "cue": None,
        "points": 0.25,
    }
    base.update(kw)
    return Question(**base)


def group(stimulus: str | None = None) -> QuestionGroup:
    return QuestionGroup(id="g-1", stimulus=stimulus, pictures=[], questions=[])


def opts(labels: str) -> list[Option]:
    return [Option(label=x, text=x.lower()) for x in labels]


def test_gap_fill_pass() -> None:
    assert validate_word_blank(question(1, answer_form="word", stem="I ____ tea."), group()) == []
    cloze = question(2, answer_form="word", stem=None)
    assert validate_word_blank(cloze, group("He (2) ____ home.")) == []


def test_gap_fill_fail() -> None:
    [f] = validate_word_blank(question(7, page=2, answer_form="word", stem="I __ tea."), group())
    assert (f.validator, f.page_no, f.printed_number) == ("gap_fill_blank", 2, 7)


def test_mcq_pass() -> None:
    assert validate_choice(question(1, answer_form="choice", options=opts("ABCD"))) == []
    assert validate_choice(question(1, answer_form="choice", options=opts("AB"))) == []


@pytest.mark.parametrize("labels", ["A", "ABCDE", "ABD", "BCDA", ""])
def test_mcq_fail(labels: str) -> None:
    [f] = validate_choice(question(3, page=4, answer_form="choice", options=opts(labels)))
    assert (f.validator, f.page_no) == ("mcq_options", 4)


def test_numbering_pass_with_listening_gap() -> None:
    assert validate_numbering([question(n) for n in range(5, 12)], LISTENING) == []


def test_numbering_fail() -> None:
    qs = [question(n, page=1) for n in range(5, 9)] + [question(n, page=2) for n in range(10, 12)]
    [f] = validate_numbering(qs, LISTENING)
    assert (f.validator, f.page_no, f.printed_number) == ("numbering", 2, 10)
    # without the listening entry, starting at 5 is itself a gap
    assert failing_pages(validate_numbering([question(n) for n in range(5, 8)], [])) == [1]
    # a repeated number fails
    assert len(validate_numbering([question(1), question(2), question(2, page=3)], [])) == 1


def test_failing_pages() -> None:
    fs = validate_choice(question(1, page=3, answer_form="choice", options=opts("A")))
    fs += validate_word_blank(question(2, page=1, answer_form="word", stem="x"), group())
    fs += validate_word_blank(question(3, page=3, answer_form="word", stem="y"), group())
    assert failing_pages(fs) == [1, 3]


def test_validators_is_pure() -> None:
    assert_pure("etach.domain.validators")


def test_r22_5_3_4_checks_by_form() -> None:
    """Step 22.5.3: the blank check is for a ``word`` question with no cue and no options (a
    former gap_fill), the option check for every ``choice``; a True/False choice has the two
    options the code adds."""
    assert validate_choice(question(1, answer_form="choice", options=opts("TF"))) == []
    [f] = validate_choice(question(1, answer_form="choice", options=None))
    assert f.validator == "mcq_options" and "choice question 1" in f.message
    assert validate_choice(question(1, answer_form="choice", options=opts("FT"))) != []
    [w] = validate_word_blank(question(4, answer_form="word", stem="beauty"), group())
    assert w.validator == "gap_fill_blank" and "word question 4" in w.message
    for form in ("sentence", "writing"):
        assert validate_word_blank(question(5, answer_form=form, stem="no blank"), group()) == []
        assert validate_choice(question(5, answer_form=form, options=None)) == []


def test_word_blank_only_without_cue_or_options() -> None:
    """Fix of step 22.5.3: the blank check flags what it flagged before the forms. A ``word``
    question with a cue (a former word_form / verb_form) or with printed options (as the
    recorded S1 page 1 gives) has no blank to check; one with neither (a former gap_fill) needs
    ``____``."""
    cued = question(1, answer_form="word", stem="She is very ____ .", cue="BEAUTY")
    assert validate_word_blank(cued, group()) == []
    assert (
        validate_word_blank(question(2, answer_form="word", stem="x", cue="DESTROY"), group()) == []
    )
    no_blank = question(3, answer_form="word", stem="William: Happy Birthday, David!")
    assert validate_word_blank(no_blank.model_copy(update={"options": opts("ABCD")}), group()) == []
    [f] = validate_word_blank(no_blank, group())
    assert (f.validator, f.printed_number) == ("gap_fill_blank", 3)
    # with no stem, the blank is looked for in the stimulus (a cloze gap)
    [g] = validate_word_blank(question(4, answer_form="word", stem=None), group("A text."))
    assert g.validator == "gap_fill_blank"


def test_choice_check_as_mcq_and_true_false() -> None:
    """The option check on a ``choice`` flags what the mcq check flagged (2-4 options A, B, C,
    D in order), and passes a True/False choice with the T/F pair the code adds; a choice with
    no options (neither lettered nor True/False) is flagged."""
    for labels in ("AB", "ABC", "ABCD", "TF"):
        assert validate_choice(question(1, answer_form="choice", options=opts(labels))) == []
    for bad in ("A", "ABCDE", "TFX", ""):
        assert validate_choice(question(1, answer_form="choice", options=opts(bad))) != []
    assert validate_choice(question(1, answer_form="choice", options=None)) != []
