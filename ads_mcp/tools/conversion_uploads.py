"""Tool for uploading offline conversions (by click id or by caller number).

Pathfinder-authored; does not exist upstream. One tool covers both kinds so the
tool list stays small. Uploads always use partial failure, so one bad row never
sinks the rest, and every row gets its own result.

Out of scope on purpose: enhanced conversions for leads (hashed email/phone)
and conversion adjustments (restatements/retractions).

Known limit: Google rejects click uploads through this API for our developer
token (new integrations must use the Data Manager API). See the tool docstring.
"""

import re
from typing import Any

from ads_mcp.coordinator import mcp
import ads_mcp.utils as utils
from ads_mcp.conversion_common import (
    _conversion_action_resource_name,
    _format_googleads_error,
)
from google.ads.googleads.errors import GoogleAdsException
from fastmcp.exceptions import ToolError

# Google's per-request cap for conversion uploads.
MAX_PER_REQUEST = 2000

# "yyyy-mm-dd hh:mm:ss+|-hh:mm", e.g. "2026-10-01 10:30:00+08:00".
DATETIME_RE = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}")

CLICK_ID_FIELDS = ("gclid", "gbraid", "wbraid")
CLICK_FIELDS = set(CLICK_ID_FIELDS) | {
    "conversion_date_time",
    "conversion_value",
    "currency_code",
    "order_id",
}
CALL_FIELDS = {
    "caller_id",
    "call_start_date_time",
    "conversion_date_time",
    "conversion_value",
    "currency_code",
}


def _validate_rows(kind: str, rows: list) -> None:
    """Raises ToolError naming the first bad row. Nothing is sent to the API."""
    if kind not in ("click", "call"):
        raise ToolError("kind must be 'click' or 'call'.")
    if not rows:
        raise ToolError("conversions must contain at least one row.")
    if len(rows) > MAX_PER_REQUEST:
        raise ToolError(
            f"At most {MAX_PER_REQUEST} conversions per call, got {len(rows)}."
        )

    allowed = CLICK_FIELDS if kind == "click" else CALL_FIELDS
    time_fields = (
        ("conversion_date_time",)
        if kind == "click"
        else ("conversion_date_time", "call_start_date_time")
    )

    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ToolError(f"row {i}: each conversion must be an object.")
        unknown = sorted(set(row) - allowed)
        if unknown:
            raise ToolError(
                f"row {i}: unknown field(s) for kind '{kind}': "
                f"{', '.join(unknown)}. Allowed: {', '.join(sorted(allowed))}."
            )
        if kind == "click":
            ids = [f for f in CLICK_ID_FIELDS if row.get(f)]
            if len(ids) != 1:
                raise ToolError(
                    f"row {i}: supply exactly one of gclid, gbraid, wbraid "
                    f"(got {len(ids)})."
                )
        elif not row.get("caller_id"):
            raise ToolError(f"row {i}: caller_id is required for kind 'call'.")
        for f in time_fields:
            value = row.get(f)
            if not value:
                raise ToolError(f"row {i}: {f} is required.")
            if not DATETIME_RE.fullmatch(str(value)):
                raise ToolError(
                    f"row {i}: {f} must look like '2026-10-01 10:30:00+08:00' "
                    f"(with a UTC offset), got {value!r}."
                )


def _element_index(element) -> Any:
    """The operation index a field-path element points at, or None if unset."""
    pb = type(element).pb(element)
    return pb.index if pb.HasField("index") else None


def _row_errors(response, failure_cls) -> tuple[dict, list]:
    """Splits a partial-failure error into (errors by row index, other errors)."""
    by_index: dict = {}
    other: list = []
    partial = getattr(response, "partial_failure_error", None)
    if partial is None or getattr(partial, "code", 0) == 0:
        return by_index, other

    for detail in partial.details:
        failure = failure_cls.deserialize(detail.value)
        for error in failure.errors:
            elements = list(error.location.field_path_elements)
            index = _element_index(elements[0]) if elements else None
            path = ".".join(e.field_name for e in elements[1:] if e.field_name)
            message = f"{error.message} [field: {path}]" if path else error.message
            if index is None:
                other.append(message)
            else:
                by_index.setdefault(index, []).append(message)
    if not partial.details and getattr(partial, "message", ""):
        other.append(partial.message)
    return by_index, other


@mcp.tool()
def upload_offline_conversions(
    customer_id: str,
    conversion_action_id: str,
    conversions: list[dict],
    kind: str = "click",
    validate_only: bool = False,
) -> dict:
    """Uploads offline conversions to a conversion action.

    Use kind="click" for conversions matched by a click id, or kind="call" for
    conversions matched by the caller's phone number. The conversion action
    must be of the matching upload type (UPLOAD_CLICKS or UPLOAD_CALLS).

    KNOWN LIMIT (checked live 2026-10-01): Google currently rejects kind="click"
    for our developer token with "New integrations for uploading click
    conversions should use the Data Manager API". Every click row then comes
    back as an error. kind="call" reaches Google's normal validation (calls
    must be at least 6 hours old). HubSpot's own integration still uploads
    click conversions to the existing "HubSpot - ..." conversions.

    Rows are sent with partial failure on, so one bad row does not stop the
    others; each row gets its own result. For click uploads, include order_id
    on every row: Google uses it to ignore duplicates, so a retried call does
    not double-count. Set validate_only=True to have Google
    check the rows without recording anything.

    Args:
        customer_id: Google Ads customer ID (digits only, no hyphens).
        conversion_action_id: Numeric id of the conversion action (or its full
            resource name).
        conversions: List of rows, at most 2000 per call.
            For kind="click" each row needs exactly one of gclid / gbraid /
            wbraid plus conversion_date_time; optional conversion_value,
            currency_code (e.g. "AUD") and order_id.
            For kind="call" each row needs caller_id (e.g. "+61400000000"),
            call_start_date_time and conversion_date_time; optional
            conversion_value and currency_code.
            Times look like "2026-10-01 10:30:00+08:00" (with a UTC offset).
            Unknown fields are refused rather than ignored.
        kind: "click" (default) or "call".
        validate_only: If True, validate without uploading.

    Returns:
        submitted, succeeded, failed counts; validate_only; results (one per
        row: index, status "ok" / "validated" / "error", errors); and
        other_errors for failures that do not point at a single row.
    """
    _validate_rows(kind, conversions)
    cid, _, resource_name = _conversion_action_resource_name(
        customer_id, conversion_action_id
    )

    client = utils.get_googleads_client()
    service = client.get_service("ConversionUploadService")

    built = []
    for row in conversions:
        if kind == "click":
            item = utils.get_googleads_type("ClickConversion")
            for f in CLICK_ID_FIELDS:
                if row.get(f):
                    setattr(item, f, row[f])
            if row.get("order_id"):
                item.order_id = row["order_id"]
        else:
            item = utils.get_googleads_type("CallConversion")
            item.caller_id = row["caller_id"]
            item.call_start_date_time = row["call_start_date_time"]
        item.conversion_action = resource_name
        item.conversion_date_time = row["conversion_date_time"]
        if row.get("conversion_value") is not None:
            item.conversion_value = row["conversion_value"]
        if row.get("currency_code"):
            item.currency_code = row["currency_code"]
        built.append(item)

    # The client library accepts validate_only only inside a request object, not
    # as a keyword argument (found live, 2026-10-01).
    request = utils.get_googleads_type(
        "UploadClickConversionsRequest"
        if kind == "click"
        else "UploadCallConversionsRequest"
    )
    request.customer_id = cid
    request.conversions.extend(built)
    request.partial_failure = True
    request.validate_only = validate_only
    upload = (
        service.upload_click_conversions
        if kind == "click"
        else service.upload_call_conversions
    )
    try:
        response = upload(request=request)
    except GoogleAdsException as ex:
        raise ToolError(_format_googleads_error(ex))

    failure_cls = type(utils.get_googleads_type("GoogleAdsFailure"))
    by_index, other_errors = _row_errors(response, failure_cls)

    ok_status = "validated" if validate_only else "ok"
    results = []
    for i in range(len(built)):
        if i in by_index:
            results.append({"index": i, "status": "error", "errors": by_index[i]})
        else:
            results.append({"index": i, "status": ok_status, "errors": []})

    failed = len(by_index)
    return {
        "kind": kind,
        "validate_only": validate_only,
        "submitted": len(built),
        "succeeded": len(built) - failed,
        "failed": failed,
        "results": results,
        "other_errors": other_errors,
    }
