# Google Ads MCP — PM-Labs Deployment

This is PM-Labs' fork of [googleads/google-ads-mcp](https://github.com/googleads/google-ads-mcp),
extended with an OAuth PKCE proxy for claude.ai integration and container-native refresh-token auth.

## What's added

- `oauth-proxy.js` — Node.js OAuth PKCE proxy (port 8080). Handles claude.ai's OAuth handshake,
  proxies authenticated requests to the Python backend (port 8081), strips Authorization header
  before proxying, performs session resurrection on stale MCP session IDs.
- `start.sh` — Starts the Python MCP server in streamable-http mode then starts the Node proxy.
- `Dockerfile` — Combined Python 3.11 + Node 22 image.
- `ads_mcp/utils.py` — Extended to support OAuth2 refresh-token credentials via env vars
  (`GOOGLE_ADS_CLIENT_ID`, `GOOGLE_ADS_CLIENT_SECRET`, `GOOGLE_ADS_REFRESH_TOKEN`) in addition
  to Application Default Credentials.
- `ads_mcp/server.py` — Extended to accept `MCP_TRANSPORT=streamable-http` env var.

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `GOOGLE_ADS_DEVELOPER_TOKEN` | Yes | Google Ads API developer token |
| `GOOGLE_ADS_CLIENT_ID` | Yes | Google OAuth2 client ID |
| `GOOGLE_ADS_CLIENT_SECRET` | Yes | Google OAuth2 client secret |
| `GOOGLE_ADS_REFRESH_TOKEN` | Yes | OAuth2 refresh token with adwords scope |
| `GOOGLE_ADS_LOGIN_CUSTOMER_ID` | Recommended | MCC manager account ID (no dashes) |
| `MCP_AUTH_TOKEN` | Yes | Static bearer token for claude.ai |
| `OAUTH_CLIENT_ID` | No | OAuth client ID exposed to claude.ai (default: `claude-pathfinder`) |
| `OAUTH_CLIENT_SECRET` | Yes | OAuth client secret for client_credentials flow |
| `PORT` | No | Proxy port (default: 8080) |
| `BACKEND_PORT` | No | Python server port (default: 8081) |

## Obtaining credentials

1. **Developer Token**: Google Ads → Tools → API Center
2. **OAuth credentials**: Google Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client
   - Application type: Web or Desktop
   - Required scope: `https://www.googleapis.com/auth/adwords`
3. **Refresh token**: Use Google's OAuth Playground with scope `https://www.googleapis.com/auth/adwords`

## Infrastructure

Deployed at: `https://google-ads.mcp.pathfindermarketing.com.au/mcp`

Runbook: `/opt/pmin-mcpinfrastructure/docs/runbooks/google-ads.md`
