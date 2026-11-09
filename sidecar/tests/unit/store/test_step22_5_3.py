"""Step 22.5.3 (decision D9): fewer question types — the answer form and the context.

R22.5.3.1 (no old type value in a schema; context from the stimulus), R22.5.3.2 (the first-start
pass), R22.5.3.3 (grading by form, with every difference from the old types listed) and the
sidecar part of R22.5.3.4 (test text, Word export, eval form accuracy).
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from unit.domain.grading_support import answer as g_answer
from unit.domain.grading_support import key as g_key
from unit.domain.grading_support import question as g_question
from unit.store.conftest import answer, make_attempt, make_test

from etach.domain import docx_export, scoring
from etach.domain import models as m
from etach.domain.llm_schemas import TranscribedQuestion, read_answers_schema
from etach.domain.review import resolve
from etach.domain.test_text import read, render
from etach.eval.metrics import SimpleQuestion, SimpleSection, structure_counts
from etach.store import db
from etach.store.repos import attempts, keys, regrade, tests
from etach.store.repos import review as review_repo
from etach.store.repos.answer_form_pass import (
    revert_content_data,
    run_answer_form_pass,
    upgrade_content_data,
)

SIDECAR = Path(__file__).resolve().parents[3]
REPO = SIDECAR.parent
OLD_TYPES = [
    "mcq",
    "true_false",
    "gap_fill",
    "word_form",
    "verb_form",
    "rewrite",
    "combine",
    "ordering",
    "matching",
    "short_answer",
    "writing",
]
#: The table of D9 (plan step 22.5.3), written out here on purpose.
TABLE = {
    "mcq": "choice",
    "true_false": "choice",
    "matching": "choice",
    "gap_fill": "word",
    "word_form": "word",
    "verb_form": "word",
    "rewrite": "sentence",
    "combine": "sentence",
    "ordering": "sentence",
    "short_answer": "sentence",
    "writing": "writing",
}
FORMS = ("choice", "word", "sentence", "writing")


# --- R22.5.3.1 -----------------------------------------------------------------------------------


def test_r22_5_3_1_table_is_the_d9_table() -> None:
    assert m.FORM_OF_OLD_TYPE == TABLE


def _generated() -> list[Path]:
    files = list((SIDECAR / "schema").rglob("*.json"))
    files += list((REPO / "app" / "src" / "gen").rglob("*.ts"))
    files += list((SIDECAR / "src" / "etach" / "prompts").rglob("*.md"))
    return files


def test_r22_5_3_1_no_old_type_value_in_schemas_or_prompts() -> None:
    # word_form / rewrite / writing are also section skills; mcq … short_answer are not
    only_types = [t for t in OLD_TYPES if t not in ("word_form", "rewrite", "writing")]
    pattern = re.compile(r'"(' + "|".join(only_types) + r')"|`(' + "|".join(only_types) + r")`")
    hits: list[str] = []
    for path in _generated():
        text = path.read_text(encoding="utf-8")
        hits += [f"{path.name}: {mt.group(0)}" for mt in pattern.finditer(text)]
        if "QuestionType" in text:
            hits.append(f"{path.name}: QuestionType")
    # the only place an old type may appear is the old_type enum of Question
    hits = [h for h in hits if not h.startswith(("Question", "openapi", "Test", "Section"))]
    assert hits == []


def test_r22_5_3_1_old_type_is_the_only_old_value_in_question_schema() -> None:
    schema = m.Question.model_json_schema()
    props = schema["properties"]
    assert "type" not in props
    assert set(props) >= {"answer_form", "context", "old_type"}
    text = json.dumps({k: v for k, v in props.items() if k != "old_type"})
    for old in ("mcq", "true_false", "gap_fill", "verb_form", "short_answer", "ordering"):
        assert old not in text
    llm = json.dumps(TranscribedQuestion.model_json_schema())
    for old in OLD_TYPES[:-1]:
        assert f'"{old}"' not in llm


@pytest.mark.parametrize("given", [None, "single", "paragraph"])
def test_r22_5_3_1_context_comes_from_the_stimulus_whatever_is_given(given: str | None) -> None:
    def group(stimulus: str | None) -> m.QuestionGroup:
        q: dict[str, Any] = {
            "id": "q-1",
            "number": 1,
            "printed_number": 1,
            "page_no": 1,
            "answer_form": "word",
            "stem": "s ____",
            "options": None,
            "cue": None,
            "points": 0.25,
        }
        if given is not None:
            q["context"] = given
        return m.QuestionGroup.model_validate(
            {"id": "g", "stimulus": stimulus, "pictures": [], "questions": [q]}
        )

    assert group("A passage (1) ____.").questions[0].context == "paragraph"
    assert group(None).questions[0].context == "single"


# --- R22.5.3.2: the first-start pass -------------------------------------------------------------


def _old_content() -> dict[str, Any]:
    """Raw content in the shape before step 22.5.3: one question of each of the 11 old types,
    the even ones in a group with a stimulus."""
    groups = []
    for i, old in enumerate(OLD_TYPES, start=1):
        options = (
            [{"label": "A", "text": "one"}, {"label": "B", "text": "two"}]
            if old in ("mcq", "matching")
            else None
        )
        groups.append(
            {
                "id": f"g-{i}",
                "stimulus": "A passage." if i % 2 == 0 else None,
                "pictures": [],
                "questions": [
                    {
                        "id": f"q-{i}",
                        "number": i,
                        "printed_number": i,
                        "page_no": 1,
                        "type": old,
                        "stem": f"Stem {i} ____",
                        "options": options,
                        "cue": None,
                        "points": 0.25,
                    }
                ],
            }
        )
    section = {
        "id": "s-1",
        "number": 1,
        "printed_title": "I",
        "title": "Mixed",
        "instructions": "Do it.",
        "points": 2.75,
        "points_source": "printed",
        "skill": "mixed",
        "groups": groups,
    }
    return {"sections": [section]}


def _snapshot(conn: sqlite3.Connection) -> dict[str, list[tuple[Any, ...]]]:
    names = [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    ]
    out = {}
    for name in names:
        if name in ("answer_form_pending",):
            continue
        cols = "*" if name != "tests" else "id, meta, fingerprint, points_possible, updated_at"
        rows = conn.execute(f"SELECT {cols} FROM {name} ORDER BY 1").fetchall()
        out[name] = [tuple(r) for r in rows]
    return out


def _seed(path: Path) -> str:
    c = db.open_database(path)
    test = make_test(c)
    attempt = make_attempt(c, test.id)
    attempts.insert_answers(
        c, [answer(attempt.id, f"q-{i}", value="A", printed_number=i) for i in (1, 2, 3)]
    )
    for i in (1, 3):
        k = g_key(f"q-{i}", "A").model_copy(update={"test_id": test.id})
        keys.upsert_key(c, k)
    regrade.mark(c, test.id)
    c.execute("UPDATE tests SET content = ? WHERE id = ?", (json.dumps(_old_content()), test.id))
    c.execute("INSERT INTO answer_form_pending (id) VALUES (1)")  # as just after migration 0012
    c.commit()
    c.close()
    return test.id


def test_r22_5_3_2_pass_maps_every_old_type_and_runs_once(tmp_path: Path) -> None:
    path = tmp_path / "data" / "app.db"
    test_id = _seed(path)
    raw = sqlite3.connect(path)
    before = _snapshot(raw)
    raw.close()

    c = db.open_database(path)  # the first start after the update runs the pass
    assert not c.execute("SELECT 1 FROM answer_form_pending").fetchone()
    t = tests.get_test(c, test_id)
    assert t is not None
    got = {q.id: q for g in t.content.sections[0].groups for q in g.questions}
    for i, old in enumerate(OLD_TYPES, start=1):
        q = got[f"q-{i}"]
        assert (q.answer_form, q.old_type) == (TABLE[old], old)
        want_context = None if old == "writing" else ("paragraph" if i % 2 == 0 else "single")
        assert q.context == want_context, old
    tf = got["q-2"]
    assert [o.label for o in tf.options or []] == ["T", "F"]
    # student answers, keys, verdicts, grade reports, regrade_pending: row-for-row unchanged
    assert _snapshot(c) == before
    after = c.execute("SELECT content FROM tests WHERE id = ?", (test_id,)).fetchone()[0]
    assert run_answer_form_pass(c) is False  # the row is gone: a second start changes nothing
    c.close()
    c = db.open_database(path)
    assert c.execute("SELECT content FROM tests WHERE id = ?", (test_id,)).fetchone()[0] == after
    assert _snapshot(c) == before
    c.close()


def test_r22_5_3_2_revert_round_trip() -> None:
    old = _old_content()
    upgraded = upgrade_content_data(old)
    reverted = revert_content_data(upgraded)
    qs = [q for g in reverted["sections"][0]["groups"] for q in g["questions"]]
    olds = [q for g in old["sections"][0]["groups"] for q in g["questions"]]
    assert [q["type"] for q in qs] == OLD_TYPES
    for a, b in zip(qs, olds, strict=True):
        assert {k: a.get(k) for k in b} == b
    assert upgrade_content_data(upgraded) == upgraded  # already mapped: left as it is


# --- R22.5.3.3: grading by form ------------------------------------------------------------------


def _verdict(form: str, value: str, accepted: str = "went", judged: Any = None) -> Any:
    return scoring.grade_answer(
        g_question("q-1", form), g_answer("q-1", value), g_key("q-1", accepted), judged
    )


def test_r22_5_3_3_each_form_follows_its_rule() -> None:
    assert (_verdict("choice", "A", "A").rule, _verdict("choice", "B", "A").rule) == (4, 5)
    assert _verdict("word", "went").rule == 6
    near = _verdict("word", "wnet")
    assert near.rule == 7 and near.near_miss
    assert _verdict("sentence", "He went home.", "He went home.").rule == 6
    assert _verdict("sentence", "He gone home.", "He went home.").needs_judge
    assert _verdict("sentence", "x", "y", judged="correct").rule == 9
    assert scoring.graded_questions(m.TestContent(sections=[])) == []


def test_r22_5_3_3_old_to_new_differences_are_listed() -> None:
    """Every place where grading changes because of the new forms:

    1. former short_answer (now sentence): not exact → the judge (was: incorrect, rule 6/7);
    2. former ordering (now sentence): not exact → the judge (rule 9; was rule 12, exact only);
    3. former combine: follows row 9 (was row 13);
    4. former matching (now choice): rows 4/5 (was row 12);
    5. writing: not graded (was: judged).
    """
    for old in ("short_answer", "ordering", "combine"):
        assert m.FORM_OF_OLD_TYPE[old] == "sentence"
    assert _verdict("sentence", "a b c", "c b a").needs_judge  # 1, 2, 3
    assert _verdict("sentence", "a b c", "c b a", judged="incorrect").rule == 9
    assert m.FORM_OF_OLD_TYPE["matching"] == "choice"
    assert (_verdict("choice", "C", "C").rule, _verdict("choice", "D", "C").rule) == (4, 5)  # 4
    assert all(_verdict(f, "x", "y").rule not in (12, 13) for f in ("choice", "word", "sentence"))
    assert m.FORM_OF_OLD_TYPE["writing"] == "writing"  # 5: grade() drops writing answers


# --- R22.5.3.4 (sidecar part) --------------------------------------------------------------------


def _form_content() -> m.TestContent:
    def q(i: int, form: str, options: list[m.Option] | None = None) -> m.Question:
        return m.Question(
            id=f"q-{i}",
            number=i,
            printed_number=i,
            page_no=1,
            answer_form=form,  # type: ignore[arg-type]
            stem=f"Stem {i} ____" if form != "sentence" else f"Rewrite {i}.",
            options=options,
            cue=None,
            answer_start="He" if form == "sentence" else None,
            points=0.25,
        )

    opts = [m.Option(label=x, text=f"opt {x}") for x in "ABCD"]
    questions = [q(1, "choice", opts), q(2, "word"), q(3, "sentence")]
    group = m.QuestionGroup(id="g-1", stimulus=None, pictures=[], questions=questions)
    section = m.Section(
        id="s-1",
        number=1,
        printed_title="I",
        title="Mixed",
        instructions="Do it.",
        points=0.75,
        points_source="printed",
        skill="mixed",
        groups=[group],
    )
    return m.TestContent(sections=[section])


def test_r22_5_3_4_test_text_round_trip_keeps_the_form() -> None:
    content = _form_content()
    result = read(render(content), content)
    assert not result.errors
    assert result.content is not None
    forms = [q.answer_form for s in result.content.sections for g in s.groups for q in g.questions]
    assert forms == ["choice", "word", "sentence"]


def test_r22_5_3_4_word_export_per_form() -> None:
    test = m.Test.model_construct(
        meta=m.TestMetadata(occasion="FinalTerm"), content=_form_content(), points_possible=0.75
    )
    texts = [p.text for p in docx_export.test_document(test).paragraphs]
    assert any("opt A" in t and "opt D" in t for t in texts)  # choice: its options
    assert any(t.startswith("2. Stem 2") for t in texts)  # word: the stem with its blank
    assert "He ____" in texts  # sentence: the printed answer line


def test_r22_5_3_4_read_answers_schema_per_form() -> None:
    content = _form_content()
    qs = [q for s in content.sections for g in s.groups for q in g.questions]
    schema = read_answers_schema(qs).model_json_schema()
    assert schema["$defs"]["Reading_0"]["properties"]["value"]["anyOf"][0]["enum"] == list("ABCD")


def test_r22_5_3_4_eval_reports_form_accuracy() -> None:
    exp = [
        SimpleSection.flat(
            "I",
            [
                SimpleQuestion(printed_number=1, answer_form="choice"),
                SimpleQuestion(printed_number=2, answer_form="word"),
            ],
        )
    ]
    got = [
        SimpleSection.flat(
            "I",
            [
                SimpleQuestion(printed_number=1, answer_form="choice"),
                SimpleQuestion(printed_number=2, answer_form="sentence"),
            ],
        )
    ]
    s = structure_counts(exp, got)
    assert (s.types.hits, s.types.total) == (1, 2)
    assert s.form_confusion == {"choice→choice": 1, "word→sentence": 1}
    assert s.form_accuracy == 0.5


# --- R22.5.3.8: True/False options relabelled T/F (checklist (d)) ---------------------------------


def _tf_content() -> dict[str, Any]:
    """Old-shape content: q-1 a True/False the model lettered reversed (``A. FALSE``,
    ``B. TRUE``, as G1 Test G), q-2 an ordinary two-option choice."""
    content = _old_content()
    groups = content["sections"][0]["groups"][:2]
    groups[0]["questions"][0].update(
        type="true_false",
        options=[{"label": "A", "text": "FALSE"}, {"label": "B", "text": "TRUE"}],
    )
    groups[1]["questions"][0].update(
        type="mcq", options=[{"label": "A", "text": "yes"}, {"label": "B", "text": "no"}]
    )
    content["sections"][0]["groups"] = groups
    return content


def _seed_tf(path: Path) -> tuple[str, str]:
    c = db.open_database(path)
    test = make_test(c)
    attempt = make_attempt(c, test.id)
    attempts.insert_answers(
        c,
        [
            answer(
                attempt.id, "q-1", value="A", value_norm="a", alt_value="B", verdict="incorrect"
            ),
            answer(attempt.id, "q-2", value="A", value_norm="a", verdict="correct"),
        ],
    )
    keys.upsert_key(c, g_key("q-1", ["B", "b"]).model_copy(update={"test_id": test.id}))
    keys.upsert_key(c, g_key("q-2", "A").model_copy(update={"test_id": test.id}))
    c.execute(
        "INSERT INTO explanations (test_id, question_id, wrong_answer_norm, error_type, text_vi,"
        " status, llm_call_id) VALUES (?, 'q-1', 'a', 'gap', 'Giải thích.', 'ai', NULL)",
        (test.id,),
    )
    c.execute("UPDATE tests SET content = ? WHERE id = ?", (json.dumps(_tf_content()), test.id))
    c.execute("INSERT INTO answer_form_pending (id) VALUES (1)")
    c.commit()
    c.close()
    return test.id, attempt.id


def test_r22_5_3_8_pass_relabels_true_false_key_and_student_answers(tmp_path: Path) -> None:
    path = tmp_path / "data" / "app.db"
    test_id, attempt_id = _seed_tf(path)
    c = db.open_database(path)  # the first start runs the pass
    t = tests.get_test(c, test_id)
    assert t is not None
    got = {q.id: q for g in t.content.sections[0].groups for q in g.questions}
    tf, other = got["q-1"], got["q-2"]
    assert [(o.label, o.text) for o in tf.options or []] == [("T", "True"), ("F", "False")]
    assert tf.old_type == "true_false"
    assert [(o.label, o.text) for o in tf.old_options or []] == [("A", "FALSE"), ("B", "TRUE")]
    assert [o.label for o in other.options or []] == ["A", "B"]
    assert other.old_options is None
    k = keys.get_key(c, test_id, "q-1")
    assert k is not None and k.accepted == ["T"]
    k2 = keys.get_key(c, test_id, "q-2")
    assert k2 is not None and k2.accepted == ["A"]
    rows = {
        r[0]: tuple(r[1:])
        for r in c.execute(
            "SELECT question_id, value, value_norm, alt_value, verdict FROM answers"
            " WHERE attempt_id = ?",
            (attempt_id,),
        )
    }
    assert rows["q-1"] == ("F", "f", "T", "incorrect")  # verdict untouched
    assert rows["q-2"] == ("A", "a", None, "correct")
    wrong = c.execute("SELECT wrong_answer_norm FROM explanations WHERE question_id = 'q-1'")
    assert [r[0] for r in wrong] == ["f"]
    # guarded: a second start changes nothing
    after = c.execute("SELECT content FROM tests WHERE id = ?", (test_id,)).fetchone()[0]
    assert run_answer_form_pass(c) is False
    c.close()
    c = db.open_database(path)
    assert c.execute("SELECT content FROM tests WHERE id = ?", (test_id,)).fetchone()[0] == after
    k = keys.get_key(c, test_id, "q-1")
    assert k is not None and k.accepted == ["T"]
    c.close()


def test_r22_5_3_8_revert_gives_the_old_labels_back() -> None:
    old = _tf_content()
    upgraded = upgrade_content_data(old)
    q1 = upgraded["sections"][0]["groups"][0]["questions"][0]
    assert q1["options"] == [{"label": "T", "text": "True"}, {"label": "F", "text": "False"}]
    reverted = revert_content_data(upgraded)
    qs = [q for g in reverted["sections"][0]["groups"] for q in g["questions"]]
    olds = [q for g in old["sections"][0]["groups"] for q in g["questions"]]
    for a, b in zip(qs, olds, strict=True):
        assert {k: a.get(k) for k in b} == b
        assert "old_options" not in a
    assert upgrade_content_data(upgraded) == upgraded  # already relabelled: left as it is


def test_r22_5_3_8_reading_offers_t_f_for_relabelled_question() -> None:
    upgraded = m.TestContent.model_validate(upgrade_content_data(_tf_content()))
    qs = [q for s in upgraded.sections for g in s.groups for q in g.questions]
    schema = read_answers_schema(qs).model_json_schema()
    assert schema["$defs"]["Reading_0"]["properties"]["value"]["anyOf"][0]["enum"] == ["T", "F"]
    assert schema["$defs"]["Reading_1"]["properties"]["value"]["anyOf"][0]["enum"] == ["A", "B"]


def _seed_tf_review(path: Path) -> tuple[str, dict[str, str], dict[str, str]]:
    """The verifier's case: q-1 lettered ``A. FALSE`` / ``B. TRUE``, the student wrote B (= TRUE),
    the key is B. Attempt 1 has an unsure reading (open ``uncertain_answer``), attempt 2 a box and
    an inline reading that disagree (open ``box_inline_conflict``), attempt 3 a resolved item
    (history), and the key an open ``uncertain_key``."""
    c = db.open_database(path)
    test = make_test(c)
    atts = [make_attempt(c, test.id) for _ in range(3)]
    for att in atts:
        attempts.insert_answers(
            c,
            [
                answer(
                    att.id, "q-1", value="B", value_norm="b", alt_value="A", reading_unsure=True
                ),
                answer(att.id, "q-2", value="A", value_norm="a"),
            ],
        )
    keys.upsert_key(c, g_key("q-1", "B").model_copy(update={"test_id": test.id}))
    keys.upsert_key(c, g_key("q-2", "A").model_copy(update={"test_id": test.id}))
    items: dict[str, str] = {}
    for name, kind, att, proposal in (
        ("unsure", "uncertain_answer", atts[0], {"value": " b ", "alt_value": "A", "page_no": 1}),
        ("conflict", "box_inline_conflict", atts[1], {"box_value": "B", "inline_value": "a"}),
        ("history", "uncertain_answer", atts[2], {"value": "B", "alt_value": "A"}),
        ("key", "uncertain_key", None, {"accepted": ["B", "b"]}),
        ("other", "uncertain_answer", atts[0], {"value": "B", "alt_value": None}),
    ):
        item, _ = review_repo.upsert_item(
            c,
            kind=kind,  # type: ignore[arg-type]
            owner="extract",
            dedupe_key=f"{kind}:{name}",
            proposal=proposal,
            test_id=test.id,
            attempt_id=att.id if att else None,
            question_id="q-2" if name == "other" else "q-1",
        )
        items[name] = item.id
    review_repo.resolve_item(c, items["history"], "skipped", {"action": "skip", "value": None})
    c.execute("UPDATE tests SET content = ? WHERE id = ?", (json.dumps(_tf_content()), test.id))
    c.execute("INSERT INTO answer_form_pending (id) VALUES (1)")
    c.commit()
    c.close()
    return test.id, items, {"unsure": atts[0].id, "conflict": atts[1].id}


def _proposal(c: sqlite3.Connection, item_id: str) -> dict[str, Any]:
    item = review_repo.get_item(c, item_id)
    assert item is not None
    return item.proposal


def test_r22_5_3_8_pass_relabels_open_review_items(tmp_path: Path) -> None:
    path = tmp_path / "data" / "app.db"
    test_id, items, att = _seed_tf_review(path)
    c = db.open_database(path)  # the first start runs the pass
    assert _proposal(c, items["unsure"]) == {"value": "T", "alt_value": "F", "page_no": 1}
    assert _proposal(c, items["conflict"]) == {"box_value": "T", "inline_value": "F"}
    assert _proposal(c, items["key"]) == {"accepted": ["T"]}
    assert _proposal(c, items["history"]) == {"value": "B", "alt_value": "A"}  # resolved: kept
    assert _proposal(c, items["other"]) == {"value": "B", "alt_value": None}  # not relabelled
    t = tests.get_test(c, test_id)
    assert t is not None
    q1 = next(q for g in t.content.sections[0].groups for q in g.questions if q.id == "q-1")
    key = keys.get_key(c, test_id, "q-1")
    assert key is not None and key.accepted == ["T"]
    # Accept stores the relabelled letter, and the re-grade marks the student answer correct
    for name in ("unsure", "conflict"):
        resolve(c, items[name], "accept")
        got = attempts.get_answer(c, att[name], "q-1")
        assert got is not None
        assert (got.teacher_override, got.value_norm) == ("T", "t")
        assert scoring.grade_answer(q1, got, key).verdict == "correct"
    c.close()


def _swapped_content() -> dict[str, Any]:
    """q-1 stored with swapped labels: ``T. False``, ``F. True``."""
    content = _tf_content()
    content["sections"][0]["groups"][0]["questions"][0]["options"] = [
        {"label": "T", "text": "False"},
        {"label": "F", "text": "True"},
    ]
    return content


def test_r22_5_3_8_swapped_labels_relabel_without_a_collision(tmp_path: Path) -> None:
    path = tmp_path / "data" / "app.db"
    c = db.open_database(path)
    test = make_test(c)
    attempt = make_attempt(c, test.id)
    attempts.insert_answers(
        c,
        [answer(attempt.id, "q-1", value="T", value_norm="t", alt_value="F", teacher_override="f")],
    )
    keys.upsert_key(c, g_key("q-1", ["T", "F"]).model_copy(update={"test_id": test.id}))
    for wrong, text in (("t", "Sai vì False."), ("f", "Sai vì True.")):
        c.execute(
            "INSERT INTO explanations (test_id, question_id, wrong_answer_norm, error_type,"
            " text_vi, status, llm_call_id) VALUES (?, 'q-1', ?, 'gap', ?, 'ai', NULL)",
            (test.id, wrong, text),
        )
    c.execute(
        "UPDATE tests SET content = ? WHERE id = ?", (json.dumps(_swapped_content()), test.id)
    )
    c.execute("INSERT INTO answer_form_pending (id) VALUES (1)")
    c.commit()
    c.close()
    c = db.open_database(path)  # the first start runs the pass and does not abort
    assert c.execute("SELECT COUNT(*) FROM answer_form_pending").fetchone()[0] == 0
    key = keys.get_key(c, test.id, "q-1")
    assert key is not None and key.accepted == ["F", "T"]
    row = c.execute(
        "SELECT value, value_norm, alt_value, teacher_override FROM answers"
        " WHERE question_id = 'q-1'"
    ).fetchone()
    assert tuple(row) == ("F", "f", "T", "T")
    expl = dict(
        c.execute(
            "SELECT wrong_answer_norm, text_vi FROM explanations WHERE question_id = 'q-1'"
        ).fetchall()
    )
    assert expl == {"f": "Sai vì False.", "t": "Sai vì True."}
    c.close()
