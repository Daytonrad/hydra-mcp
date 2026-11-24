"""OAuth discovery plumbing for router mode.

Router mode keeps the client and the upstream authorization server talking directly. The proxy
only rewrites two things so that each account looks like its own protected resource:

1. the `resource_metadata` parameter of `WWW-Authenticate` on upstream 401/403 responses, and
2. the Protected Resource Metadata (RFC 9728) document, whose `resource` must equal the URL the
   client called (RFC 9728 section 3.3), i.e. the proxy's account URL.

`authorization_servers` is copied verbatim, so login and consent happen at the upstream AS.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit, urlunsplit

import httpx

WELL_KNOWN_PRM = "/.well-known/oauth-protected-resource"

# auth-param = token "=" ( token / quoted-string ), RFC 9110 section 11.2
_PARAM_RE = re.compile(r'\s*([!#$%&\'*+.^_`|~0-9A-Za-z-]+)\s*=\s*("(?:[^"\\]|\\.)*"|[^\s,]*)\s*,?')


@dataclass
class Challenge:
    scheme: str
    params: dict[str, str] = field(default_factory=dict)

    def render(self) -> str:
        if not self.params:
            return self.scheme
        parts = []
        for k, v in self.params.items():
            escaped = v.replace("\\", "\\\\").replace('"', '\\"')
            parts.append(f'{k}="{escaped}"')
        return f"{self.scheme} " + ", ".join(parts)


def parse_www_authenticate(value: str) -> list[Challenge]:
    """Parse a WWW-Authenticate header into challenges.

    Handles the common shapes (`Bearer k="v", k2=v2`, several schemes in one header). Token68
    challenges are kept as a bare scheme.
    """
    challenges: list[Challenge] = []
    pos, n = 0, len(value)
    while pos < n:
        m = re.compile(r"\s*,?\s*([!#$%&'*+.^_`|~0-9A-Za-z-]+)").match(value, pos)
        if not m or m.end() == pos:
            break
        ch = Challenge(scheme=m.group(1))
        pos = m.end()
        while pos < n:
            pm = _PARAM_RE.match(value, pos)
            # stop when the next token is the start of a new scheme (no "=")
            if not pm:
                break
            raw = pm.group(2)
            if raw.startswith('"'):
                raw = re.sub(r"\\(.)", r"\1", raw[1:-1])
            ch.params[pm.group(1).lower()] = raw
            pos = pm.end()
        challenges.append(ch)
    return challenges


def rewrite_www_authenticate(value: str, resource_metadata_url: str) -> str:
    """Point every Bearer challenge at the proxy's PRM for this account."""
    challenges = parse_www_authenticate(value)
    for ch in challenges:
        if ch.scheme.lower() == "bearer":
            ch.params["resource_metadata"] = resource_metadata_url
    return ", ".join(ch.render() for ch in challenges)


def prm_candidates(upstream_url: str, hinted: str | None = None) -> list[str]:
    """Where to look for the upstream's PRM, in spec order (MCP 2025-11-25 authorization)."""
    parts = urlsplit(upstream_url)
    path = parts.path.rstrip("/")
    urls = []
    if hinted:
        urls.append(hinted)
    if path:
        urls.append(urlunsplit((parts.scheme, parts.netloc, WELL_KNOWN_PRM + path, "", "")))
    urls.append(urlunsplit((parts.scheme, parts.netloc, WELL_KNOWN_PRM, "", "")))
    return list(dict.fromkeys(urls))


def proxy_prm_url(account_resource: str) -> str:
    """PRM URL for a proxy resource, using the path-suffixed well-known form."""
    parts = urlsplit(account_resource)
    return urlunsplit((parts.scheme, parts.netloc, WELL_KNOWN_PRM + parts.path, "", ""))


class DiscoveryError(RuntimeError):
    pass


class PrmCache:
    """Fetches and remembers upstream PRM documents, and the hint URLs seen in 401 headers."""

    def __init__(self, http: httpx.AsyncClient):
        self.http = http
        self.hints: dict[str, str] = {}  # upstream url -> resource_metadata from its 401
        self.docs: dict[str, dict] = {}

    def remember_hint(self, upstream_url: str, www_authenticate: str) -> None:
        for ch in parse_www_authenticate(www_authenticate):
            if ch.scheme.lower() == "bearer" and "resource_metadata" in ch.params:
                self.hints[upstream_url] = ch.params["resource_metadata"]
                return

    async def upstream_prm(self, upstream_url: str) -> dict:
        if upstream_url in self.docs:
            return self.docs[upstream_url]
        tried = []
        for url in prm_candidates(upstream_url, self.hints.get(upstream_url)):
            try:
                resp = await self.http.get(url, headers={"Accept": "application/json"})
            except httpx.HTTPError as exc:
                tried.append(f"{url}: {exc.__class__.__name__}")
                continue
            if resp.status_code == 200:
                doc = resp.json()
                if not doc.get("authorization_servers"):
                    raise DiscoveryError(f"{url} has no authorization_servers")
                self.docs[upstream_url] = doc
                return doc
            tried.append(f"{url}: HTTP {resp.status_code}")
        raise DiscoveryError("no protected resource metadata found; tried " + "; ".join(tried))

    async def account_prm(self, upstream_url: str, account_resource: str) -> dict:
        doc = dict(await self.upstream_prm(upstream_url))
        doc["resource"] = account_resource
        return doc


def as_metadata_candidates(issuer: str) -> list[str]:
    """RFC 8414, then OpenID Connect discovery (path-inserted, then appended)."""
    parts = urlsplit(issuer)
    path = parts.path.rstrip("/")
    return list(
        dict.fromkeys(
            [
                urlunsplit(
                    (
                        parts.scheme,
                        parts.netloc,
                        "/.well-known/oauth-authorization-server" + path,
                        "",
                        "",
                    )
                ),
                urlunsplit(
                    (parts.scheme, parts.netloc, "/.well-known/openid-configuration" + path, "", "")
                ),
                issuer.rstrip("/") + "/.well-known/openid-configuration",
            ]
        )
    )


async def fetch_as_metadata(http: httpx.AsyncClient, issuer: str) -> tuple[str, dict] | None:
    """Return (metadata_url, metadata) for an issuer, or None if nothing is found."""
    for url in as_metadata_candidates(issuer):
        try:
            resp = await http.get(url, headers={"Accept": "application/json"})
        except httpx.HTTPError:
            continue
        if resp.status_code == 200:
            return url, resp.json()
    return None
