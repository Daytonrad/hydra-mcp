"""Domain model.

Upstream  -- an MCP server (one URL), e.g. Gmail MCP or Atlassian MCP.
Account   -- one identity at one upstream ("gmail/work", "gmail/perso").
             The credential key of the whole proxy is (user, account), never (user, upstream).
Client    -- one login of one MCP client app at the proxy (Claude Desktop, Claude Code...).
Grant     -- what a client may use: an account, a tool pattern, and read/write mode.
"""

from __future__ import annotations

import fnmatch
import re
from enum import StrEnum

from pydantic import BaseModel, Field, HttpUrl, field_validator

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")


def _slug(v: str) -> str:
    if not SLUG_RE.match(v):
        raise ValueError("must be 1-32 chars of a-z, 0-9 and '-', starting with a letter or digit")
    return v


class Upstream(BaseModel):
    id: str = Field(description="slug, e.g. 'gmail'")
    name: str
    url: HttpUrl = Field(description="canonical MCP endpoint of the upstream server")

    _check_id = field_validator("id")(_slug)


class Account(BaseModel):
    id: str = Field(description="slug, unique across the proxy, e.g. 'gmail-work'")
    upstream_id: str
    alias: str = Field(description="what the model sees, e.g. 'work'")
    identity: str = Field(default="", description="human hint, e.g. alice@corp.example")
    enabled: bool = True

    _check_id = field_validator("id")(_slug)


class GrantMode(StrEnum):
    READ = "read"  # only tools annotated readOnlyHint=true
    WRITE = "write"  # everything (read + write)


class Grant(BaseModel):
    account_id: str
    tools: str = Field(default="*", description="fnmatch pattern on the upstream tool name")
    mode: GrantMode = GrantMode.WRITE


class Client(BaseModel):
    id: str
    name: str
    grants: list[Grant] = Field(default_factory=list)

    _check_id = field_validator("id")(_slug)

    def visible_accounts(self) -> set[str]:
        return {g.account_id for g in self.grants}

    def allows(self, account_id: str, tool: str, *, read_only: bool) -> bool:
        """Authorization check, run on every call (list filtering alone is not security)."""
        for g in self.grants:
            if g.account_id != account_id or not fnmatch.fnmatchcase(tool, g.tools):
                continue
            if g.mode is GrantMode.WRITE or read_only:
                return True
        return False
