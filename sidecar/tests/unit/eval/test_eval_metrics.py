"""R11.1: the eval metrics."""

import math

import pytest

from etach.eval.metrics import (
    ReadAnswer,
    ReadKey,
    SimpleGroup,
    SimpleQuestion,
    SimpleSection,
    answer_counts,
    calibration_counts,
    cer,
    key_counts,
    levenshtein,
    question_keys,
    structure_counts,
    wilson_interval,
)


def test_cer_r11_1() -> None:
    assert cer("abc", "abd") == pytest.approx(1 / 3)
    assert cer("abc", "abc") == 0.0
    assert cer("", "") == 0.0
    assert cer("", "x") == 1.0
    assert levenshtein("kitten", "sitting") == 3
    assert levenshtein("Tiếng", "Tieng") == 1


def test_question_keys_number_repeats() -> None:
    assert question_keys([1, 2, 1, 3, 1]) == ["1", "2", "1#2", "3", "1#3"]


def _q(n: int, **kw: object) -> SimpleQuestion:
    base: dict[str, object] = {
        "answer_form": "choice",
        "stem": f"Question {n} ____ here",
        "options": ["go", "went", "gone", "going"],
    }
    base.update(kw)
    return SimpleQuestion(printed_number=n, **base)  # type: ignore[arg-type]


def test_structure_identical_pair() -> None:
    sections = [SimpleSection.flat("I", [_q(1), _q(2)]), SimpleSection.flat("II", [_q(1)])]
    s = structure_counts(sections, sections)
    assert s.overall == 1.0
    assert s.text.value == 0.0
    assert s.underline.value is None  # no underline on either side


def test_structure_synthetic_pair() -> None:
    expected = [
        SimpleSection.flat(
            "I",
            [
                _q(1, stem="Choose the <u>underlined</u> part"),
                _q(2, stem="He is **very** tall ____"),
                _q(3, answer_form="word", options=None),
            ],
        ),
        SimpleSection.flat("II", [_q(4, answer_form="sentence", options=None, stem="Rewrite")]),
    ]
    actual = [
        SimpleSection.flat(
            "I",
            [
                _q(1, stem="Choose the underlined part"),  # underline lost
                _q(2, stem="He is **very** tall ____", answer_form="word"),  # wrong form
                _q(3, answer_form="word", options=["a", "b"]),  # options invented; no blank
            ],
        ),
        # question 4 missing; one section fewer
    ]
    s = structure_counts(expected, actual)
    # partial credit: min / max of the counts
    assert (s.section_count.hits, s.section_count.total) == (1, 2)
    assert (s.question_count.hits, s.question_count.total) == (3, 4)
    assert (s.question_match.hits, s.question_match.total) == (3, 4)
    assert (s.types.hits, s.types.total) == (2, 3)
    assert (s.option_count.hits, s.option_count.total) == (2, 3)
    assert (s.option_text.hits, s.option_text.total) == (2, 3)
    # q1 has no blank on either side; q2 and q3 have one "____" on both sides
    assert (s.blanks.hits, s.blanks.total) == (3, 3)
    assert (s.underline.hits, s.underline.total) == (0, 1)
    assert (s.bold.hits, s.bold.total) == (1, 1)
    assert s.text.value is not None and s.text.value > 0
    # section I is matched (no stimulus on either side), section II is missing; no skill given
    assert (s.groups.hits, s.groups.total) == (1, 2)
    assert s.skill.value is None and s.stimulus.value is None
    dims = (1 / 2, 3 / 4, 1 / 2, 3 / 4, 2 / 3, 2 / 3, 2 / 3, 1, 0, 1)
    assert s.overall == pytest.approx(sum(dims) / len(dims))


def test_structure_counts_partial_credit() -> None:
    """Off-by-one counts are not scored 0 (the first live baseline read 6 of 7 sections and
    34 of 36 questions, and both counts came out 0)."""
    expected = [SimpleSection.flat(t, [_q(n)]) for t, n in (("I", 1), ("II", 2), ("III", 3))]
    exact = structure_counts(expected, expected)
    assert (exact.section_count.hits, exact.section_count.total) == (3, 3)
    assert (exact.question_count.hits, exact.question_count.total) == (3, 3)
    fewer = structure_counts(expected, expected[:2])
    assert fewer.section_count.value == pytest.approx(2 / 3)
    assert fewer.question_count.value == pytest.approx(2 / 3)
    more = structure_counts(expected[:2], expected)  # too many read is penalised the same way
    assert (more.section_count.hits, more.section_count.total) == (2, 3)
    none = structure_counts(expected, [])
    assert (none.section_count.hits, none.section_count.total) == (0, 3)
    assert (none.question_count.hits, none.question_count.total) == (0, 3)
    # summed over fixtures (a micro-average): 2/3 + 3/3 = 5/6
    total = fewer.add(exact)
    assert (total.section_count.hits, total.section_count.total) == (5, 6)


def test_answers_blank_matches_blank() -> None:
    expected = {"1": "B", "2": None, "3": "Went ", "4": "C"}
    read = {
        "1": ReadAnswer("b"),
        "2": ReadAnswer(None),
        "3": ReadAnswer("went"),
        "4": ReadAnswer("D"),
    }
    a = answer_counts(expected, read)
    assert (a.accuracy.hits, a.accuracy.total) == (3, 4)
    # a missing reading of a blank question still counts as blank
    assert answer_counts({"9": None}, {}).accuracy.value == 1.0


def test_calibration_r11_1_synthetic_set() -> None:
    expected = {str(i): "A" for i in range(1, 11)}
    read = {
        # 4 wrong readings: 3 flagged, 1 not
        "1": ReadAnswer("B", reading_unsure=True),
        "2": ReadAnswer("C", reading_unsure=True),
        "3": ReadAnswer(None, reading_unsure=True),
        "4": ReadAnswer("D", reading_unsure=False),
        # 6 right readings: 1 flagged
        "5": ReadAnswer("A", reading_unsure=True),
        **{str(i): ReadAnswer("a") for i in range(6, 11)},
    }
    c = calibration_counts(expected, read)
    assert (c.wrong_flagged.hits, c.wrong_flagged.total) == (3, 4)
    assert c.wrong_flagged.value == 0.75
    assert (c.correct_flagged.hits, c.correct_flagged.total) == (1, 6)
    lo, hi = c.interval or (0, 0)
    # Wilson 95 % for 3/4: (0.3006, 0.9544)
    assert lo == pytest.approx(0.3006, abs=1e-4)
    assert hi == pytest.approx(0.9544, abs=1e-4)
    assert calibration_counts({"1": "A"}, {"1": ReadAnswer("A")}).interval is None


def test_wilson_edges() -> None:
    assert wilson_interval(0, 0) == (0.0, 1.0)
    lo, hi = wilson_interval(10, 10)
    assert hi == pytest.approx(1.0) and 0.69 < lo < 0.73
    lo, hi = wilson_interval(0, 10)
    assert lo == 0.0 and math.isclose(hi, 1 - 0.7224672001371107, abs_tol=1e-3)


def test_keys_and_mapping() -> None:
    expected = {"1": ["B"], "2": ["went", "had gone"], "3": ["C"]}
    read = {
        "1": ReadKey(["b"], from_key_photo=True),
        "2": ReadKey(["Had gone", "went"], from_key_photo=False),
        "3": ReadKey(["D"], from_key_photo=True),
    }
    k = key_counts(expected, read, has_key_photo=True)
    assert (k.accuracy.hits, k.accuracy.total) == (2, 3)
    assert (k.mapping.hits, k.mapping.total) == (1, 3)
    k2 = key_counts(expected, read, has_key_photo=False)
    assert k2.mapping.total == 0
    assert key_counts(None, read, has_key_photo=True).accuracy.value is None


def _cloze(stimulus: str | None, skill: str = "reading") -> list[SimpleSection]:
    return [
        SimpleSection.flat("II", [_q(1), _q(2)], skill="grammar"),
        SimpleSection(
            "IV",
            [SimpleGroup(stimulus, [_q(3, stem=None), _q(4, stem=None)])],
            skill=skill,
        ),
    ]


def test_structure_passage_cer_groups_and_skill() -> None:
    ref = "A trip to (3) ____ and back (4) ____."
    same = structure_counts(_cloze(ref), _cloze(ref))
    assert same.overall == 1.0
    assert (same.groups.hits, same.groups.total) == (2, 2)
    assert (same.skill.hits, same.skill.total) == (2, 2)
    assert same.stimulus.value == 0.0
    # one typo in the passage, a wrong skill
    hyp = "A trip to (3) ____ and bock (4) ____."
    s = structure_counts(_cloze(ref), _cloze(hyp, skill="vocabulary"))
    assert s.stimulus.value == pytest.approx(1 / len(ref))
    assert (s.skill.hits, s.skill.total) == (1, 2)
    # the passage lost: the group no longer has a stimulus
    lost = structure_counts(_cloze(ref), _cloze(None))
    assert (lost.groups.hits, lost.groups.total) == (1, 2)
    assert lost.stimulus.value == 1.0
    # split into two groups: same questions, but the group count differs
    split = [
        _cloze(ref)[0],
        SimpleSection(
            "IV",
            [SimpleGroup(ref, [_q(3, stem=None)]), SimpleGroup(None, [_q(4, stem=None)])],
            skill="reading",
        ),
    ]
    s2 = structure_counts(_cloze(ref), split)
    assert (s2.groups.hits, s2.groups.total) == (1, 2)
    assert s2.stimulus.value == 0.0
    assert s2.question_match.value == 1.0


def test_key_compare_counts_sentence_forms_as_the_expected_key() -> None:
    """Step 22.3.4: a saved rewrite key carries its forms; it still equals the fixture's key."""
    from etach.eval.metrics import _same_key

    key = "My brother used to stay up late playing mobile games."
    four = [
        key,
        key[:-1],
        "used to stay up late playing mobile games.",
        "used to stay up late playing mobile games",
    ]
    assert _same_key(four, [key]) and _same_key(four[:2], [key])
    assert not _same_key(four, ["My brother used to stay up late."])
    assert not _same_key(["has gone", "gone"], ["has gone"])  # not forms: no new matches
