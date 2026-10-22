"""Tools for choosing which conversion goals Google Ads bids on.

A conversion goal is a (category, origin) pair, e.g. SUBMIT_LEAD_FORM from
WEBSITE or PHONE_CALL_LEAD from CALL_FROM_ADS. Whether campaigns bid on a goal
is set in one of two places:

  - account-default goals (customer_conversion_goal) -- used by every campaign
    whose conversion_goal_campaign_config.goal_config_level is CUSTOMER;
  - campaign-specific goals (campaign_conversion_goal) -- used by a campaign
    whose goal_config_level is CAMPAIGN.

Goals cannot be created or removed through the API: Google creates one per
(category, origin) as soon as a conversion action of that kind exists. These
tools only flip `biddable` (and the campaign's goal level).
"""

import re

from ads_mcp.coordinator import mcp
import ads_mcp.utils as utils
from google.ads.googleads.errors import GoogleAdsException
from fastmcp.exceptions import ToolError
from ads_mcp.conversion_common import _format_googleads_error


def _clean_cid(customer_id: str) -> str:
    cid = utils.clean_customer_id(customer_id)
    if not re.fullmatch(r"[0-9]+", cid):
        raise ToolError(
            f"customer_id must be digits only (e.g. 9239924925), got: {customer_id!r}"
        )
    return cid


def _clean_campaign_id(campaign_id: str) -> str:
    raw = str(campaign_id).strip()
    if not re.fullmatch(r"[0-9]+", raw):
        raise ToolError(f"campaign_id must be digits only, got: {campaign_id!r}")
    return raw


def _enum_name(client, enum_name: str, value: str) -> str:
    """Validates an enum member name, raising a helpful ToolError on a bad value.

    Resource names use the member NAME (e.g. SUBMIT_LEAD_FORM~WEBSITE), so the
    validated name is returned rather than the numeric value.
    """
    enum_obj = getattr(client.enums, enum_name)
    value = str(value).strip().upper()
    try:
        enum_obj[value]
    except KeyError:
        valid = [
            m.name for m in enum_obj if m.name not in ("UNSPECIFIED", "UNKNOWN")
        ]
        raise ToolError(
            f"Invalid {enum_name} value '{value}'. Valid values: {', '.join(valid)}"
        )
    return value


def _read_rows(customer_id: str, query: str) -> list:
    ga_service = utils.get_googleads_service("GoogleAdsService")
    rows = []
    try:
        for batch in ga_service.search_stream(customer_id=customer_id, query=query):
            rows.extend(batch.results)
    except GoogleAdsException as ex:
        raise ToolError(_format_googleads_error(ex))
    return rows


@mcp.tool()
def update_customer_conversion_goal(
    customer_id: str, category: str, origin: str, biddable: bool
) -> dict:
    """Sets whether an ACCOUNT-DEFAULT conversion goal is biddable.

    This is the "Use as account-default goal" switch in Goals > Summary. Every
    campaign whose goal_config_level is CUSTOMER bids on the account-default
    goals; a campaign set to CAMPAIGN uses its own goals instead (see
    update_campaign_conversion_goal and set_campaign_goal_config_level).

    Which conversion actions sit inside a goal, and which of them are primary,
    is set per action with update_conversion_action(primary_for_goal=...).

    Args:
        customer_id: Google Ads customer ID (digits only, no hyphens).
        category: Goal category, e.g. SUBMIT_LEAD_FORM, PHONE_CALL_LEAD,
            OUTBOUND_CLICK, PURCHASE, PAGE_VIEW, CONTACT, BOOK_APPOINTMENT.
        origin: Where the conversions come from: WEBSITE, CALL_FROM_ADS,
            GOOGLE_HOSTED, APP, STORE, YOUTUBE_HOSTED.
        biddable: True = account-default goal (campaigns bid on it),
            False = not bid on by default.

    Hints:
        Read the current state first with search on resource
        customer_conversion_goal (fields category, origin, biddable). A goal
        only exists once a conversion action of that category/origin exists;
        an unknown pair returns NOT_FOUND.

    Returns:
        resource_name, category, origin and biddable as read back from the API.
    """
    cid = _clean_cid(customer_id)
    client = utils.get_googleads_client()
    category = _enum_name(client, "ConversionActionCategoryEnum", category)
    origin = _enum_name(client, "ConversionOriginEnum", origin)
    resource_name = f"customers/{cid}/customerConversionGoals/{category}~{origin}"

    goal = utils.get_googleads_type("CustomerConversionGoal")
    goal.resource_name = resource_name
    goal.biddable = bool(biddable)

    operation = utils.get_googleads_type("CustomerConversionGoalOperation")
    operation.update = goal
    operation.update_mask.paths.append("biddable")

    service = client.get_service("CustomerConversionGoalService")
    try:
        service.mutate_customer_conversion_goals(
            customer_id=cid, operations=[operation]
        )
    except GoogleAdsException as ex:
        raise ToolError(_format_googleads_error(ex))

    rows = _read_rows(
        cid,
        "SELECT customer_conversion_goal.category, customer_conversion_goal.origin, "
        "customer_conversion_goal.biddable FROM customer_conversion_goal "
        f"WHERE customer_conversion_goal.resource_name = '{resource_name}'",
    )
    if not rows:
        return {
            "resource_name": resource_name,
            "verified": False,
            "note": "Updated, but the API did not return the row on read-back.",
        }
    g = rows[0].customer_conversion_goal
    return {
        "resource_name": resource_name,
        "category": g.category.name,
        "origin": g.origin.name,
        "biddable": g.biddable,
    }


@mcp.tool()
def update_campaign_conversion_goal(
    customer_id: str,
    campaign_id: str,
    category: str,
    origin: str,
    biddable: bool,
) -> dict:
    """Sets whether a CAMPAIGN-SPECIFIC conversion goal is biddable.

    Only takes effect for a campaign whose goal_config_level is CAMPAIGN; a
    campaign on CUSTOMER uses the account-default goals
    (update_customer_conversion_goal). Check the level with search on resource
    conversion_goal_campaign_config, or change it with
    set_campaign_goal_config_level.

    Args:
        customer_id: Google Ads customer ID (digits only, no hyphens).
        campaign_id: Numeric campaign id.
        category: Goal category, e.g. SUBMIT_LEAD_FORM, PHONE_CALL_LEAD,
            OUTBOUND_CLICK, PURCHASE.
        origin: WEBSITE, CALL_FROM_ADS, GOOGLE_HOSTED, APP, STORE,
            YOUTUBE_HOSTED.
        biddable: True = this campaign bids on the goal, False = it doesn't.

    Returns:
        resource_name, campaign_id, category, origin and biddable as read back
        from the API.
    """
    cid = _clean_cid(customer_id)
    camp = _clean_campaign_id(campaign_id)
    client = utils.get_googleads_client()
    category = _enum_name(client, "ConversionActionCategoryEnum", category)
    origin = _enum_name(client, "ConversionOriginEnum", origin)
    resource_name = (
        f"customers/{cid}/campaignConversionGoals/{camp}~{category}~{origin}"
    )

    goal = utils.get_googleads_type("CampaignConversionGoal")
    goal.resource_name = resource_name
    goal.biddable = bool(biddable)

    operation = utils.get_googleads_type("CampaignConversionGoalOperation")
    operation.update = goal
    operation.update_mask.paths.append("biddable")

    service = client.get_service("CampaignConversionGoalService")
    try:
        service.mutate_campaign_conversion_goals(
            customer_id=cid, operations=[operation]
        )
    except GoogleAdsException as ex:
        raise ToolError(_format_googleads_error(ex))

    rows = _read_rows(
        cid,
        "SELECT campaign.id, campaign_conversion_goal.category, "
        "campaign_conversion_goal.origin, campaign_conversion_goal.biddable "
        "FROM campaign_conversion_goal "
        f"WHERE campaign_conversion_goal.resource_name = '{resource_name}'",
    )
    if not rows:
        return {
            "resource_name": resource_name,
            "verified": False,
            "note": "Updated, but the API did not return the row on read-back.",
        }
    g = rows[0].campaign_conversion_goal
    return {
        "resource_name": resource_name,
        "campaign_id": camp,
        "category": g.category.name,
        "origin": g.origin.name,
        "biddable": g.biddable,
    }


@mcp.tool()
def set_campaign_goal_config_level(
    customer_id: str, campaign_id: str, goal_config_level: str
) -> dict:
    """Chooses whether a campaign uses the account-default goals or its own.

    CUSTOMER = the campaign bids on the account-default goals
    (update_customer_conversion_goal). CAMPAIGN = it bids on its own
    campaign-specific goals (update_campaign_conversion_goal). Switching a live
    campaign changes what it optimises towards immediately.

    Args:
        customer_id: Google Ads customer ID (digits only, no hyphens).
        campaign_id: Numeric campaign id.
        goal_config_level: "CUSTOMER" or "CAMPAIGN".

    Returns:
        resource_name, campaign_id and goal_config_level as read back from the
        API.
    """
    cid = _clean_cid(customer_id)
    camp = _clean_campaign_id(campaign_id)
    level = str(goal_config_level).strip().upper()
    if level not in ("CUSTOMER", "CAMPAIGN"):
        raise ToolError("goal_config_level must be CUSTOMER or CAMPAIGN.")

    client = utils.get_googleads_client()
    resource_name = f"customers/{cid}/conversionGoalCampaignConfigs/{camp}"

    config = utils.get_googleads_type("ConversionGoalCampaignConfig")
    config.resource_name = resource_name
    config.goal_config_level = client.enums.GoalConfigLevelEnum[level]

    operation = utils.get_googleads_type("ConversionGoalCampaignConfigOperation")
    operation.update = config
    operation.update_mask.paths.append("goal_config_level")

    service = client.get_service("ConversionGoalCampaignConfigService")
    try:
        service.mutate_conversion_goal_campaign_configs(
            customer_id=cid, operations=[operation]
        )
    except GoogleAdsException as ex:
        raise ToolError(_format_googleads_error(ex))

    rows = _read_rows(
        cid,
        "SELECT campaign.id, conversion_goal_campaign_config.goal_config_level "
        "FROM conversion_goal_campaign_config "
        f"WHERE campaign.id = {camp}",
    )
    if not rows:
        return {
            "resource_name": resource_name,
            "verified": False,
            "note": "Updated, but the API did not return the row on read-back.",
        }
    return {
        "resource_name": resource_name,
        "campaign_id": camp,
        "goal_config_level": (
            rows[0].conversion_goal_campaign_config.goal_config_level.name
        ),
    }
