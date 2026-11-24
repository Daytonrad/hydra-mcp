# Security policy

hydra-mcp stores OAuth tokens for your accounts, so we take vulnerabilities seriously.

## Reporting a vulnerability

**Do not open a public issue.** Report it privately through GitHub:
[Report a vulnerability](https://github.com/lambi702/hydra-mcp/security/advisories/new)
(Security tab, *Report a vulnerability*).

Please include what an attacker can do, the steps to reproduce, the version or commit, and your
setup (OS, how the proxy is exposed). Never include real tokens or keys.

What to expect:

- An acknowledgement within 3 working days.
- An assessment and a plan within 10 working days.
- A fix in a release, then a published advisory crediting you (unless you prefer not to be
  named). We aim to fix critical issues within 30 days and ask you to keep the report private
  until then.

## Supported versions

hydra-mcp is in alpha: only the latest release and `main` receive security fixes.

## Scope

In scope: anything that lets someone read or use a stored token, use an account or tool an app
was not granted, bypass the admin token or client keys, or forge an OAuth login. The
[security model](docs/security.md) describes what hydra-mcp defends against and what it does not
(for example, malware running as your user is out of scope).

Vulnerabilities in the upstream MCP servers themselves (Atlassian, Google, GitHub…) should be
reported to those vendors.
