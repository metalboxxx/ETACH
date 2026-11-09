"""Step 22.4.4: option letters (R22.4.4.1), equal points (R22.4.4.2) and the first-start pass
(R22.4.4.3). Synthetic data only."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from unit.domain.test_review import _world, conn  # noqa: F401

from etach.domain import models as m
from etach.domain.points import clean_label, equal_points, points_possible
from etach.domain.scoring import grade
from etach.domain.test_text import read, render
from etach.domain.validators import validate_choice, validate_content
from etach.store import db
from etach.store.repos import attempts, review, tests
from etach.store.repos.points import run_equal_points_pass, save_content


def _q(qid: str, labels: tuple[str, ...] = ("A", "B", "C", "D")) -> m.Question:
    return m.Question(
        id=qid,
        number=1,
        printed_number=1,
        page_no=1,
        answer_form="choice",
        stem=f"Stem {qid}",
        options=[m.Option(label=lb, text=f"word {i}") for i, lb in enumerate(labels)],
        cue=None,
        points=0.25,
    )


def _sec(sid: str, qs: list[m.Question], points: float, graded: bool = True) -> m.Section:
    groups = [m.QuestionGroup(id=f"g-{sid}", stimulus=None, pictures=[], questions=qs)]
    return m.Section(
        id=sid,
        number=1,
        printed_title=sid,
        title=sid,
        instructions="Choose.",
        points=points,
        points_source="printed",
        skill="grammar" if graded else "writing",
        graded=graded,
        groups=groups if qs else [],
    )


def _numbered(content: m.TestContent) -> m.TestContent:
    n = 1
    for s_no, s in enumerate(content.sections, 1):
        s.number = s_no
        for g in s.groups:
            for q in g.questions:
                q.number = q.printed_number = n
                n += 1
    return content


# --- R22.4.4.1 -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "clean"),
    [("A.", "A"), ("B)", "B"), ("c", "C"), (" d ", "D"), ("(a)", "A"), ("???", "???")],
)
def test_clean_label(raw: str, clean: str) -> None:
    assert clean_label(raw) == clean


def test_r22_4_4_1_dotted_labels_pass_and_are_stored_bare() -> None:
    q = _q("q1", ("A.", "B)", "c", "D."))
    assert validate_choice(q) == []  # comment 7: cloze options with a dot are complete
    content = equal_points(_numbered(m.TestContent(sections=[_sec("I", [q], 2.5)])))
    opts = content.sections[0].groups[0].questions[0].options
    assert opts is not None and [o.label for o in opts] == ["A", "B", "C", "D"]
    got = read(render(content), content).content  # the same through the text read-back
    assert got is not None
    opts = got.sections[0].groups[0].questions[0].options
    assert opts is not None and [o.label for o in opts] == ["A", "B", "C", "D"]
    assert validate_content(got, []) == []


# --- R22.4.4.2 -------------------------------------------------------------------------------


def _shaped(n: int) -> m.TestContent:
    """n graded questions in two printed sections, an empty section and a writing section."""
    half = n // 2
    writing = _sec("IV", [_q("w1")], 1.0, graded=False)
    writing.groups[0].questions[0] = (
        writing.groups[0]
        .questions[0]
        .model_copy(update={"answer_form": "writing", "options": None})
    )
    return _numbered(
        m.TestContent(
            sections=[
                _sec("I", [_q(f"a{i}") for i in range(half)], 2.5),
                _sec("II", [_q(f"b{i}") for i in range(n - half)], 1.5),
                _sec("III", [], 0.5),
                writing,
            ]
        )
    )


@pytest.mark.parametrize("n", [40, 50, 13])
def test_r22_4_4_2_equal_points(n: int) -> None:
    content = equal_points(_shaped(n))
    graded = [q for s in content.sections if s.graded for g in s.groups for q in g.questions]
    assert len(graded) == n and all(q.points == 10 / n for q in graded)
    for s in content.sections:
        assert s.points_source == "equal"
        assert s.points == round(sum(q.points for g in s.groups for q in g.questions), 6)
    assert content.sections[2].points == 0.0 and content.sections[3].points == 0.0
    assert points_possible(content) == 10.0
    assert grade(content, [], []).score_possible == 10.0
    assert points_possible(m.TestContent(sections=[_sec("I", [], 1.0)])) == 0.0


def test_r22_4_4_2_save_paths_give_ten(conn: sqlite3.Connection) -> None:  # noqa: F811
    from etach.domain.review import save_test_text

    w = _world(conn, graded=True)
    stored = save_content(conn, w.t, _shaped(13))
    t = tests.get_test(conn, w.t)
    assert t is not None and t.points_possible == 10.0 and t.content == stored
    assert grade(t.content, [], []).score_possible == t.points_possible
    text = render(t.content)
    assert "# I\n" in text
    save_test_text(conn, w.t, text.replace("# I\n", "I  [7 points]\n", 1))  # typed: ignored
    t = tests.get_test(conn, w.t)
    assert t is not None and t.points_possible == 10.0 and t.content == stored
    a = attempts.get_attempt(conn, w.a1.id)
    assert a is not None and a.score_possible == 10.0


# --- R22.4.4.3 -------------------------------------------------------------------------------


def _teacher_case(c: sqlite3.Connection) -> tuple[str, str]:
    """A T-0006-like test: printed 2.5 / 1.5 / 0.5 sections, an assumed one and an empty one;
    one graded attempt with 30 correct, 8 incorrect and 2 unsure answers."""
    w = _world(c, graded=True)
    legacy = m.TestContent(
        sections=[
            _sec("s-1", [_q(f"q{i}", ("A.", "B.", "C.", "D.")) for i in range(1, 11)], 2.5),
            _sec("s-2", [_q(f"r{i}") for i in range(1, 7)], 1.5),
            _sec("s-3", [_q(f"t{i}") for i in range(1, 3)], 0.5),
            _sec("s-4", [_q(f"u{i}") for i in range(1, 23)], 5.5),
            _sec("s-5", [], 0.5),
        ]
    )
    legacy.sections[3].points_source = "assumed"
    legacy = _numbered(legacy)
    tests.update_content(c, w.t, legacy, 9.75)  # raw, as a pre-v1.19 row
    a = w.a1.id
    c.execute("DELETE FROM answers WHERE attempt_id = ?", (a,))
    qids = [q.id for s in legacy.sections for g in s.groups for q in g.questions]
    verdicts = ["correct"] * 30 + ["incorrect"] * 8 + ["uncertain"] * 2
    for i, (qid, v) in enumerate(zip(qids, verdicts, strict=True)):
        pts = 0.25 if v == "correct" else (0.0 if v == "incorrect" else None)
        c.execute(
            "INSERT INTO answers (attempt_id, question_id, printed_number, value, location,"
            " confidence, verdict, points_awarded)"
            " VALUES (?, ?, ?, 'A', 'circled_option', 0.9, ?, ?)",
            (a, qid, i + 1, v, pts),
        )
    c.execute("UPDATE attempts SET score_earned = 7.5, score_possible = 9.75 WHERE id = ?", (a,))
    review.upsert_item(
        c,
        kind="points_assumed",
        owner="extract",
        dedupe_key=f"points_assumed:r:{w.t}:s-4",
        proposal={"section_id": "s-4"},
        test_id=w.t,
    )
    review.upsert_item(
        c,
        kind="validator_failed",
        owner="extract",
        dedupe_key=f"validator_failed:r:{w.t}:mcq",
        proposal={"validator": "mcq_options"},
        test_id=w.t,
    )
    c.commit()
    return w.t, a


def _snapshot(c: sqlite3.Connection) -> list[list[tuple[object, ...]]]:
    tables = ("tests", "attempts", "answers", "review_items", "messages", "grade_reports")
    return [
        [tuple(r) for r in c.execute(f"SELECT * FROM {t} ORDER BY 1").fetchall()] for t in tables
    ]


def test_r22_4_4_3_first_start_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    def no_model(*_a: object, **_k: object) -> None:
        raise AssertionError("the first-start pass must not call a model")

    monkeypatch.setattr(httpx.Client, "send", no_model)
    path = tmp_path / "data" / "app.db"
    c = db.open_database(path)
    test_id, attempt_id = _teacher_case(c)
    c.execute("INSERT INTO equal_points_pending (id) VALUES (1)")  # as just after migration 0009
    c.commit()
    c.close()

    c = db.open_database(path)  # the first start after the update
    t = tests.get_test(c, test_id)
    assert t is not None and t.points_possible == 10.0
    qs = [q for s in t.content.sections for g in s.groups for q in g.questions]
    assert len(qs) == 40 and all(q.points == 0.25 for q in qs)
    assert [s.points for s in t.content.sections] == [2.5, 1.5, 0.5, 5.5, 0.0]
    assert all(o.label in "ABCD" and len(o.label) == 1 for q in qs for o in q.options or [])
    a = attempts.get_attempt(c, attempt_id)
    assert a is not None and (a.score_earned, a.score_possible) == (7.5, 10.0)
    unsure = [x for x in attempts.list_answers(c, attempt_id) if x.points_awarded is None]
    assert len(unsure) == 2  # unsure stays unsure
    kinds = {
        (r[0], r[1])
        for r in c.execute("SELECT kind, status FROM review_items WHERE test_id = ?", (test_id,))
    }
    assert ("points_assumed", "obsolete") in kinds and ("points_assumed", "open") not in kinds
    assert ("validator_failed", "fixed") in kinds and ("validator_failed", "open") not in kinds
    assert not c.execute("SELECT 1 FROM equal_points_pending").fetchone()
    before = _snapshot(c)
    c.close()

    c = db.open_database(path)  # a second start changes nothing
    assert run_equal_points_pass(c) is False
    assert _snapshot(c) == before
    c.close()


def test_r22_4_4_4_headings_and_word_file_read_two_decimals() -> None:
    """13 graded questions (5 / 4 / 4). v1.21 (D7) supersedes the headings' points: the text
    has none, and a rounded points heading (v1.20.1) still reads back with the computed points;
    the Word file's score reads x/10."""
    from etach.domain.docx_export import _num

    secs = [
        _sec("I", [_q(f"a{i}") for i in range(5)], 0),
        _sec("II", [_q(f"b{i}") for i in range(4)], 0),
        _sec("III", [_q(f"c{i}") for i in range(4)], 0),
        _sec("IV", [], 0, graded=False),
    ]
    content = equal_points(_numbered(m.TestContent(sections=secs)))
    text = render(content)
    assert "points" not in text
    old = text.replace("# I\n", "I  [3.85 points, 0.77 each]\n", 1)
    again = read(old, content).content  # the rounded heading reads back; the points stay computed
    assert again is not None
    assert again.sections[0].points == pytest.approx(50 / 13, abs=1e-6)
    assert f"{_num(7 * 10 / 13)}/{_num(10.0)}" == "5.38/10"
    assert _num(0.2941) == "0.29"


# --- R22.4.8.3 -------------------------------------------------------------------------------


def _heading_texts(content: m.TestContent) -> list[str]:
    from etach.domain import docx_export

    test = m.Test.model_construct(
        meta=m.TestMetadata(occasion="FinalTerm", grade=8),
        content=content,
        points_possible=points_possible(content),
    )
    doc = docx_export.test_document(test)
    return [p.text for p in doc.paragraphs if p.style is not None and p.style.name == "Heading 2"]


@pytest.mark.parametrize(
    ("sizes", "expected"),
    [((10, 10, 10, 10), "10 points · 0.25 each"), ((5, 4, 4), "10 points · 0.77 each")],
    ids=["40 questions", "13 questions"],
)
def test_r22_4_8_3_headings_show_total_and_each(sizes: tuple[int, ...], expected: str) -> None:
    """40 and 13 graded questions. v1.21 (D7) supersedes R22.4.8.3's heading points: the test text
    and the Word file write headings with no points (a writing section keeps "[not graded]"), the
    Word file's line under the title gives each question's value, and typed points are ignored."""
    from etach.domain.docx_export import meta_line

    names = ("I", "II", "III", "IV")
    secs = [
        _sec(name, [_q(f"{name}{i}") for i in range(k)], 0)
        for name, k in zip(names, sizes, strict=False)
    ]
    secs.append(_sec("V", [], 0, graded=False))
    content = equal_points(_numbered(m.TestContent(sections=secs)))
    text = render(content)
    headings = [ln for ln in text.split("\n") if ln.startswith("#")]
    assert headings == [f"# {n}" for n in names[: len(sizes)]] + ["# V  [not graded]"]
    again = read(text, content).content
    assert again == content  # round trip
    typed = text.replace("# I\n", "I  [9 points, 4 each]\n", 1)
    assert read(typed, content).content == content  # typed points: ignored
    assert _heading_texts(content) == [*names[: len(sizes)], "V  [not graded]"]
    test = m.Test.model_construct(
        meta=m.TestMetadata(occasion="FinalTerm"), content=content, points_possible=10.0
    )
    assert meta_line(test) == expected


@pytest.mark.parametrize(
    "tag",
    ["[2.5 points]", "[0.25 points each]", "[2.5 points: 1 / 1.5]", "[2.5 points, assumed]"],
)
def test_r22_4_8_3_old_heading_forms_still_read(tag: str) -> None:
    secs = [_sec("I", [_q("a"), _q("b")], 0)]
    content = equal_points(_numbered(m.TestContent(sections=secs)))
    text = render(content)
    line = next(ln for ln in text.split("\n") if ln == "# I")
    result = read(text.replace(line, f"I  {tag}".rstrip()), content)
    assert result.errors == []
    assert result.content == content
