"""M1 p2: ``transcribe_page`` puts shared passages whole into the group ``stimulus``.

The phrases pinned here follow the teacher's fixture convention (cloze gaps ``(17) ____`` in the
stimulus with null stems, the passage title as the stimulus' first line, a dictionary entry as the
stimulus), so a later prompt edit cannot drop them silently.
"""

from __future__ import annotations

from etach.prompts.render import FilePromptProvider


def _text() -> str:
    return FilePromptProvider().base_text("transcribe_page")


def test_passage_rule_keeps_the_whole_text_in_the_stimulus() -> None:
    text = _text()
    assert "goes whole into one group's `stimulus`" in text
    assert "Never cut it into the question stems." in text


def test_cloze_gap_notation_and_null_stem() -> None:
    text = _text()
    assert "`(17) ____`" in text
    assert "cloze question's `stem` is null" in text


def test_passage_title_stays_in_the_stimulus() -> None:
    text = _text()
    assert "A passage title is the first line of the stimulus" in text
    assert "is never a new section" in text


def test_one_dictionary_rule() -> None:
    text = _text()
    assert "Dictionary entry: the whole entry is the stimulus" in text
    assert "Its senses\n    and examples are never questions" in text
    # merged: the Pictures rule points to the Passages rule instead of repeating it
    assert "a dictionary\n  entry follows the Passages rule" in text
    assert "a sign, a dictionary entry" not in text
