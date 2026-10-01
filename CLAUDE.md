# mcp-google-ads — orientation

Python FastMCP server wrapping the Google Ads API. Deployed at
`https://google-ads.mcp.pathfindermarketing.com.au/mcp`.

This file covers what is **not** obvious from reading the code. The README
covers structure.

---

## This is a fork — know what is ours

Forked from `googleads/google-ads-mcp` (the `upstream` remote is configured).
Most of `ads_mcp/` is upstream code we periodically sync.

**`ads_mcp/tools/conversions.py` is entirely Pathfinder-authored** — it does
not exist upstream. Don't expect upstream fixes for it, and don't lose it in a
merge. Check `git log upstream/main -- <path>` before assuming a file is theirs.

---

## Invariant: never set `include_in_conversions_metric` on create

`create_conversion_action` must only assign fields the caller explicitly
supplied. Assigning unset optional fields is not merely untidy — it breaks the
tool outright.

Under Google's conversion-goals model, whether an action counts toward the
"Conversions" metric is governed by `primary_for_goal` and the
customer/campaign conversion goals. `include_in_conversions_metric` is not
settable at create; sending it fails the **entire** mutate with
`IMMUTABLE_FIELD`, regardless of every other argument.

This shipped broken and stayed broken because the tool had **zero test
coverage** — it was the only module in `ads_mcp/tools/` without a test file, so
nothing caught it. `tests/tools/conversions_test.py` now guards it. Do not
weaken that test.

Reference implementation to mirror when extending: Google's official
`examples/remarketing/add_conversion_action.py` in `googleads/google-ads-python`
— it sets only `name`, `type_`, `category`, `status`,
`view_through_lookback_window_days` and `value_settings`.

## Always surface `field_path_elements` on API errors

`GoogleAdsException` messages are untargeted — "The field attempted to be
mutated is immutable." names no field. Use `_format_googleads_error()`, which
renders `error.location.field_path_elements`. Without it, diagnosing a field
error costs a full code-change-and-redeploy cycle (it did, on 2026-08-13).

Apply the same pattern to any new tool that mutates.

---

## Auth: one static identity, and its access level gates every write

The server authenticates with a **static refresh token**
(`GOOGLE_ADS_REFRESH_TOKEN`), not per-user OAuth — see `ads_mcp/utils.py`. It
does **not** act as the Claude session user.

Consequence: every write tool's success depends on the Google Ads access role
of that one identity on MCC `1062239797`. If it holds `READ_ONLY`, all reads
succeed and **all ~20 mutating tools fail** with
`PERMISSION_DENIED — The user does not have permission…`. That exact state
existed until 2026-08-13.

To check the current identity's role:

```
SELECT customer_user_access.email_address, customer_user_access.access_role
FROM customer_user_access
```
(run against the MCC; requires ADMIN to return rows)

`STANDARD` is sufficient for conversion actions and campaign management —
`ADMIN` is not required.

## Decision: no write gate

Unlike `mcp-bing-ads` — which hides every mutating tool behind
`BING_ADS_MCP_WRITE` in `src/writeGate.ts` and refuses them at call time when
unset — this server has **no gate**, on purpose. A gate would be one on/off
switch for the whole shared server, and the conversion work needs writes on, so
it would block nothing. All mutating tools are exposed unconditionally against
every client account in the MCC. Don't add a gate without a per-account design.

---

## Conversion tools (`conversions.py`, `conversion_uploads.py`)

Four tools: `create_conversion_action`, `update_conversion_action`,
`remove_conversion_action`, `upload_offline_conversions`.

- **`CREATABLE_TYPES` is an allowlist** (web page, website call, ad call,
  click-to-call, upload clicks, upload calls). The other types in Google's enum
  come from linking GA4/Firebase/app stores or are Google-reserved. The type is
  **immutable after create** — `update_conversion_action` can't change it.
- **"Primary" is `primary_for_goal`**, settable on create and update. `False`
  is a real value: check `is not None`, never truthiness.
- **Update sends only supplied fields**, with an explicit `update_mask`
  (`value_settings.*` for the nested ones). Same principle as the create
  invariant above — never assign a field the caller didn't pass.
- **Remove is permanent** (Google never lets a removed action be re-enabled).
  `status` on update accepts only ENABLED/HIDDEN and points at the remove tool.
- **Every write reads back** from the API and returns that state, not the
  request echoed.
- **Uploads always use partial failure** and return one result per row.
  Unknown row keys are refused (a typo'd `gclidd` would otherwise upload
  nothing silently). Out of scope by design: enhanced conversions for leads
  (hashed email/phone) and upload adjustments (restatements/retractions).
- Tag snippets are only waited for on types that have a tag (`TYPES_WITH_TAG`);
  other types return `snippets_ready: None` instead of burning the retry budget.

---

## Env vars

| Var | Notes |
|---|---|
| `GOOGLE_ADS_DEVELOPER_TOKEN` | Required; raises at client construction if unset |
| `GOOGLE_ADS_REFRESH_TOKEN` | With client id/secret — the static identity above |
| `GOOGLE_ADS_LOGIN_CUSTOMER_ID` | The MCC. Optional, but omit it and child-account calls fail |

---

## Runtime gotchas

- **fastmcp 3.3.1 breaking changes:** import from `fastmcp`, not
  `mcp.server.fastmcp`; `host`/`port` moved off the `FastMCP()` constructor onto
  `mcp.run()`.
- **Node oauth-proxy sidecar** (port 8080) starts the Python backend on 8081 via
  `start.sh`. Both must be healthy for the MCP to answer.

---

## Tests

```bash
uv run --with "google-ads>=31.0.0" --with fastmcp --with pytest \
  python -m pytest tests/ -q --ignore=tests/smoke
```

`tests/smoke/test_token_usage.py` needs `google.genai`, which isn't in the
default dev set — it fails at **collection** and aborts the whole run, so
exclude `tests/smoke` unless you've installed it.
