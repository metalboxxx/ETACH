"""Step 22.5.4a: the settings API reads and writes all four model roles (R22.5.4.1)."""

from __future__ import annotations

import tomllib

import pytest
from unit.api.test_routes_c import client
from unit.api.test_routes_c import ctx as ctx

from etach.api.deps import AppContext

ROLES = ("vision", "reasoning", "grading_check", "extraction_check")


@pytest.mark.asyncio
async def test_settings_round_trip_all_four_roles(ctx: AppContext) -> None:
    async with client(ctx) as c:
        got = (await c.get("/settings")).json()
        assert set(got["roles"]) == set(ROLES)
        assert got["roles"]["grading_check"]["model"] == "qwen3.5:4b"
        assert got["roles"]["extraction_check"]["model"] == "qwen3.5:4b"

        tags = {role: f"m{i}:1b" for i, role in enumerate(ROLES)}
        r = await c.put("/settings", json={"roles": {k: {"model": v} for k, v in tags.items()}})
        assert r.status_code == 200, r.text
        new = r.json()
        assert {k: v["model"] for k, v in new["roles"].items()} == tags
        assert (await c.get("/settings")).json() == new
        on_disk = tomllib.loads(ctx.paths.models_toml.read_text(encoding="utf-8"))
        assert {k: v["model"] for k, v in on_disk["roles"].items()} == tags
        assert ctx.client.config.role("grading_check").model == "m2:1b"
