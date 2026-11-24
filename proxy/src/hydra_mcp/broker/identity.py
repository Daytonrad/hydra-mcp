"""Learn who (or what) a fresh token belongs to, when the token response does not say.

Google returns an id_token with the email. Atlassian returns neither an id_token nor a
user-readable identity: what tells two Atlassian accounts apart is the *site* the login was
granted on (acme.atlassian.net vs globex.atlassian.net), and the only reliable way to
read it with an MCP-audience token is the upstream's own tool. So the probe is an MCP call,
per upstream host, kept here as data.

The identity is a label and a de-duplication key (same site again = reconnect, not a second
account). It is never used to authorize anything.
"""

from __future__ import annotations

import json
import logging
import secrets
from collections.abc import Callable
from urllib.parse import urlsplit

from hydra_mcp.broker.upstream import UpstreamClient, UpstreamError
from hydra_mcp.models import Upstream

log = logging.getLogger(__name__)


def _atlassian_sites(result: dict) -> str:
    """getAccessibleAtlassianResources -> 'site-a.atlassian.net' (or several, comma-joined)."""
    for item in result.get("content") or []:
        if item.get("type") != "text":
            continue
        try:
            data = json.loads(item["text"])
        except (ValueError, KeyError):
            continue
        payload = data.get("data", data) if isinstance(data, dict) else {}
        resources = payload.get("resources", payload) if isinstance(payload, dict) else payload
        if not isinstance(resources, list):
            continue
        hosts = [urlsplit(r.get("url", "")).hostname for r in resources if isinstance(r, dict)]
        return ", ".join(sorted(h for h in hosts if h))
    return ""


def _text_json(result: dict) -> dict:
    for item in result.get("content") or []:
        if item.get("type") == "text":
            try:
                data = json.loads(item["text"])
            except (ValueError, KeyError):
                continue
            if isinstance(data, dict):
                return data
    return result.get("structuredContent") or {}


def _github_login(result: dict) -> str:
    """get_me -> 'octocat' (the GitHub login)."""
    data = _text_json(result)
    data = data.get("user", data) if isinstance(data.get("user"), dict) else data
    return str(data.get("login") or "")


# host of the MCP URL -> (tool to call, how to read its result)
PROBES: dict[str, tuple[str, Callable[[dict], str]]] = {
    "mcp.atlassian.com": ("getAccessibleAtlassianResources", _atlassian_sites),
    "api.githubcopilot.com": ("get_me", _github_login),
}


class IdentityProbe:
    def __init__(self, upstream: UpstreamClient):
        self.upstream = upstream

    def supports(self, upstream: Upstream) -> bool:
        return (urlsplit(str(upstream.url)).hostname or "") in PROBES

    async def __call__(self, upstream: Upstream, access_token: str) -> str:
        probe = PROBES.get(urlsplit(str(upstream.url)).hostname or "")
        if probe is None:
            return ""
        tool, read = probe
        key = f"identity-probe:{secrets.token_hex(4)}"  # throwaway upstream session
        try:
            result = await self.upstream.request(
                key, str(upstream.url), access_token, "tools/call", {"name": tool, "arguments": {}}
            )
            return read(result)
        except (UpstreamError, ValueError, KeyError) as exc:
            log.warning("identity probe on %s failed: %s", upstream.id, exc)
            return ""
        finally:
            self.upstream.forget(key)

    async def verify(self, upstream: Upstream, access_token: str) -> str:
        """Check a pasted token against the upstream (initialize + tools/list), then name it.

        Raises UpstreamAuthError when the upstream refuses the token, UpstreamError otherwise.
        """
        key = f"token-check:{secrets.token_hex(4)}"
        try:
            await self.upstream.request(key, str(upstream.url), access_token, "tools/list", {})
        finally:
            self.upstream.forget(key)
        return await self(upstream, access_token)
