"""Phase-0 live checks (plan step 5, items 1-6; llm-design §9 Q1, Q2; PRD R4).

Every call goes through the step 4 ``OllamaClient.call`` (both adapters) against our own
``ollama serve`` (see ``conftest.py``). Inputs are the synthetic page of ``phase0.py``, never
student photos. Each test appends a record to ``_out/phase0-results.json``; run with ``-s`` to
also see them on screen. Items 1 and 3 record cassettes when ``ETACH_PHASE0_RECORD=1``; their task
names end in ``_image`` or ``_text`` (or ``_think``), which tells the input.

What fails a test: a call that cannot run, missing logprobs (item 1), an answer value that cannot
be found in the logprob tokens (item 3), no valid output from either NuExtract3 variant (item 2),
no load/speed data (items 4, 6). Everything else is a measurement for
``docs/initial-plan/phases-testing/phase0-report.md``.
Item 5 records an error (for example flash attention failing on Turing) as its finding instead
of failing.
"""

from __future__ import annotations

from typing import Any

import pytest
from live.phase0 import (
    EXPECTED,
    FA_Q8_ENV,
    PAGE_TEXT,
    Client,
    MakeClient,
    Phase0Answers,
    Phase0Transcript,
    PrivateOllama,
    RequireRole,
    Results,
    Workspace,
    logprob_presence,
    nvidia_smi,
    timing,
    value_tokens,
    vram,
)
from pydantic import BaseModel

from etach.llm.client import CallFailure, CallResult, OllamaError, StreamDropped
from etach.llm.config import ModelsConfig

pytestmark = pytest.mark.live

THINK_NUM_PREDICT = 1500  # as verify_key (llm-design §3.1)


def check_answers(parsed: BaseModel | None) -> dict[str, bool] | None:
    if not isinstance(parsed, Phase0Answers):
        return None
    got = parsed.model_dump()
    return {
        key: isinstance(got[key], str) and got[key].strip().casefold() == value.casefold()
        for key, value in EXPECTED.items()
    }


async def run_call(
    c: Client,
    ws: Workspace,
    role: str,
    task: str,
    schema: type[BaseModel],
    *,
    image: bool,
    think: bool | None = None,
    num_predict: int | None = None,
) -> dict[str, Any]:
    """One ``client.call``; returns the outcome with the last ``llm_calls`` row's logprobs."""
    before = len(ws.rows())
    finals_before = len(c.backend.finals)
    inputs: dict[str, Any] = {"page_no": 1}
    if not image:
        inputs["document"] = PAGE_TEXT
    result = await c.client.call(
        role,  # type: ignore[arg-type]
        task,
        inputs,
        schema,
        step_id=ws.step_id,
        images=[ws.page_id] if image else [],
        think=think,
        num_predict=num_predict,
    )
    rows = ws.rows()[before:]
    last = rows[-1]
    final = c.backend.finals[-1] if len(c.backend.finals) > finals_before else None
    parsed = result.parsed if isinstance(result, CallResult) else None
    joined = "".join(str(e.get("token", "")) for e in last.logprobs or [] if isinstance(e, dict))
    return {
        "task": task,
        "model": c.config.role(role).model,
        "input": "image" if image else "text",
        "request_has_format": "format" in last.request,
        "think": last.request.get("think"),
        "statuses": [r.status for r in rows],
        "valid": isinstance(result, CallResult),
        "failure": result.reason[:500] if isinstance(result, CallFailure) else None,
        "parsed": parsed.model_dump() if parsed is not None else None,
        "answers_correct": check_answers(parsed),
        "response_text": last.response_text[:800],
        "thinking_chars": len(last.thinking_text),
        "logprob_text_chars": len(joined),
        "logprobs_cover": (
            "thinking+response"
            if last.thinking_text and joined == last.thinking_text + last.response_text
            else "response"
            if joined == last.response_text
            else "other"
        ),
        "logprobs": logprob_presence(last.logprobs, final),
        "timing": timing(final),
        "_logprobs_raw": last.logprobs,
    }


def public(outcome: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in outcome.items() if not k.startswith("_")}


# --- item 1: logprobs with format, with an image, with both --------------------------------

ITEM1_CASES = [
    # (id, role, also_format, input, think)
    ("vision-template-text", "vision", False, "text", None),
    ("vision-template-image", "vision", False, "image", None),
    ("vision-template+format-text", "vision", True, "text", None),
    ("vision-template+format-image", "vision", True, "image", None),
    ("reasoning-format-text", "reasoning", False, "text", None),
    ("reasoning-format-image", "reasoning", False, "image", None),
    ("reasoning-format-text-think", "reasoning", False, "text", True),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("role", "also_format", "input_kind", "think"),
    [pytest.param(*case[1:], id=case[0]) for case in ITEM1_CASES],
)
async def test_item1_logprobs(
    role: str,
    also_format: bool,
    input_kind: str,
    think: bool | None,
    server: PrivateOllama,
    require_role: RequireRole,
    make_client: MakeClient,
    workspace: Workspace,
    results: Results,
) -> None:
    model = require_role(role)
    image = input_kind == "image"
    if image and role == "reasoning" and "vision" not in server.capabilities(model):
        results.add(1, f"{role}-format-image", role=role, skipped="the model has no vision")
        pytest.skip(f"{model} has no vision capability (/api/show)")
    c = make_client(also_format=also_format, record=True)
    shape = (
        "template+format"
        if role == "vision" and also_format
        else ("template" if role == "vision" else "format")
    )
    suffix = "think" if think else input_kind
    task = f"phase0_logprobs_{role}_{shape.replace('+', '_')}_{suffix}"
    outcome = await run_call(
        c,
        workspace,
        role,
        task,
        Phase0Answers,
        image=image,
        think=think,
        num_predict=THINK_NUM_PREDICT if think else None,
    )
    presence = outcome["logprobs"]
    results.add(1, f"{role}-{shape}-{suffix}", role=role, shape=shape, **public(outcome))
    assert presence["count"] > 0, f"no logprobs: {presence['missing']}"
    assert presence["with_top_logprobs"] == presence["count"], presence["missing"]


# --- item 2: NuExtract3 template alone vs template + format -------------------------------


@pytest.mark.asyncio
async def test_item2_nuextract_template_vs_format(
    require_role: RequireRole,
    make_client: MakeClient,
    workspace: Workspace,
    results: Results,
) -> None:
    require_role("vision")
    valid = []
    for also_format in (False, True):
        shape = "template+format" if also_format else "template"
        c = make_client(also_format=also_format)
        outcome = await run_call(
            c,
            workspace,
            "vision",
            f"phase0_nuextract_{shape.replace('+', '_')}_image",
            Phase0Answers,
            image=True,
        )
        results.add(2, shape, role="vision", shape=shape, **public(outcome))
        valid.append(outcome["valid"])
    assert any(valid), "neither template alone nor template + format gave valid output"


# --- item 3: the MCQ letter is a single token ----------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["vision", "reasoning"])
async def test_item3_mcq_letter_token(
    role: str,
    server: PrivateOllama,
    require_role: RequireRole,
    make_client: MakeClient,
    workspace: Workspace,
    results: Results,
) -> None:
    model = require_role(role)
    image = role == "vision" or "vision" in server.capabilities(model)
    c = make_client(record=True)
    shape = "template" if role == "vision" else "format"
    input_kind = "image" if image else "text"
    outcome = await run_call(
        c,
        workspace,
        role,
        f"phase0_letter_{role}_{shape}_{input_kind}",
        Phase0Answers,
        image=image,
    )
    letter = value_tokens(outcome["_logprobs_raw"], outcome["response_text"], "q1")
    results.add(3, f"{role}-{shape}-{input_kind}", role=role, q1_tokens=letter, **public(outcome))
    assert outcome["logprobs"]["count"] > 0, "no logprobs"
    assert letter["found"], letter.get("note")
    assert letter["tokens"], "no token covers the answer letter"


# --- item 4: VRAM and speed per role model at num_ctx 16384 --------------------------------


async def measure_speed(
    c: Client, ws: Workspace, server: PrivateOllama, role: str, label: str
) -> dict[str, Any]:
    """Cold load (everything unloaded first), one transcription call, then VRAM."""
    model = c.config.role(role).model
    image = role == "vision" or "vision" in server.capabilities(model)
    server.unload_all()
    gpu_idle = nvidia_smi()
    outcome = await run_call(
        c, ws, role, f"phase0_speed_{label}_{role}", Phase0Transcript, image=image
    )
    return {
        "role": role,
        "num_ctx": c.config.role(role).options.get("num_ctx"),
        "gpu_idle": gpu_idle,
        "vram": vram(server, model),
        **{k: outcome[k] for k in ("model", "input", "statuses", "valid", "timing")},
        "lines": (outcome["parsed"] or {}).get("lines"),
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["vision", "reasoning"])
async def test_item4_vram_and_speed(
    role: str,
    server: PrivateOllama,
    require_role: RequireRole,
    make_client: MakeClient,
    workspace: Workspace,
    results: Results,
) -> None:
    require_role(role)
    data = await measure_speed(make_client(), workspace, server, role, "baseline")
    results.add(4, role, env="baseline", server_env=server.env, **data)
    assert data["vram"]["loaded"], "the model is not in /api/ps after the call"
    assert data["timing"].get("eval_tok_per_s"), "no eval speed in the final chunk"


# --- item 5: flash attention + q8_0 KV cache on Turing -------------------------------------


@pytest.mark.asyncio
async def test_item5_flash_attention_q8_kv(
    server: PrivateOllama,
    config: ModelsConfig,
    make_client: MakeClient,
    workspace: Workspace,
    results: Results,
) -> None:
    roles = [r for r in ("vision", "reasoning") if server.has_model(config.role(r).model)]
    if not roles:
        pytest.skip("no role model is pulled (see items 1-4 for the pull commands)")
    server.unload_all()  # the baseline server keeps no model in VRAM meanwhile
    baseline = {r["role"]: r for r in results.records(4)}
    with PrivateOllama("fa-q8", dict(FA_Q8_ENV)) as fa:
        for role in roles:
            c = make_client(on=fa)
            model = c.config.role(role).model
            image = role == "vision" or "vision" in fa.capabilities(model)
            try:
                data = await measure_speed(c, workspace, fa, role, "faq8")
                answers = await run_call(
                    c, workspace, role, f"phase0_faq8_answers_{role}", Phase0Answers, image=image
                )
                data["answers"] = {
                    k: answers[k] for k in ("valid", "parsed", "answers_correct", "statuses")
                }
                data["answers"]["logprobs_count"] = answers["logprobs"]["count"]
                error = None
            except (OllamaError, StreamDropped) as exc:
                data, error = {"role": role}, f"{type(exc).__name__}: {exc}"[:800]
            base = baseline.get(role)
            if base and error is None:
                data["vs_baseline"] = compare(base, data)
            data["server_log"] = fa.log_lines(r"flash|kv.?cache|cache.?type|type_k|type_v")
            results.add(
                5,
                role,
                env="flash_attention=1 kv_cache=q8_0",
                server_env=fa.env,
                error=error,
                **data,
            )


def compare(base: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    def delta(path: tuple[str, str]) -> dict[str, Any]:
        a, b = base.get(path[0], {}).get(path[1]), new.get(path[0], {}).get(path[1])
        numbers = isinstance(a, int | float) and isinstance(b, int | float)
        diff = round(b - a, 2) if numbers else None
        return {"baseline": a, "fa_q8": b, "diff": diff}

    return {
        "size_vram_mib": delta(("vram", "size_vram_mib")),
        "size_mib": delta(("vram", "size_mib")),
        "fully_on_gpu": {
            "baseline": base.get("vram", {}).get("fully_on_gpu"),
            "fa_q8": new.get("vram", {}).get("fully_on_gpu"),
        },
        "eval_tok_per_s": delta(("timing", "eval_tok_per_s")),
        "prompt_tok_per_s": delta(("timing", "prompt_tok_per_s")),
        "load_s": delta(("timing", "load_s")),
        "transcript_valid": {"baseline": base.get("valid"), "fa_q8": new.get("valid")},
        "same_lines": base.get("lines") == new.get("lines"),
    }


# --- item 6: swap time with OLLAMA_MAX_LOADED_MODELS=1 -------------------------------------


@pytest.mark.asyncio
async def test_item6_swap_time(
    server: PrivateOllama,
    require_role: RequireRole,
    make_client: MakeClient,
    workspace: Workspace,
    results: Results,
) -> None:
    require_role("vision")
    require_role("reasoning")
    assert server.env["OLLAMA_MAX_LOADED_MODELS"] == "1"
    server.unload_all()
    c = make_client()
    steps = []
    for n, role in enumerate(("vision", "reasoning", "vision"), start=1):
        # the reasoning role reads the page as text, as it does in the app
        outcome = await run_call(
            c, workspace, role, f"phase0_swap_{n}_{role}", Phase0Answers, image=role == "vision"
        )
        loaded = [m.get("name") for m in server.ps()]
        steps.append(
            {
                "n": n,
                "role": role,
                "model": outcome["model"],
                "valid": outcome["valid"],
                "load_s": outcome["timing"].get("load_s"),
                "wall_s": outcome["timing"].get("wall_s"),
                "loaded_after": loaded,
            }
        )
    results.add(6, "vision-reasoning-vision", server_env=server.env, steps=steps)
    for step in steps:
        assert step["load_s"] is not None, f"no load_duration for call {step['n']}"
        assert len(step["loaded_after"]) == 1, f"more than one model loaded: {step}"
