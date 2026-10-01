"""Helpers shared by the conversion tools.

Lives outside `ads_mcp/tools/` on purpose: it must not import the coordinator.
Tool modules are auto-loaded by the coordinator, so a tool module importing a
sibling tool module for helpers creates a circular import whenever the sibling
happens to be loaded first.
"""

import re

import ads_mcp.utils as utils
from google.ads.googleads.errors import GoogleAdsException
from fastmcp.exceptions import ToolError


def _format_googleads_error(ex: GoogleAdsException) -> str:
    """Renders a GoogleAdsException with the field path of each error.

    The bare `error.message` for a field-level failure is untargeted -- e.g.
    "The field attempted to be mutated is immutable." names no field, which
    makes a failing mutate effectively undiagnosable without a code change and
    redeploy. `error.location.field_path_elements` carries the actual path, so
    always render it when present.
    """
    lines = [f"Request ID: {ex.request_id}"]
    for error in ex.failure.errors:
        path_elements = getattr(
            getattr(error, "location", None), "field_path_elements", []
        ) or []
        path = ".".join(
            str(getattr(el, "field_name", "")) for el in path_elements
            if getattr(el, "field_name", "")
        )
        lines.append(f"{error.message} [field: {path}]" if path else error.message)
    return "\n".join(lines)


def _conversion_action_resource_name(
    customer_id: str, conversion_action_id: str
) -> tuple[str, str, str]:
    """Returns (clean customer id, conversion action id, resource name).

    Accepts a bare numeric id or a full resource name, and refuses a resource
    name that belongs to a different customer than `customer_id`.
    """
    cid = utils.clean_customer_id(customer_id)
    if not re.fullmatch(r"[0-9]+", cid):
        raise ToolError(
            f"customer_id must be digits only (e.g. 9239924925), got: {customer_id!r}"
        )
    raw = str(conversion_action_id).strip()
    match = re.fullmatch(r"customers/([0-9]+)/conversionActions/([0-9]+)", raw)
    if match:
        if match.group(1) != cid:
            raise ToolError(
                f"conversion_action_id belongs to customer {match.group(1)}, "
                f"not {cid}."
            )
        action_id = match.group(2)
    elif re.fullmatch(r"[0-9]+", raw):
        action_id = raw
    else:
        raise ToolError(
            "conversion_action_id must be the numeric id (e.g. 7720348543) or "
            "a full resource name (customers/<id>/conversionActions/<id>), "
            f"got: {raw!r}"
        )
    return cid, action_id, f"customers/{cid}/conversionActions/{action_id}"
