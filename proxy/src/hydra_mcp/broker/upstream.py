"""Minimal MCP client for upstream servers over Streamable HTTP (protocol 2025-11-25).

Written against the wire protocol rather than an SDK because the proxy needs exact control of
ids, headers and sessions. One upstream session per account, created lazily:

    POST initialize                 -> result + Mcp-Session-Id
    POST notifications/initialized  -> 202
    POST <request>                  -> application/json, or text/event-stream carrying the
                                       response (and possibly notifications before it)

Not supported yet: server-to-client requests during a call (sampling, elicitation) and the
standalone GET notification stream. Both are listed in the design doc's session section.
"""

from __future__ import annotations

import itertools
import json
import logging
from dataclasses import dataclass, field

import httpx

from hydra_mcp import __version__

log = logging.getLogger(__name__)

PROTOCOL_VERSION = "2025-11-25"


class UpstreamError(RuntimeError):
    pass


class UpstreamAuthError(UpstreamError):
    """401/403 from the upstream: the stored token is no longer accepted."""


@dataclass
class _Session:
    session_id: str | None
    protocol_version: str
    server_info: dict = field(default_factory=dict)


class UpstreamClient:
    def __init__(self, http: httpx.AsyncClient):
        self.http = http
        self._sessions: dict[str, _Session] = {}
        self._ids = itertools.count(1)

    def forget(self, key: str) -> None:
        self._sessions.pop(key, None)

    async def request(
        self, key: str, url: str, token: str, method: str, params: dict | None = None
    ) -> dict:
        """Send one JSON-RPC request for account `key`, (re)initializing the session if needed."""
        for attempt in (1, 2):
            session = self._sessions.get(key) or await self._initialize(key, url, token)
            try:
                return await self._rpc(url, token, session, method, params)
            except _SessionExpired:
                self.forget(key)
                if attempt == 2:
                    raise UpstreamError("upstream session expired twice in a row") from None
        raise AssertionError("unreachable")

    async def _initialize(self, key: str, url: str, token: str) -> _Session:
        bootstrap = _Session(session_id=None, protocol_version=PROTOCOL_VERSION)
        result, headers = await self._post(
            url,
            token,
            bootstrap,
            {
                "jsonrpc": "2.0",
                "id": next(self._ids),
                "method": "initialize",
                "params": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "hydra-mcp", "version": __version__},
                },
            },
        )
        session = _Session(
            session_id=headers.get("mcp-session-id"),
            protocol_version=result.get("protocolVersion", PROTOCOL_VERSION),
            server_info=result.get("serverInfo", {}),
        )
        await self._post(
            url, token, session, {"jsonrpc": "2.0", "method": "notifications/initialized"}
        )
        self._sessions[key] = session
        return session

    async def _rpc(
        self, url: str, token: str, session: _Session, method: str, params: dict | None
    ) -> dict:
        msg: dict = {"jsonrpc": "2.0", "id": next(self._ids), "method": method}
        if params is not None:
            msg["params"] = params
        result, _ = await self._post(url, token, session, msg)
        return result

    async def _post(
        self, url: str, token: str, session: _Session, msg: dict
    ) -> tuple[dict, httpx.Headers]:
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": session.protocol_version,
        }
        if session.session_id:
            headers["Mcp-Session-Id"] = session.session_id
        is_request = "id" in msg
        async with self.http.stream("POST", url, json=msg, headers=headers) as resp:
            if resp.status_code in (401, 403):
                raise UpstreamAuthError(f"upstream rejected the token ({resp.status_code})")
            if resp.status_code == 404 and session.session_id:
                raise _SessionExpired()
            if not is_request:
                if resp.status_code >= 400:
                    raise UpstreamError(f"upstream answered {resp.status_code} to a notification")
                return {}, resp.headers
            if resp.status_code >= 400:
                body = (await resp.aread()).decode(errors="replace")[:300]
                raise UpstreamError(f"upstream answered {resp.status_code}: {body}")
            ctype = resp.headers.get("content-type", "")
            if ctype.startswith("text/event-stream"):
                reply = await _read_sse_response(resp, msg["id"])
            else:
                reply = json.loads(await resp.aread())
            if "error" in reply:
                err = reply["error"]
                raise UpstreamError(f"upstream error {err.get('code')}: {err.get('message')}")
            return reply.get("result", {}), resp.headers


class _SessionExpired(Exception):
    pass


async def _read_sse_response(resp: httpx.Response, request_id: int) -> dict:
    """Read SSE events until the JSON-RPC response for request_id arrives."""
    data_lines: list[str] = []
    async for line in resp.aiter_lines():
        if line == "":
            if data_lines:
                payload = "\n".join(data_lines)
                data_lines = []
                try:
                    msg = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                if msg.get("id") == request_id and ("result" in msg or "error" in msg):
                    return msg
                # notifications and server requests are ignored in this version
            continue
        if line.startswith("data:"):
            data_lines.append(line[5:].lstrip(" "))
    if data_lines:
        msg = json.loads("\n".join(data_lines))
        if msg.get("id") == request_id:
            return msg
    raise UpstreamError("upstream closed the stream without a response")
