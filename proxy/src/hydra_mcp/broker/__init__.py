"""Broker mode: one aggregated `/mcp` endpoint for all accounts.

* `oauth.py`      the proxy as OAuth client of each upstream AS (discovery, DCR, PKCE, refresh)
* `upstream.py`   minimal Streamable HTTP MCP client toward upstreams
* `aggregator.py` `{upstream}__{tool}` tools with an injected `account` argument, per-client grants
* `endpoint.py`   the `/mcp` JSON-RPC endpoint, authenticated by per-client keys

Planned next: the proxy as OAuth AS toward clients (replacing static client keys), the
client-keyed vault, the 2026-07-28 stateless protocol, server-to-client requests.
"""
