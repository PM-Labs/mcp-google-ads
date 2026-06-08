"""Tools for managing Google Ads conversion actions.

SAFETY NOTE — divergence from campaign_builder.py:
    campaign_builder.py hardcodes status=PAUSED on every create because those
    tools commit ad spend. A conversion action is *tracking configuration*, not
    spend, so create_conversion_action defaults status=ENABLED — a freshly
    created conversion action should start measuring immediately. status is a
    parameter here (default ENABLED) rather than a hardcoded invariant.
"""

import re
import time
from typing import Optional
from ads_mcp.coordinator import mcp
import ads_mcp.utils as utils
from google.ads.googleads.errors import GoogleAdsException
from fastmcp.exceptions import ToolError


def _resolve_enum(client, enum_name: str, value: str):
    """Looks up an enum member by name, raising a helpful ToolError on a bad value."""
    enum_obj = getattr(client.enums, enum_name)
    try:
        return enum_obj[value]
    except KeyError:
        valid = [
            m.name
            for m in enum_obj
            if m.name not in ("UNSPECIFIED", "UNKNOWN")
        ]
        raise ToolError(
            f"Invalid {enum_name} value '{value}'. Valid values: {', '.join(valid)}"
        )


def _parse_send_to(snippets) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Extracts (conversion_id, label, send_to) from a conversion action's tag snippets.

    The gtag event snippet contains `'send_to': 'AW-XXXXXXXXX/label'`. The
    AW-prefixed value is the account-level conversion ID; the label is per
    conversion action.
    """
    for snippet in snippets:
        event_snippet = getattr(snippet, "event_snippet", "") or ""
        match = re.search(
            r"send_to['\"]?\s*:\s*['\"]([^'\"]+)['\"]", event_snippet
        )
        if match:
            send_to = match.group(1)
            if "/" in send_to:
                conversion_id, label = send_to.split("/", 1)
            else:
                conversion_id, label = send_to, None
            return conversion_id, label, send_to
    return None, None, None


@mcp.tool()
def create_conversion_action(
    customer_id: str,
    name: str,
    category: str,
    type: str = "WEBPAGE",
    status: str = "ENABLED",
    counting_type: str = "ONE_PER_CLICK",
    click_through_lookback_window_days: int = 30,
    view_through_lookback_window_days: int = 1,
    default_value: Optional[float] = None,
    always_use_default_value: bool = False,
    default_currency_code: Optional[str] = None,
    include_in_conversions_metric: bool = True,
) -> dict:
    """Creates a Google Ads conversion action (e.g. a website lead-form or purchase goal).

    Unlike the campaign-build tools, this creates the conversion action LIVE
    (status defaults to ENABLED) so it begins measuring immediately. After
    creation, the conversion action's tag snippets are re-queried (with retry,
    since they can lag the create call) so the caller gets the gtag conversion
    ID (AW-XXXXXXXXX) and label back.

    Args:
        customer_id: Google Ads customer ID (digits only, no hyphens).
        name: Conversion action name (e.g. "PM | Website Form Submission").
        category: Conversion category. Common values: SUBMIT_LEAD_FORM,
            PHONE_CALL_LEAD, PURCHASE, CONTACT, SIGNUP, PAGE_VIEW, DOWNLOAD,
            BOOK_APPOINTMENT, REQUEST_QUOTE, QUALIFIED_LEAD, CONVERTED_LEAD.
            (Invalid values return the full valid list.)
        type: Conversion action type. Default "WEBPAGE".
        status: "ENABLED" (default), "HIDDEN", or "REMOVED" (REMOVED = archived).
        counting_type: "ONE_PER_CLICK" (default, use for leads) or
            "MANY_PER_CLICK" (use for purchases/e-commerce).
        click_through_lookback_window_days: Click-through conversion window. Default 30.
        view_through_lookback_window_days: View-through conversion window. Default 1.
        default_value: Optional default conversion value (a number, e.g. 50.0).
        always_use_default_value: If True, always report default_value rather than
            a tag-supplied value. Default False.
        default_currency_code: Optional ISO 4217 currency for the default value
            (e.g. "AUD"). Only meaningful when default_value is set.
        include_in_conversions_metric: Whether to include this action in the
            "Conversions" reporting metric. Default True.

    Returns:
        A dict with: resource_name, id, name, status, conversion_id
        (e.g. "AW-123456789"), conversion_label, send_to, tag_snippets, and
        snippets_ready (False if snippets had not propagated before the retry
        budget elapsed — re-query the conversion_action by id shortly after).
    """
    client = utils.get_googleads_client()
    service = client.get_service("ConversionActionService")

    conversion_action = utils.get_googleads_type("ConversionAction")
    conversion_action.name = name
    conversion_action.category = _resolve_enum(
        client, "ConversionActionCategoryEnum", category
    )
    conversion_action.type_ = _resolve_enum(
        client, "ConversionActionTypeEnum", type
    )
    conversion_action.status = _resolve_enum(
        client, "ConversionActionStatusEnum", status
    )
    conversion_action.counting_type = _resolve_enum(
        client, "ConversionActionCountingTypeEnum", counting_type
    )
    conversion_action.click_through_lookback_window_days = (
        click_through_lookback_window_days
    )
    conversion_action.view_through_lookback_window_days = (
        view_through_lookback_window_days
    )
    conversion_action.include_in_conversions_metric = include_in_conversions_metric

    if default_value is not None:
        conversion_action.value_settings.default_value = default_value
    conversion_action.value_settings.always_use_default_value = (
        always_use_default_value
    )
    if default_currency_code:
        conversion_action.value_settings.default_currency_code = (
            default_currency_code
        )

    operation = utils.get_googleads_type("ConversionActionOperation")
    operation.create = conversion_action

    try:
        response = service.mutate_conversion_actions(
            customer_id=customer_id, operations=[operation]
        )
    except GoogleAdsException as ex:
        raise ToolError(
            f"Request ID: {ex.request_id}\n"
            + "\n".join(e.message for e in ex.failure.errors)
        )

    resource_name = response.results[0].resource_name
    conversion_action_id = resource_name.rsplit("/", 1)[-1]

    # Re-query for tag snippets — they can lag immediately after create, so
    # retry a few times before giving up.
    ga_service = utils.get_googleads_service("GoogleAdsService")
    query = (
        "SELECT conversion_action.id, conversion_action.name, "
        "conversion_action.status, conversion_action.resource_name, "
        "conversion_action.tag_snippets "
        "FROM conversion_action "
        f"WHERE conversion_action.id = {conversion_action_id} "
        "PARAMETERS omit_unselected_resource_names=true"
    )

    snippets = []
    snippets_ready = False
    fetched_name = name
    fetched_status = status
    for attempt in range(6):
        try:
            stream = ga_service.search_stream(
                customer_id=customer_id, query=query
            )
            for batch in stream:
                for row in batch.results:
                    fetched_name = row.conversion_action.name
                    fetched_status = row.conversion_action.status.name
                    snippets = list(row.conversion_action.tag_snippets)
        except GoogleAdsException:
            snippets = []
        if snippets:
            snippets_ready = True
            break
        if attempt < 5:
            time.sleep(1.0)

    conversion_id, label, send_to = _parse_send_to(snippets)

    return {
        "resource_name": resource_name,
        "id": conversion_action_id,
        "name": fetched_name,
        "status": fetched_status,
        "conversion_id": conversion_id,
        "conversion_label": label,
        "send_to": send_to,
        "tag_snippets": utils.format_output_value(snippets),
        "snippets_ready": snippets_ready,
    }
