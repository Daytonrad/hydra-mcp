from hydra_mcp.router.discovery import (
    parse_www_authenticate,
    prm_candidates,
    proxy_prm_url,
    rewrite_www_authenticate,
)


def test_parse_quoted_and_token_values():
    (ch,) = parse_www_authenticate(
        'Bearer realm="x, y", error=invalid_token, error_description="a \\"q\\""'
    )
    assert ch.params == {"realm": "x, y", "error": "invalid_token", "error_description": 'a "q"'}


def test_parse_several_schemes():
    chs = parse_www_authenticate('Basic realm="r", Bearer resource_metadata="https://x/y"')
    assert [c.scheme for c in chs] == ["Basic", "Bearer"]
    assert chs[1].params["resource_metadata"] == "https://x/y"


def test_rewrite_adds_resource_metadata_when_missing():
    out = rewrite_www_authenticate('Bearer error="insufficient_scope", scope="a b"', "https://p/m")
    (ch,) = parse_www_authenticate(out)
    assert ch.params == {
        "error": "insufficient_scope",
        "scope": "a b",
        "resource_metadata": "https://p/m",
    }


def test_prm_candidates_follow_spec_order():
    assert prm_candidates("https://h.example/public/mcp", "https://h.example/hint") == [
        "https://h.example/hint",
        "https://h.example/.well-known/oauth-protected-resource/public/mcp",
        "https://h.example/.well-known/oauth-protected-resource",
    ]


def test_proxy_prm_url():
    assert (
        proxy_prm_url("http://127.0.0.1:8765/a/gmail-work/mcp")
        == "http://127.0.0.1:8765/.well-known/oauth-protected-resource/a/gmail-work/mcp"
    )
