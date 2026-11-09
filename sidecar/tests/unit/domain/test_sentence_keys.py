"""R22.3.4.1: the sentence-key forms (teacher's comment 10, data-model §2.4 v1.15)."""

from __future__ import annotations

from etach.domain import keys
from etach.domain import models as m

KEY = "My brother used to stay up late playing mobile games."
FOUR = [
    "My brother used to stay up late playing mobile games.",
    "My brother used to stay up late playing mobile games",
    "used to stay up late playing mobile games.",
    "used to stay up late playing mobile games",
]


def q(type_: str = "rewrite", stem: str | None = None, cue: str | None = None) -> m.Question:
    return m.Question(
        id="q-1", number=1, printed_number=37, page_no=1, type=type_,  # type: ignore[arg-type]
        stem=stem, options=[], cue=cue, points=0.5,
    )  # fmt: skip


def test_teachers_example_four_forms_canonical_first() -> None:
    assert keys.sentence_forms(KEY, "My brother") == FOUR


def test_no_given_words_two_forms() -> None:
    assert keys.sentence_forms(KEY, None) == FOUR[:2]
    assert keys.sentence_forms(KEY, "Your sister") == FOUR[:2]  # the key does not start with it


def test_punctuation_letters_and_case_kept() -> None:
    forms = keys.sentence_forms('Tôi đã nói: "Đừng đi!", rồi về.', None)
    assert forms == ['Tôi đã nói: "Đừng đi!", rồi về.', 'Tôi đã nói: "Đừng đi!", rồi về']
    assert keys.sentence_forms("Does she like it?", "Does") == ["Does she like it?", "she like it?"]


def test_pure_and_idempotent() -> None:
    first = keys.sentence_forms(KEY, "My brother")
    assert keys.sentence_forms(KEY, "My brother") == first
    assert keys.sentence_forms(first[0], "My brother") == first
    question = q(stem="My brother no longer stays up late.\n→ My brother ……", cue="(used to)")
    once = keys.with_forms([KEY], question)
    assert keys.with_forms(once, question) == once == FOUR


def test_given_words_from_stem_arrow_line_or_cue() -> None:
    assert keys.with_forms([KEY], q(stem="He no longer ... -> My brother ____")) == FOUR
    assert (
        keys.with_forms([KEY], q(stem="My brother no longer stays up late.", cue="My brother ..."))
        == FOUR
    )
    # the s1 shape: the cue is a structure hint, not opening words
    assert (
        keys.with_forms([KEY], q(stem="My brother no longer stays up.", cue="(used to)"))
        == FOUR[:2]
    )


def test_combine_too_other_types_unchanged_variants_kept() -> None:
    assert keys.with_forms([KEY, "other"], q("combine", cue="My brother")) == [*FOUR, "other"]
    assert keys.with_forms(["goes."], q("gap_fill", cue="goes")) == ["goes."]
    assert keys.with_forms([KEY], None) == [KEY]


def _key(accepted: list[str]) -> m.AnswerKey:
    from datetime import UTC, datetime

    return m.AnswerKey(
        test_id="T-1", question_id="q-1", accepted=accepted, reason_vi=None, source="ai",
        status="ai_unverified", confidence=None, updated_at=datetime.now(UTC),
    )  # fmt: skip


def test_teacher_removed_form_stays_removed_until_key_text_changes() -> None:
    question = q(cue="My brother ...")
    kept = [FOUR[0], FOUR[2]]  # the teacher removed two forms
    assert keys.teacher_accepted(_key(FOUR), kept, question) == kept
    new = "My brother used to stay up very late."
    assert keys.teacher_accepted(_key(kept), [new], question) == [
        new, "My brother used to stay up very late", "used to stay up very late.",
        "used to stay up very late",
    ]  # fmt: skip
    assert keys.teacher_accepted(None, [KEY], question) == FOUR
