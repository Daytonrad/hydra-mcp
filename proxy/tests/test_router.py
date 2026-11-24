from hydra_mcp.router.discovery import parse_www_authenticate
from tests.conftest import GOOD_TOKEN

INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}


async def test_unauthenticated_call_points_client_at_proxy_prm(proxy):
    r = await proxy.post("/a/gmail-work/mcp", json=INIT)
    assert r.status_code == 401
    (ch,) = parse_www_authenticate(r.headers["www-authenticate"])
    assert ch.scheme == "Bearer"
    assert ch.params["resource_metadata"] == (
        "http://proxy.test/.well-known/oauth-protected-resource/a/gmail-work/mcp"
    )
    assert ch.params["scope"] == "mail.read"  # other params survive


async def test_prm_is_rewritten_to_the_account_resource(proxy):
    await proxy.post("/a/gmail-work/mcp", json=INIT)  # learn the upstream's hint
    r = await proxy.get("/.well-known/oauth-protected-resource/a/gmail-work/mcp")
    assert r.status_code == 200
    doc = r.json()
    assert doc["resource"] == "http://proxy.test/a/gmail-work/mcp"
    assert doc["authorization_servers"] == ["https://as.upstream.test"]  # login stays upstream


async def test_prm_found_without_hint_via_well_known_fallback(proxy):
    r = await proxy.get("/.well-known/oauth-protected-resource/a/gmail-work/mcp")
    assert r.json()["authorization_servers"] == ["https://as.upstream.test"]


async def test_token_and_session_pass_through_untouched(proxy):
    r = await proxy.post(
        "/a/gmail-work/mcp", json=INIT, headers={"Authorization": f"Bearer {GOOD_TOKEN}"}
    )
    assert r.status_code == 200
    assert r.json()["result"] == {"echo": "initialize"}
    assert r.headers["mcp-session-id"] == "s-1"


async def test_sse_is_streamed(proxy):
    r = await proxy.post(
        "/a/gmail-work/mcp",
        json={"jsonrpc": "2.0", "id": 2, "method": "stream"},
        headers={"Authorization": f"Bearer {GOOD_TOKEN}"},
    )
    assert r.headers["content-type"].startswith("text/event-stream")
    assert r.text.count("event: message") == 3


async def test_unknown_and_disabled_accounts_are_404(proxy):
    assert (await proxy.post("/a/nope/mcp", json=INIT)).status_code == 404
    assert (await proxy.post("/a/gmail-off/mcp", json=INIT)).status_code == 404
