"""Step 22.5.6 (sidecar) R22.5.6.6: the listening part left out is stored and on the attempt read.

The extraction records each left-out section's ``kind`` (``listening`` / ``writing``) with its
printed numbers in ``meta.omitted_sections``; ``GET /attempts/{id}`` carries
``listening_skipped: {first, last} | null``. A section stored before step 22.5.6 has no kind:
it counts as listening when none of its printed numbers is a stored question.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from unit.api.test_routes_b import _attempt, _conn, _test
from unit.api.test_routes_c import client

from etach.api.deps import AppContext
from etach.domain import models as m
from etach.domain.llm_schemas import TranscribeOut
from etach.domain.models import OmittedSection, listening_range
from etach.domain.renumber import merge_pages, page_transcript
from etach.store.repos import tests


@pytest.fixture
def ctx(make_ctx: Callable[..., AppContext]) -> AppContext:
    return make_ctx()


def _set_omitted(ctx: AppContext, omitted: list[OmittedSection]) -> str:
    conn = _conn(ctx)
    try:
        test_id = _test(conn)
        test = tests.get_test(conn, test_id)
        assert test is not None
        meta = test.meta.model_copy(update={"omitted_sections": omitted})
        conn.execute("UPDATE tests SET meta = ? WHERE id = ?", (meta.model_dump_json(), test_id))
        return _attempt(conn, test_id, graded=False).id
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_r22_5_6_6_attempt_read_carries_the_listening_range(ctx: AppContext) -> None:
    att = _set_omitted(
        ctx,
        [
            OmittedSection(title="I", questions=[1, 2, 3, 4, 5], points=1.0, kind="listening"),
            OmittedSection(title="IX", questions=[41], points=1.0, kind="writing"),
        ],
    )
    async with client(ctx) as c:
        r = await c.get(f"/attempts/{att}")
    assert r.status_code == 200, r.text
    assert r.json()["listening_skipped"] == {"first": 1, "last": 5}


@pytest.mark.asyncio
async def test_r22_5_6_6_no_listening_reads_null(ctx: AppContext) -> None:
    att = _set_omitted(ctx, [])
    async with client(ctx) as c:
        r = await c.get(f"/attempts/{att}")
    assert r.status_code == 200, r.text
    assert r.json()["listening_skipped"] is None


def _content(printed: list[int]) -> m.TestContent:
    qs = [
        m.Question(
            id=f"q{p}",
            number=i,
            printed_number=p,
            page_no=1,
            answer_form="writing",
            stem="Write.",
            options=None,
            cue=None,
            points=1.0,
        )
        for i, p in enumerate(printed, 1)
    ]
    return m.TestContent(
        sections=[
            m.Section(
                id="s1",
                number=1,
                printed_title="IX",
                title="IX",
                instructions="",
                points=1.0,
                points_source="equal",
                skill="writing",
                graded=False,
                groups=[m.QuestionGroup(id="g1", stimulus=None, pictures=[], questions=qs)],
            )
        ]
    )


def test_r22_5_6_6_sections_stored_before_have_no_kind() -> None:
    meta = m.TestMetadata(
        occasion="FinalTerm",
        grade=8,
        omitted_sections=[
            OmittedSection(title="I", questions=[1, 2, 3, 4], points=1.0),  # not stored
            OmittedSection(title="IX", questions=[41], points=1.0),  # stored: writing
        ],
    )
    assert listening_range(meta, _content([41])) == (1, 4)
    meta.omitted_sections.pop(0)
    assert listening_range(meta, _content([41])) is None


def test_r22_5_6_6_extraction_records_the_listening_kind() -> None:
    page = TranscribeOut.model_validate(
        {
            "header_text": None,
            "sections": [
                {
                    "printed_title": "I",
                    "instructions": "Listen and choose.",
                    "points_text": "(1 pt)",
                    "kind": "listening",
                    "skill": "grammar",
                    "range_first": 1,
                    "range_last": 4,
                    "groups": [],
                },
            ],
        }
    )
    draft = merge_pages(
        [page_transcript(1, page, "call-1")],
        page_files={1: "f1"},
        meta=m.TestMetadata(occasion="FinalTerm", grade=8),
    ).draft
    assert [(o.kind, o.questions) for o in draft.meta.omitted_sections] == [
        ("listening", [1, 2, 3, 4])
    ]
