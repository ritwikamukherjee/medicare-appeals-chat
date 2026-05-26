"""
Dual-mode authentication for Databricks App.

- Deployed on Databricks Apps: uses auto-injected service principal credentials
- Local development: uses Databricks CLI profile
"""

import os
import logging
from databricks.sdk import WorkspaceClient

logger = logging.getLogger(__name__)

IS_DATABRICKS_APP = bool(os.environ.get("DATABRICKS_APP_NAME"))


def get_workspace_client() -> WorkspaceClient:
    """Return an authenticated WorkspaceClient for either deployed or local mode."""
    if IS_DATABRICKS_APP:
        return WorkspaceClient()
    else:
        profile = os.environ.get("DATABRICKS_PROFILE", "hls_amer")
        return WorkspaceClient(profile=profile)


def get_serving_credentials() -> tuple[str, str]:
    """Return (host, token) for calling serving endpoints via OpenAI client."""
    w = get_workspace_client()

    # Get host
    host = w.config.host or os.environ.get("DATABRICKS_HOST", "")
    if host and not host.startswith("http"):
        host = f"https://{host}"
    host = host.rstrip("/")

    # Get token — try multiple methods
    token = w.config.token
    if not token:
        try:
            auth_headers = w.config.authenticate()
            if isinstance(auth_headers, dict) and "Authorization" in auth_headers:
                token = auth_headers["Authorization"].replace("Bearer ", "")
        except Exception as e:
            logger.error(f"authenticate() failed: {e}")

    if not token:
        token = os.environ.get("DATABRICKS_TOKEN", "")

    logger.info(f"Serving credentials: host={host}, token_len={len(token) if token else 0}")
    return host, token
