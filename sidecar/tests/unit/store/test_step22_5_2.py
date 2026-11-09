"""Step 22.5.2 (data-model v1.21, decisions D2, D7, D8): headings without points (R22.5.2.3),
untitled sections titled from their skill (R22.5.2.4), the "A.." options (R22.5.2.5) and the
store side of Extract again into the same test (R22.5.2.6). Synthetic data only."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from unit.domain.test_review import _world, conn  # noqa: F401
from unit.store.test_equal_points import _numbered, _q, _sec

from etach.domain import docx_export, working
from etach.domain import models as m
from etach.domain.points import equal_points
from etach.domain.renumber import clean_option_label, merge_pages
from etach.domain.section_titles import fill_titles, is_untitled, skill_title
from etach.domain.test_text import heading_text, points_each, read, render
from etach.domain.working import PageTranscript, PreparedPage
from etach.store import db
from etach.store.repos import attempts, extract_again, keys, regrade, review, tests
from etach.store.repos.text_pass import run_test_text_pass

# --- R22.5.2.5: the "A.." options ---------------------------------------------------------------

# Stored label shapes that ``points.clean_label`` (step 22.4.4) left as they were: a second dot,
# a fullwidth letter and full stop, a Cyrillic capital A, a zero-width space, a comma.
BAD_LABELS = ["A..", chr(0xFF21) + chr(0xFF0E), chr(0x0410) + ".", "A." + chr(0x200B), "A,"]


def _mcq(labels: list[str]) -> m.TestContent:
    q = m.Question(
        id="q-1",
        number=1,
        printed_number=1,
        page_no=1,
        answer_form="choice",
        stem="She ____ to school.",
        options=[m.Option(label=lb, text=w) for lb, w in zip(labels, ["go", "goes"], strict=True)],
        cue=None,
        points=10.0,
    )
    group = m.QuestionGroup(id="g-1", stimulus=None, pictures=[], questions=[q])
    return m.TestContent(
        sections=[
            m.Section(
                id="s-1",
                number=1,
                printed_title="I. GRAMMAR",
                title="I. GRAMMAR",
                instructions="",
                points=10.0,
                points_source="equal",
                skill="grammar",
                groups=[group],
            )
        ]
    )


@pytest.mark.parametrize("bad", BAD_LABELS)
def test_r22_5_2_5_a_dot_dot_renders_on_one_line(bad: str) -> None:
    """Before the fix, ``render`` wrote the stored label and a dot ("A.."): the line no longer
    read as an option, so the option's word went to the next line."""
    text = render(_mcq([bad, "B"]))
    assert "   A. go    B. goes\n" in text
    assert "A.." not in text and "\n   go" not in text
    back = read(text, _mcq([bad, "B"])).content
    assert back is not None
    opts = back.sections[0].groups[0].questions[0].options
    assert [(o.label, o.text) for o in opts or []] == [("A", "go"), ("B", "goes")]


@pytest.mark.parametrize("bad", BAD_LABELS)
def test_r22_5_2_5_the_merge_stores_the_bare_letter(bad: str) -> None:
    assert clean_option_label(bad) == "A"
    page = PageTranscript(
        page_no=1,
        header_text=None,
        sections=[
            {
                "printed_title": "I",
                "instructions": "Choose.",
                "kind": "questions",
                "skill": "grammar",
                "points_text": None,
                "range_first": None,
                "range_last": None,
                "groups": [
                    {
                        "stimulus": None,
                        "pictures": [],
                        "questions": [
                            {
                                "printed_number": 1,
                                "answer_form": "choice",
                                "stem": "She ____ to school.",
                                "options": [
                                    {"label": bad, "text": "go"},
                                    {"label": "B.", "text": "goes"},
                                ],
                                "cue": None,
                            }
                        ],
                    }
                ],
            }
        ],
        llm_call_id="c-1",
    )
    content = merge_pages([page], page_files={1: "f-1"}).draft.content
    q = content.sections[0].groups[0].questions[0]
    assert [o.label for o in q.options or []] == ["A", "B"]
    assert "   A. go    B. goes\n" in render(content)


def test_clean_option_label_leaves_the_unreadable_mark() -> None:
    assert clean_option_label("???") == "???"
    assert clean_option_label("(c)") == "C"


# --- R22.5.2.3: headings without points ----------------------------------------------------------


def test_r22_5_2_3_headings_have_no_points_and_writing_says_not_graded() -> None:
    secs = [_sec("I", [_q(f"a{i}") for i in range(40)], 0), _sec("II", [], 0, graded=False)]
    content = equal_points(_numbered(m.TestContent(sections=secs)))
    text = render(content)
    assert [ln for ln in text.split("\n") if ln.startswith("#")] == ["# I", "# II  [not graded]"]
    assert "point" not in text
    test = m.Test.model_construct(
        meta=m.TestMetadata(occasion="FinalTerm"), content=content, points_possible=10.0
    )
    doc = docx_export.test_document(test)
    heads = [p.text for p in doc.paragraphs if p.style is not None and p.style.name == "Heading 2"]
    assert heads == ["I", "II  [not graded]"] == [heading_text(s) for s in content.sections]
    assert docx_export.meta_line(test) == "10 points · 0.25 each"
    assert points_each(content) == 0.25
    # an old points bracket gives the same test as none
    old = text.replace("# I\n", "I  [2.5 points, 0.25 each]\n").replace(
        "# II  [not graded]", "II  [0 points, not graded]"
    )
    assert read(old, content).content == read(text, content).content == content


def test_points_each_counts_graded_questions_only() -> None:
    def content(n: int) -> m.TestContent:
        secs = [_sec("I", [_q(f"a{i}") for i in range(n)], 0), _sec("II", [_q("w")], 0, False)]
        return equal_points(_numbered(m.TestContent(sections=secs)))

    assert points_each(content(50)) == 0.2
    assert points_each(content(45)) == pytest.approx(10 / 45)
    assert points_each(m.TestContent(sections=[])) is None


def test_hash_heading_forms_read() -> None:
    text = (
        "# I. PRONUNCIATION\nChoose.\n\n1. She ____ to school.\n   A. go    B. goes\n\n"
        "# PART [A]\n\n2. Pick.\n   A. x    B. y\n\n#  [title: Reading]\n\n3. Read.\n\n"
        "# VI. WRITING  [not graded]\n\n4. Write.\n"
    )
    got = read(text, None).content
    assert got is not None
    assert [(s.printed_title, s.title, s.graded) for s in got.sections] == [
        ("I. PRONUNCIATION", "I. PRONUNCIATION", True),
        ("PART [A]", "PART [A]", True),  # an unknown bracket stays in the title
        ("", "Reading", True),
        ("VI. WRITING", "VI. WRITING", False),
    ]
    assert read(render(got), got).content == got


# --- R22.5.2.4: untitled sections ----------------------------------------------------------------


def _titled(title: str, skill: str, typed: str | None = None) -> m.Section:
    return m.Section(
        id=f"s-{title}-{skill}",
        number=1,
        printed_title=title,
        title=typed if typed is not None else title,
        instructions="",
        points=0.0,
        points_source="equal",
        skill=skill,
        groups=[],
    )


def test_r22_5_2_4_fill_titles() -> None:
    assert is_untitled("") and is_untitled(" I. ") and is_untitled("1.") and is_untitled("(IV)")
    assert not is_untitled("PART A") and not is_untitled("Reading")
    assert skill_title("word_form") == "WORD FORM" and skill_title("mixed") is None
    content = m.TestContent(
        sections=[
            _titled("I.", "pronunciation"),
            _titled("", "word_form"),
            _titled("III", "reading"),
            _titled("IV.", "mixed"),
            _titled("V.", "nonsense"),
            _titled("VI. Choose the word", "grammar"),
            _titled("VII.", "grammar", typed="My title"),  # a title typed on its own
        ]
    )
    got = fill_titles(content)
    assert [(s.printed_title, s.title) for s in got.sections] == [
        ("I. PRONUNCIATION", "I. PRONUNCIATION"),
        ("WORD FORM", "WORD FORM"),
        ("III. READING", "III. READING"),
        ("IV.", "IV."),
        ("V.", "V."),
        ("VI. Choose the word", "VI. Choose the word"),
        ("VII.", "My title"),
    ]
    assert fill_titles(got) == got


def _stored(conn: sqlite3.Connection) -> str:  # noqa: F811
    w = _world(conn, graded=True)
    content = equal_points(
        m.TestContent(
            sections=[
                _titled("I.", "pronunciation").model_copy(
                    update={
                        "groups": [
                            m.QuestionGroup(
                                id="g-1",
                                stimulus=None,
                                pictures=[],
                                questions=[_q("q1", ("A..", "B"))],
                            )
                        ]
                    }
                ),
                _titled("II.", "mixed"),
                _titled("III. My words", "grammar"),
            ]
        )
    )
    tests.update_content(conn, w.t, content, 10.0)  # the stored shape, not cleaned
    return w.t


def test_r22_5_2_4_first_start_pass_runs_once(tmp_path: Path) -> None:
    path = tmp_path / "data" / "app.db"
    c = db.open_database(path)
    test_id = _stored(c)
    c.execute("INSERT INTO test_text_pending (id) VALUES (1)")  # as just after migration 0011
    c.commit()
    c.close()

    c = db.open_database(path)  # the first start after the update
    t = tests.get_test(c, test_id)
    assert t is not None
    assert [s.printed_title for s in t.content.sections] == [
        "I. PRONUNCIATION",
        "II.",
        "III. My words",
    ]
    q = t.content.sections[0].groups[0].questions[0]
    assert [o.label for o in q.options or []] == ["A", "B"]
    assert not c.execute("SELECT 1 FROM test_text_pending").fetchone()
    before = (t.content, t.updated_at)
    assert run_test_text_pass(c) is False  # the row is gone: a second start changes nothing
    c.close()
    c = db.open_database(path)
    t = tests.get_test(c, test_id)
    assert t is not None and (t.content, t.updated_at) == before
    c.close()


# --- R22.5.2.6: replacing the test (store side) -------------------------------------------------


def _content_of(stems: dict[int, str]) -> m.TestContent:
    qs = [
        m.Question(
            id=f"n{n}",
            number=n,
            printed_number=n,
            page_no=1,
            answer_form="choice",
            stem=stem,
            options=[m.Option(label="A", text="one"), m.Option(label="B", text="two")],
            cue=None,
            points=0.0,
        )
        for n, stem in stems.items()
    ]
    group = m.QuestionGroup(id="g-n", stimulus=None, pictures=[], questions=qs)
    section = _titled("I. GRAMMAR", "grammar").model_copy(update={"groups": [group]})
    return equal_points(m.TestContent(sections=[section]))


def test_r22_5_2_6_replace_keeps_the_id_and_moves_what_matches(
    conn: sqlite3.Connection,  # noqa: F811
) -> None:
    """The world's test T has q1..q3 ("Stem 1".."Stem 3"), a teacher key on q1 and q3 is keyed
    by the AI; attempts a1, a2 are graded. The new reading: question 1 the same (exact), question
    2 reworded a little (matched, not exact), question 3 gone, question 4 new."""
    w = _world(conn, graded=True)
    keys.upsert_key(
        conn,
        m.AnswerKey(
            test_id=w.t,
            question_id="q1",
            accepted=["A"],
            reason_vi=None,
            source="teacher_edit",
            status="teacher_verified",
            confidence=None,
            updated_at="2026-01-01T00:00:00Z",  # type: ignore[arg-type]
        ),
    )
    keys.upsert_key(conn, keys.get_key(conn, w.t, "q2") or _ai_key(w.t, "q2"))
    tests.set_question_tags(conn, w.t, "q2", ["GR-TENSE"])
    tests.set_question_tags(conn, w.t, "q3", ["VOC-TOPIC"])
    gone, _ = review.upsert_item(
        conn, kind="uncertain_answer", owner="extract", dedupe_key=f"uncertain_answer:{w.a1.id}:q3",
        proposal={}, test_id=w.t, attempt_id=w.a1.id, question_id="q3",
    )  # fmt: skip
    moved, _ = review.upsert_item(
        conn, kind="uncertain_answer", owner="extract", dedupe_key=f"uncertain_answer:{w.a1.id}:q2",
        proposal={}, test_id=w.t, attempt_id=w.a1.id, question_id="q2",
    )  # fmt: skip
    new = _content_of({1: "Stem 1", 5: "Stem 2", 4: "A brand new question here"})
    draft = working.TestDraft(
        meta=m.TestMetadata(occasion="FinalTerm", grade=8),
        content=new,
        fingerprint="fp-new",
        points_possible=10.0,
    )
    conn.execute(
        "INSERT INTO files (id, path, kind, created_at) VALUES (?, ?, ?, ?)",
        ("F-NEW", "files/F-/F-NEW.png", "derived", "2026-01-01T00:00:00Z"),
    )
    page = PreparedPage(
        page_no=1, file_id="F-NEW", source_file_id="F-NEW", rotation=0, text_layer=None
    )
    with db.transaction(conn):
        report = extract_again.replace_test(conn, w.t, draft, [page])
        regrade.mark(conn, w.t)

    assert report.matched == {"q1": "n1", "q2": "n5"} and report.exact == {"n1"}
    assert report.removed == ["q3"]
    t = tests.get_test(conn, w.t)
    assert t is not None and t.fingerprint == "fp-new"
    assert [q.id for g in t.content.sections[0].groups for q in g.questions] == ["n1", "n5", "n4"]
    # the key on the exact match stays (here the teacher's); the others are keyed again
    assert [(k.question_id, k.source) for k in keys.list_keys(conn, w.t)] == [
        ("n1", "teacher_edit")
    ]
    assert tests.list_question_tags(conn, w.t) == {"n5": ["GR-TENSE"]}
    for att in (w.a1, w.a2):
        ids = sorted(a.question_id for a in attempts.list_answers(conn, att.id))
        assert ids == ["n1", "n4", "n5"]  # q3's answer is gone; n4 has an empty row
    assert review.get_item(conn, gone.id).status == "obsolete"  # type: ignore[union-attr]
    item = review.get_item(conn, moved.id)
    assert item is not None and item.status == "open" and item.question_id == "n5"
    assert item.dedupe_key == f"uncertain_answer:{w.a1.id}:n5"
    assert tests.list_test_pages(conn, w.t) == [(w.t, 1, "F-NEW")]
    assert regrade.is_pending(conn, w.t)
    a = attempts.get_attempt(conn, w.a1.id)
    assert a is not None and a.score_possible == 10.0


def test_r22_5_2_12_replace_keeps_ai_keys_on_exact_matches(
    conn: sqlite3.Connection,  # noqa: F811
) -> None:
    """D8 addition: the world's q1 has an unsure AI key (``ai_uncertain``, 0.4, an explanation
    and an open ``uncertain_key`` item), q2 an AI key on a question the new reading rewords, q3 a
    teacher key. The new reading keeps questions 1 and 3 word for word and rewords question 2."""
    w = _world(conn, graded=True)
    q1_before = keys.get_key(conn, w.t, "q1")
    assert q1_before is not None and q1_before.status == "ai_uncertain"
    keys.upsert_key(conn, _ai_key(w.t, "q2"))
    teacher = m.AnswerKey(
        test_id=w.t,
        question_id="q3",
        accepted=["C"],
        reason_vi=None,
        source="teacher_edit",
        status="teacher_verified",
        confidence=None,
        updated_at="2026-01-01T00:00:00Z",  # type: ignore[arg-type]
    )
    keys.upsert_key(conn, teacher)
    unsure = {}
    for qid in ("q1", "q2"):
        unsure[qid], _ = review.upsert_item(
            conn, kind="uncertain_key", owner="extract", dedupe_key=f"uncertain_key:{w.t}:{qid}",
            proposal={}, test_id=w.t, question_id=qid,
        )  # fmt: skip
    new = _content_of({1: "Stem 1", 2: "Stems 2", 3: "Stem 3"})
    draft = working.TestDraft(
        meta=m.TestMetadata(occasion="FinalTerm", grade=8),
        content=new,
        fingerprint="fp-new",
        points_possible=10.0,
    )
    with db.transaction(conn):
        report = extract_again.replace_test(conn, w.t, draft, [])

    assert report.exact == {"n1", "n3"} and report.matched["q2"] == "n2"
    assert sorted(report.keys_kept) == ["n1", "n3"]
    by_q = {k.question_id: k for k in keys.list_keys(conn, w.t)}
    assert sorted(by_q) == ["n1", "n3"]  # the reworded question 2 is keyed again
    # the AI key stays as it was, unsure state included; only its question id follows
    assert by_q["n1"] == q1_before.model_copy(update={"question_id": "n1"})
    # the teacher key is unchanged
    assert by_q["n3"] == teacher.model_copy(update={"question_id": "n3"})
    assert [r[0] for r in conn.execute("SELECT question_id FROM explanations WHERE test_id = ?",
                                       (w.t,))] == ["n1"]  # fmt: skip
    kept = review.get_item(conn, unsure["q1"].id)
    assert kept is not None and kept.status == "open" and kept.question_id == "n1"
    assert review.get_item(conn, unsure["q2"].id).status == "obsolete"  # type: ignore[union-attr]


def _ai_key(test_id: str, qid: str) -> m.AnswerKey:
    return m.AnswerKey(
        test_id=test_id,
        question_id=qid,
        accepted=["B"],
        reason_vi=None,
        source="ai",
        status="ai_unverified",
        confidence=0.9,
        updated_at="2026-01-01T00:00:00Z",  # type: ignore[arg-type]
    )
