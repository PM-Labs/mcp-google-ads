"""Tools for building Google Ads campaign structure.

SAFETY INVARIANTS (enforced in code, not parameters):
- All create operations set status=PAUSED. Status is not a parameter.
- No enable operations exist.
- No budget or bid update operations exist.
- Bidding strategy is hardcoded to maximize_clicks (no manual bids required).
"""

from typing import List, Optional
from ads_mcp.coordinator import mcp
import ads_mcp.utils as utils
from google.ads.googleads.errors import GoogleAdsException
from fastmcp.exceptions import ToolError


@mcp.tool()
def create_campaign_budget(
    customer_id: str,
    name: str,
    amount_micros: int,
    shared: bool = False,
) -> str:
    """Creates a campaign budget. Returns the budget resource name.

    Note: amount_micros is in micros (1,000,000 micros = $1.00).
    For a $10/day budget, use amount_micros=10000000.

    Args:
        customer_id: Google Ads customer ID (digits only, no hyphens).
        name: Budget name (must be unique within the account).
        amount_micros: Daily budget in micros (e.g. 10000000 = $10/day).
        shared: Whether this budget can be shared across campaigns. Default False.

    Returns:
        Resource name of the created budget (e.g. "customers/123/campaignBudgets/456").
    """
    client = utils.get_googleads_client()
    service = utils.get_googleads_service("CampaignBudgetService")

    budget = utils.get_googleads_type("CampaignBudget")
    budget.name = name
    budget.amount_micros = amount_micros
    budget.delivery_method = client.enums.BudgetDeliveryMethodEnum.STANDARD
    budget.explicitly_shared = shared

    operation = utils.get_googleads_type("CampaignBudgetOperation")
    operation.create = budget

    try:
        response = service.mutate_campaign_budgets(
            customer_id=customer_id, operations=[operation]
        )
        return response.results[0].resource_name
    except GoogleAdsException as ex:
        raise ToolError(
            f"Request ID: {ex.request_id}\n"
            + "\n".join(e.message for e in ex.failure.errors)
        )


@mcp.tool()
def create_campaign(
    customer_id: str,
    name: str,
    budget_resource_name: str,
    advertising_channel_type: str = "SEARCH",
) -> str:
    """Creates a new campaign. Status is always PAUSED — enable in the UI after review.

    Bidding strategy is set to Maximize Clicks (no manual bid required).
    Supports SEARCH and DISPLAY channel types.

    Args:
        customer_id: Google Ads customer ID (digits only, no hyphens).
        name: Campaign name (must be unique within the account).
        budget_resource_name: Budget resource name from create_campaign_budget.
        advertising_channel_type: "SEARCH" or "DISPLAY". Default "SEARCH".

    Returns:
        Resource name of the created campaign (e.g. "customers/123/campaigns/789").
    """
    if advertising_channel_type not in ("SEARCH", "DISPLAY"):
        raise ToolError(
            f"advertising_channel_type must be SEARCH or DISPLAY, got: {advertising_channel_type}"
        )

    client = utils.get_googleads_client()
    service = utils.get_googleads_service("CampaignService")

    campaign = utils.get_googleads_type("Campaign")
    campaign.name = name
    campaign.status = client.enums.CampaignStatusEnum.PAUSED  # HARDCODED — never ENABLED
    campaign.advertising_channel_type = client.enums.AdvertisingChannelTypeEnum[
        advertising_channel_type
    ]
    campaign.campaign_budget = budget_resource_name
    campaign.maximize_clicks = utils.get_googleads_type("MaximizeClicks")

    operation = utils.get_googleads_type("CampaignOperation")
    operation.create = campaign

    try:
        response = service.mutate_campaigns(
            customer_id=customer_id, operations=[operation]
        )
        return response.results[0].resource_name
    except GoogleAdsException as ex:
        raise ToolError(
            f"Request ID: {ex.request_id}\n"
            + "\n".join(e.message for e in ex.failure.errors)
        )


@mcp.tool()
def create_ad_group(
    customer_id: str,
    name: str,
    campaign_resource_name: str,
) -> str:
    """Creates a new ad group. Status is always PAUSED — enable in the UI after review.

    Args:
        customer_id: Google Ads customer ID (digits only, no hyphens).
        name: Ad group name.
        campaign_resource_name: Campaign resource name from create_campaign.

    Returns:
        Resource name of the created ad group (e.g. "customers/123/adGroups/111").
    """
    client = utils.get_googleads_client()
    service = utils.get_googleads_service("AdGroupService")

    ad_group = utils.get_googleads_type("AdGroup")
    ad_group.name = name
    ad_group.status = client.enums.AdGroupStatusEnum.PAUSED  # HARDCODED — never ENABLED
    ad_group.campaign = campaign_resource_name
    ad_group.type_ = client.enums.AdGroupTypeEnum.SEARCH_STANDARD

    operation = utils.get_googleads_type("AdGroupOperation")
    operation.create = ad_group

    try:
        response = service.mutate_ad_groups(
            customer_id=customer_id, operations=[operation]
        )
        return response.results[0].resource_name
    except GoogleAdsException as ex:
        raise ToolError(
            f"Request ID: {ex.request_id}\n"
            + "\n".join(e.message for e in ex.failure.errors)
        )


@mcp.tool()
def create_responsive_search_ad(
    customer_id: str,
    ad_group_resource_name: str,
    headlines: List[str],
    descriptions: List[str],
    final_urls: List[str],
    path1: Optional[str] = None,
    path2: Optional[str] = None,
) -> str:
    """Creates a Responsive Search Ad. Status is always PAUSED — enable in the UI after review.

    Google uses the headlines and descriptions to auto-assemble the best combinations.
    Provide 3-15 unique headlines and 2-4 unique descriptions.

    Args:
        customer_id: Google Ads customer ID (digits only, no hyphens).
        ad_group_resource_name: Ad group resource name from create_ad_group.
        headlines: 3-15 headline strings (max 30 chars each).
        descriptions: 2-4 description strings (max 90 chars each).
        final_urls: Landing page URLs (at least one required).
        path1: Optional first display path (max 15 chars).
        path2: Optional second display path (max 15 chars, requires path1).

    Returns:
        Resource name of the created ad (e.g. "customers/123/adGroupAds/222~333").
    """
    if len(headlines) < 3 or len(headlines) > 15:
        raise ToolError(f"headlines must have 3-15 items, got {len(headlines)}.")
    if len(descriptions) < 2 or len(descriptions) > 4:
        raise ToolError(f"descriptions must have 2-4 items, got {len(descriptions)}.")
    if not final_urls:
        raise ToolError("At least one final_url is required.")
    if path2 and not path1:
        raise ToolError("path1 is required when path2 is provided.")

    client = utils.get_googleads_client()
    service = utils.get_googleads_service("AdGroupAdService")

    ad_group_ad = utils.get_googleads_type("AdGroupAd")
    ad_group_ad.status = client.enums.AdGroupAdStatusEnum.PAUSED  # HARDCODED — never ENABLED
    ad_group_ad.ad_group = ad_group_resource_name

    rsa = utils.get_googleads_type("ResponsiveSearchAdInfo")
    for text in headlines:
        asset = utils.get_googleads_type("AdTextAsset")
        asset.text = text
        rsa.headlines.append(asset)
    for text in descriptions:
        asset = utils.get_googleads_type("AdTextAsset")
        asset.text = text
        rsa.descriptions.append(asset)

    ad_group_ad.ad.responsive_search_ad = rsa
    ad_group_ad.ad.final_urls.extend(final_urls)

    if path1:
        ad_group_ad.ad.path1 = path1
    if path2:
        ad_group_ad.ad.path2 = path2

    operation = utils.get_googleads_type("AdGroupAdOperation")
    operation.create = ad_group_ad

    try:
        response = service.mutate_ad_group_ads(
            customer_id=customer_id, operations=[operation]
        )
        return response.results[0].resource_name
    except GoogleAdsException as ex:
        raise ToolError(
            f"Request ID: {ex.request_id}\n"
            + "\n".join(e.message for e in ex.failure.errors)
        )
