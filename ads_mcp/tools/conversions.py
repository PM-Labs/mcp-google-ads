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
from ads_mcp.conversion_common import (  # noqa: F401  (re-exported for callers/tests)
    _conversion_action_resource_name,
    _format_googleads_error,
)

# Types create_conversion_action will build. Everything else in Google's type
# enum is created by linking another product (GA4, Firebase, app stores, ...)
# or is reserved for Google, so offering it here would only produce API errors.
CREATABLE_TYPES = (
    "WEBPAGE",
    "WEBSITE_CALL",
    "AD_CALL",
    "CLICK_TO_CALL",
    "UPLOAD_CLICKS",
    "UPLOAD_CALLS",
)

# Only these carry a tag, so only these have snippets worth waiting for.
TYPES_WITH_TAG = ("WEBPAGE", "WEBSITE_CALL")


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


def _read_conversion_action(customer_id: str, action_id: str) -> Optional[dict]:
    """Reads a conversion action back from the API, or None if no row returns."""
    ga_service = utils.get_googleads_service("GoogleAdsService")
    query = (
        "SELECT conversion_action.id, conversion_action.name, "
        "conversion_action.status, conversion_action.type, "
        "conversion_action.category, conversion_action.primary_for_goal, "
        "conversion_action.counting_type, "
        "conversion_action.phone_call_duration_seconds, "
        "conversion_action.click_through_lookback_window_days, "
        "conversion_action.view_through_lookback_window_days, "
        "conversion_action.value_settings.default_value, "
        "conversion_action.value_settings.default_currency_code, "
        "conversion_action.value_settings.always_use_default_value "
        "FROM conversion_action "
        f"WHERE conversion_action.id = {action_id}"
    )
    try:
        for batch in ga_service.search_stream(customer_id=customer_id, query=query):
            for row in batch.results:
                ca = row.conversion_action
                return {
                    "id": str(ca.id),
                    "name": ca.name,
                    "status": ca.status.name,
                    "type": ca.type_.name,
                    "category": ca.category.name,
                    "primary_for_goal": ca.primary_for_goal,
                    "counting_type": ca.counting_type.name,
                    "phone_call_duration_seconds": ca.phone_call_duration_seconds,
                    "click_through_lookback_window_days": (
                        ca.click_through_lookback_window_days
                    ),
                    "view_through_lookback_window_days": (
                        ca.view_through_lookback_window_days
                    ),
                    "default_value": ca.value_settings.default_value,
                    "default_currency_code": ca.value_settings.default_currency_code,
                    "always_use_default_value": (
                        ca.value_settings.always_use_default_value
                    ),
                }
    except GoogleAdsException as ex:
        raise ToolError(_format_googleads_error(ex))
    return None


@mcp.tool()
def create_conversion_action(
    customer_id: str,
    name: str,
    category: str,
    type: str = "WEBPAGE",
    status: str = "ENABLED",
    counting_type: Optional[str] = None,
    click_through_lookback_window_days: Optional[int] = None,
    view_through_lookback_window_days: Optional[int] = None,
    default_value: Optional[float] = None,
    always_use_default_value: bool = False,
    default_currency_code: Optional[str] = None,
    phone_call_duration_seconds: Optional[int] = None,
    primary_for_goal: Optional[bool] = None,
) -> dict:
    """Creates a Google Ads conversion action (e.g. a website lead-form, a phone-call goal or an offline-upload goal).

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
        type: Conversion action type. Default "WEBPAGE". One of WEBPAGE (tag on
            a page), WEBSITE_CALL (calls from a number on the website),
            AD_CALL (calls from ads), CLICK_TO_CALL (taps on a call button),
            UPLOAD_CLICKS (offline conversions matched by click id) or
            UPLOAD_CALLS (offline conversions matched by caller number). The
            type cannot be changed after creation.
        status: "ENABLED" (default), "HIDDEN", or "REMOVED" (REMOVED = archived).
        counting_type: Optional. "ONE_PER_CLICK" (use for leads) or
            "MANY_PER_CLICK" (use for purchases/e-commerce). Omit to let the
            API pick the default for the chosen category.
        click_through_lookback_window_days: Optional click-through conversion
            window. Omit for the API default.
        view_through_lookback_window_days: Optional view-through conversion
            window. Omit for the API default.
        default_value: Optional default conversion value (a number, e.g. 50.0).
        always_use_default_value: If True, always report default_value rather than
            a tag-supplied value. Default False.
        default_currency_code: Optional ISO 4217 currency for the default value
            (e.g. "AUD"). Only meaningful when default_value is set.
        phone_call_duration_seconds: Optional. For call types: the minimum call
            length (0-10000 seconds) before a call counts as a conversion.
        primary_for_goal: Optional. True makes this a primary conversion that
            campaigns bid on; False makes it secondary (reported, not bid on).
            Omit to let Google default it (primary).

    Note:
        Only fields explicitly supplied by the caller are set on the create
        operation — everything else is left to the API's own defaults. This
        mirrors Google's official add_conversion_action.py sample. Setting
        fields the API considers immutable-at-create fails the whole mutate
        with IMMUTABLE_FIELD, so do not reintroduce unconditional assignment.

        `include_in_conversions_metric` is deliberately NOT a parameter. Under
        Google's conversion-goals model, whether an action counts toward the
        "Conversions" metric is governed by `primary_for_goal` and the
        customer/campaign conversion goals — setting it directly on create
        returns IMMUTABLE_FIELD and was the cause of this tool failing on
        every call prior to 2026-08-14.

    Returns:
        A dict with: resource_name, id, name, status, conversion_id
        (e.g. "AW-123456789"), conversion_label, send_to, tag_snippets, and
        snippets_ready (False if snippets had not propagated before the retry
        budget elapsed — re-query the conversion_action by id shortly after;
        None for types that have no tag, such as the upload and ad-call types).
    """
    if type not in CREATABLE_TYPES:
        raise ToolError(
            f"Unsupported conversion type '{type}'. Supported types: "
            f"{', '.join(CREATABLE_TYPES)}"
        )

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
    if counting_type is not None:
        conversion_action.counting_type = _resolve_enum(
            client, "ConversionActionCountingTypeEnum", counting_type
        )
    if click_through_lookback_window_days is not None:
        conversion_action.click_through_lookback_window_days = (
            click_through_lookback_window_days
        )
    if view_through_lookback_window_days is not None:
        conversion_action.view_through_lookback_window_days = (
            view_through_lookback_window_days
        )

    if phone_call_duration_seconds is not None:
        conversion_action.phone_call_duration_seconds = phone_call_duration_seconds
    if primary_for_goal is not None:
        conversion_action.primary_for_goal = primary_for_goal

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
        raise ToolError(_format_googleads_error(ex))

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

    has_tag = type in TYPES_WITH_TAG
    attempts = 6 if has_tag else 1

    snippets = []
    snippets_ready = False if has_tag else None
    fetched_name = name
    fetched_status = status
    for attempt in range(attempts):
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
        if attempt < attempts - 1:
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


@mcp.tool()
def update_conversion_action(
    customer_id: str,
    conversion_action_id: str,
    name: Optional[str] = None,
    status: Optional[str] = None,
    category: Optional[str] = None,
    counting_type: Optional[str] = None,
    click_through_lookback_window_days: Optional[int] = None,
    view_through_lookback_window_days: Optional[int] = None,
    default_value: Optional[float] = None,
    always_use_default_value: Optional[bool] = None,
    default_currency_code: Optional[str] = None,
    phone_call_duration_seconds: Optional[int] = None,
    primary_for_goal: Optional[bool] = None,
) -> dict:
    """Edits an existing conversion action. Only the fields you pass are changed.

    This is also how you set which conversions are primary: primary_for_goal=True
    makes a conversion primary (campaigns bid on it), False makes it secondary
    (still reported, not bid on).

    The conversion type cannot be changed after creation (Google rule). To
    remove a conversion use remove_conversion_action, not status.

    Args:
        customer_id: Google Ads customer ID (digits only, no hyphens).
        conversion_action_id: Numeric id of the conversion action (or its full
            resource name).
        name: New name.
        status: "ENABLED" or "HIDDEN".
        category: New category (e.g. SUBMIT_LEAD_FORM, PHONE_CALL_LEAD).
        counting_type: "ONE_PER_CLICK" or "MANY_PER_CLICK".
        click_through_lookback_window_days: Click-through conversion window.
        view_through_lookback_window_days: View-through conversion window.
        default_value: Default conversion value (a number).
        always_use_default_value: True to always report default_value.
        default_currency_code: ISO 4217 currency for the default value.
        phone_call_duration_seconds: For call types, minimum call length
            (0-10000 seconds) before a call counts.
        primary_for_goal: True = primary, False = secondary.

    Returns:
        The conversion action as read back from the API after the change
        (id, name, status, type, category, primary_for_goal, counting_type,
        phone_call_duration_seconds, lookback windows and value settings).
    """
    if status is not None and status not in ("ENABLED", "HIDDEN"):
        if status == "REMOVED":
            raise ToolError(
                "To remove a conversion action use remove_conversion_action."
            )
        raise ToolError("status must be ENABLED or HIDDEN.")

    cid, action_id, resource_name = _conversion_action_resource_name(
        customer_id, conversion_action_id
    )

    client = utils.get_googleads_client()
    service = client.get_service("ConversionActionService")

    conversion_action = utils.get_googleads_type("ConversionAction")
    conversion_action.resource_name = resource_name
    paths = []

    if name is not None:
        conversion_action.name = name
        paths.append("name")
    if status is not None:
        conversion_action.status = _resolve_enum(
            client, "ConversionActionStatusEnum", status
        )
        paths.append("status")
    if category is not None:
        conversion_action.category = _resolve_enum(
            client, "ConversionActionCategoryEnum", category
        )
        paths.append("category")
    if counting_type is not None:
        conversion_action.counting_type = _resolve_enum(
            client, "ConversionActionCountingTypeEnum", counting_type
        )
        paths.append("counting_type")
    if click_through_lookback_window_days is not None:
        conversion_action.click_through_lookback_window_days = (
            click_through_lookback_window_days
        )
        paths.append("click_through_lookback_window_days")
    if view_through_lookback_window_days is not None:
        conversion_action.view_through_lookback_window_days = (
            view_through_lookback_window_days
        )
        paths.append("view_through_lookback_window_days")
    if default_value is not None:
        conversion_action.value_settings.default_value = default_value
        paths.append("value_settings.default_value")
    if always_use_default_value is not None:
        conversion_action.value_settings.always_use_default_value = (
            always_use_default_value
        )
        paths.append("value_settings.always_use_default_value")
    if default_currency_code is not None:
        conversion_action.value_settings.default_currency_code = (
            default_currency_code
        )
        paths.append("value_settings.default_currency_code")
    if phone_call_duration_seconds is not None:
        conversion_action.phone_call_duration_seconds = phone_call_duration_seconds
        paths.append("phone_call_duration_seconds")
    if primary_for_goal is not None:
        conversion_action.primary_for_goal = primary_for_goal
        paths.append("primary_for_goal")

    if not paths:
        raise ToolError("Nothing to update: pass at least one field to change.")

    operation = utils.get_googleads_type("ConversionActionOperation")
    operation.update = conversion_action
    operation.update_mask.paths.extend(paths)

    try:
        service.mutate_conversion_actions(
            customer_id=cid, operations=[operation]
        )
    except GoogleAdsException as ex:
        raise ToolError(_format_googleads_error(ex))

    state = _read_conversion_action(cid, action_id)
    if state is None:
        return {
            "resource_name": resource_name,
            "id": action_id,
            "verified": False,
            "note": "Updated, but the API did not return the row on read-back.",
        }
    return {"resource_name": resource_name, **state}


@mcp.tool()
def remove_conversion_action(customer_id: str, conversion_action_id: str) -> dict:
    """Removes a conversion action. PERMANENT: Google does not allow a removed
    conversion action to be re-enabled, and campaigns that were bidding on it
    lose that signal. Use update_conversion_action(status="HIDDEN") instead if
    you only want to stop it being used while keeping it.

    Args:
        customer_id: Google Ads customer ID (digits only, no hyphens).
        conversion_action_id: Numeric id of the conversion action (or its full
            resource name).

    Returns:
        resource_name, id, name and the status read back from the API after the
        removal (expected "REMOVED").
    """
    cid, action_id, resource_name = _conversion_action_resource_name(
        customer_id, conversion_action_id
    )

    client = utils.get_googleads_client()
    service = client.get_service("ConversionActionService")

    operation = utils.get_googleads_type("ConversionActionOperation")
    operation.remove = resource_name

    try:
        service.mutate_conversion_actions(
            customer_id=cid, operations=[operation]
        )
    except GoogleAdsException as ex:
        raise ToolError(_format_googleads_error(ex))

    state = _read_conversion_action(cid, action_id)
    if state is None:
        return {
            "resource_name": resource_name,
            "id": action_id,
            "status": None,
            "verified": False,
            "note": "Removed, but the API did not return the row on read-back.",
        }
    return {"resource_name": resource_name, **state}
