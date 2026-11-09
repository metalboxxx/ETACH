"""Route modules (llm-design §2 route inventory).

To add routes, create ``etach/api/routes/<name>.py`` with a module-level ``router = APIRouter()``;
:func:`etach.api.app.create_app` includes every such module (sorted by name) and applies the auth
dependency. Use ``etach.api.deps.ConnDep`` / ``CtxDep`` / ``FilesDep``, mark ``GET /files/{id}``
with ``etach.api.auth.allow_query_token`` (below the router decorator), publish non-run events with
``etach.api.sse.publish(ctx.events, "review.changed", ...)`` and ``await ctx.manager.poke()`` after
committing a transaction that queued runs. ``GET /events`` lives in :mod:`etach.api.sse`.
"""
