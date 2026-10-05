"""PM-Labs fork guard: the static refresh-token identity must survive upstream syncs.

This file is PM-Labs-only (no upstream counterpart) so upstream test edits never
conflict with it. The Dockerfile runs it at build time: if a fork-sync or a manual
conflict resolution drops the GOOGLE_ADS_* refresh-token branch from
ads_mcp/utils.py, the image fails to build and scripts/sync.sh rolls back instead
of deploying a server that can only fall back to Application Default Credentials.

That is exactly what happened on 2026-10-02: an upstream sync replaced
_create_credentials() with a FastMCP-token-or-ADC version, every static-bearer
caller (reporting cron, Ad Ops Sentinel, the claude.ai connector) failed with
"Your default credentials were not found", and the health check stayed green.
"""

import os
import unittest
from unittest import mock

import google.oauth2.credentials

from ads_mcp import utils

_ENV = {
    "GOOGLE_ADS_CLIENT_ID": "test-client-id",
    "GOOGLE_ADS_CLIENT_SECRET": "test-client-secret",
    "GOOGLE_ADS_REFRESH_TOKEN": "test-refresh-token",
}


class TestStaticRefreshTokenAuth(unittest.TestCase):
    """The env refresh token is the server's identity -- never ADC when it is set."""

    def test_env_refresh_token_is_used(self):
        with mock.patch.dict(os.environ, _ENV), mock.patch(
            "google.auth.default",
            side_effect=AssertionError(
                "fell back to Application Default Credentials although "
                "GOOGLE_ADS_REFRESH_TOKEN is set -- the PM-Labs static-auth "
                "branch in ads_mcp/utils.py:_create_credentials() was dropped"
            ),
        ):
            creds = utils._create_credentials()

        self.assertIsInstance(creds, google.oauth2.credentials.Credentials)
        self.assertEqual(creds.refresh_token, "test-refresh-token")
        self.assertEqual(creds.client_id, "test-client-id")
        self.assertEqual(creds.token_uri, "https://oauth2.googleapis.com/token")


if __name__ == "__main__":
    unittest.main()
