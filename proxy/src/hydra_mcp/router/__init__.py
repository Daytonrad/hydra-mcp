"""Router mode (phase 0): per-account URLs, zero token custody."""

from hydra_mcp.router.passthrough import Router, account_resource

__all__ = ["Router", "account_resource"]
