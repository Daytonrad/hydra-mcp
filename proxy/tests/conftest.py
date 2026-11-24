"""Test fixtures: a fake upstream MCP server + AS metadata, and the proxy wired to it in-process."""

from __future__ import annotations

import json

import httpx
import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route

from hydra_mcp.app import create_app
from hydra_mcp.models import Account, Upstream
from hydra_mcp.settings import Settings
from hydra_mcp.store import Store

UPSTREAM = "https://upstream.test/mcp"
ADMIN = "test-admin-token"
GOOD_TOKEN = "upstream-token-for-work"


def fake_upstream() -> Starlette:
    async def mcp(request: Request) -> Response:
        if request.headers.get("authorization") != f"Bearer {GOOD_TOKEN}":
            return Response(
                status_code=401,
                headers={
                    "WWW-Authenticate": 'Bearer resource_metadata="https://upstream.test/'
                    '.well-known/oauth-protected-resource/mcp", scope="mail.read"'
                },
            )
        body = await request.json()
        if body.get("method") == "stream":

            async def events():
                for i in range(3):
                    yield f"event: message\ndata: {json.dumps({'i': i})}\n\n".encode()

            return StreamingResponse(
                events(), media_type="text/event-stream", headers={"Mcp-Session-Id": "s-1"}
            )
        return JSONResponse(
            {"jsonrpc": "2.0", "id": body.get("id"), "result": {"echo": body.get("method")}},
            headers={"Mcp-Session-Id": "s-1"},
        )

    async def prm(request: Request) -> Response:
        return JSONResponse(
            {
                "resource": UPSTREAM,
                "authorization_servers": ["https://as.upstream.test"],
                "scopes_supported": ["mail.read"],
            }
        )

    async def as_meta(request: Request) -> Response:
        return JSONResponse(
            {
                "issuer": "https://as.upstream.test",
                "authorization_endpoint": "https://as.upstream.test/authorize",
                "token_endpoint": "https://as.upstream.test/token",
                "code_challenge_methods_supported": ["S256"],
                "client_id_metadata_document_supported": True,
            }
        )

    return Starlette(
        routes=[
            Route("/mcp", mcp, methods=["GET", "POST", "DELETE"]),
            Route("/.well-known/oauth-protected-resource/mcp", prm),
            Route("/.well-known/oauth-authorization-server", as_meta),
        ]
    )


class _Router(httpx.AsyncBaseTransport):
    """Routes upstream.test and as.upstream.test to the fake upstream app."""

    def __init__(self):
        self.inner = httpx.ASGITransport(app=fake_upstream())

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return await self.inner.handle_async_request(request)


@pytest.fixture
async def proxy(tmp_path):
    settings = Settings(
        public_url="http://proxy.test", data_dir=tmp_path, admin_token=ADMIN, admin_dist=None
    )
    store = Store(":memory:")
    await store.open()
    await store.put_upstream(Upstream(id="gmail", name="Gmail", url=UPSTREAM))
    await store.put_account(Account(id="gmail-work", upstream_id="gmail", alias="work"))
    await store.put_account(
        Account(id="gmail-off", upstream_id="gmail", alias="off", enabled=False)
    )
    upstream_http = httpx.AsyncClient(transport=_Router())
    app = create_app(settings, store=store, http=upstream_http)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://proxy.test"
    ) as client:
        yield client
    await upstream_http.aclose()
    await store.close()
