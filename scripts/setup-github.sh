#!/usr/bin/env bash
# Apply hydra-mcp's repository settings with the GitHub CLI. Safe to run again.
#
#   gh auth login            # once, as a repository admin
#   scripts/setup-github.sh  # or: REPO=owner/name scripts/setup-github.sh
#
# What it sets, and why, is described in docs/maintainers.md.
set -euo pipefail

REPO="${REPO:-$(gh repo view --json nameWithOwner -q .nameWithOwner)}"
echo "Configuring $REPO"

step() { printf '\n== %s\n' "$1"; }

step "General: description, topics, merge policy"
# REST only (no GraphQL), so it also runs where GraphQL is unavailable.
gh api -X PATCH "repos/$REPO" --input - >/dev/null <<'JSON'
{
  "description": "Self-hosted MCP proxy: use several accounts of the same MCP server (Atlassian, Gmail, GitHub…) from Claude Code, Cursor or VS Code, with per-app access.",
  "has_discussions": true,
  "has_wiki": false,
  "allow_squash_merge": true,
  "allow_merge_commit": false,
  "allow_rebase_merge": false,
  "delete_branch_on_merge": true,
  "allow_auto_merge": true,
  "allow_update_branch": true
}
JSON
gh api -X PUT "repos/$REPO/topics" --input - >/dev/null <<'JSON'
{"names": ["mcp", "model-context-protocol", "mcp-proxy", "oauth", "claude", "cursor", "self-hosted"]}
JSON
gh api -X PATCH "repos/$REPO" -f squash_merge_commit_title=PR_TITLE -f squash_merge_commit_message=PR_BODY >/dev/null

step "Security: Dependabot alerts and fixes, private vulnerability reporting"
gh api -X PUT "repos/$REPO/vulnerability-alerts" >/dev/null
gh api -X PUT "repos/$REPO/automated-security-fixes" >/dev/null
gh api -X PUT "repos/$REPO/private-vulnerability-reporting" >/dev/null

step "Security: secret scanning and push protection"
# Free on public repositories. On a private repository without GitHub Advanced Security this
# step fails: it is applied again when you run the script after making the repository public.
gh api -X PATCH "repos/$REPO" --input - >/dev/null <<'JSON' || echo "   skipped (private repository without Advanced Security?)"
{"security_and_analysis": {
  "secret_scanning": {"status": "enabled"},
  "secret_scanning_push_protection": {"status": "enabled"}
}}
JSON

step "Actions: read-only token by default, no PR approvals by workflows"
gh api -X PUT "repos/$REPO/actions/permissions/workflow" \
  -f default_workflow_permissions=read -F can_approve_pull_request_reviews=false >/dev/null

step "Ruleset: protect main"
RULESET=$(cat <<'JSON'
{
  "name": "main",
  "target": "branch",
  "enforcement": "active",
  "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
  "rules": [
    {"type": "deletion"},
    {"type": "non_fast_forward"},
    {"type": "required_linear_history"},
    {"type": "pull_request", "parameters": {
      "required_approving_review_count": 0,
      "dismiss_stale_reviews_on_push": true,
      "require_code_owner_review": false,
      "require_last_push_approval": false,
      "required_review_thread_resolution": true
    }},
    {"type": "required_status_checks", "parameters": {
      "strict_required_status_checks_policy": true,
      "required_status_checks": [
        {"context": "Proxy (Python 3.11)"},
        {"context": "Proxy (Python 3.13)"},
        {"context": "Admin page"}
      ]
    }}
  ]
}
JSON
)
EXISTING=$(gh api "repos/$REPO/rulesets" -q '.[] | select(.name=="main") | .id' || true)
if [ -n "$EXISTING" ]; then
  echo "$RULESET" | gh api -X PUT "repos/$REPO/rulesets/$EXISTING" --input - >/dev/null
else
  echo "$RULESET" | gh api -X POST "repos/$REPO/rulesets" --input - >/dev/null
fi

step "Labels"
label() {
  # Update the label if it exists, else create it.
  gh api -X PATCH "repos/$REPO/labels/$(printf %s "$1" | sed 's/ /%20/g')" \
    -f color="$2" -f description="$3" >/dev/null 2>&1 ||
    gh api -X POST "repos/$REPO/labels" -f name="$1" -f color="$2" -f description="$3" >/dev/null
}
label "bug"              d73a4a "Something does not work as documented"
label "enhancement"      a2eeef "New feature or improvement"
label "connector"        5319e7 "Connector library: new service or guide update"
label "documentation"    0075ca "Docs only"
label "security"         b60205 "Security hardening (vulnerabilities go through private reporting)"
label "good first issue" 7057ff "Small, well-scoped, good for a first contribution"
label "help wanted"      008672 "Maintainers would welcome a pull request"
label "triage"           fbca04 "Needs a first look"
label "dependencies"     0366d6 "Dependency updates"
label "question"         d876e3 "Better asked in Discussions"

printf '\nDone. Manual steps left: see docs/maintainers.md ("Settings the script cannot apply").\n'
