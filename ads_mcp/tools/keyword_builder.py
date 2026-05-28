"""Tools for creating keywords and negative keywords."""

from ads_mcp.coordinator import mcp
import ads_mcp.utils as utils
from google.ads.googleads.errors import GoogleAdsException
from fastmcp.exceptions import ToolError

_VALID_MATCH_TYPES = ("EXACT", "PHRASE", "BROAD")


@mcp.tool()
def create_keyword(
    customer_id: str,
    ad_group_resource_name: str,
    keyword_text: str,
    match_type: str,
) -> str:
    """Creates a positive keyword in an ad group.

    Args:
        customer_id: Google Ads customer ID (digits only, no hyphens).
        ad_group_resource_name: Ad group resource name from create_ad_group.
        keyword_text: The keyword text (e.g. "running shoes").
        match_type: Keyword match type -- "EXACT", "PHRASE", or "BROAD".

    Returns:
        Resource name of the created criterion.
    """
    if match_type not in _VALID_MATCH_TYPES:
        raise ToolError(
            f"match_type must be one of {_VALID_MATCH_TYPES}, got: {match_type}"
        )

    client = utils.get_googleads_client()
    service = utils.get_googleads_service("AdGroupCriterionService")

    criterion = utils.get_googleads_type("AdGroupCriterion")
    criterion.ad_group = ad_group_resource_name
    criterion.keyword.text = keyword_text
    criterion.keyword.match_type = getattr(client.enums.KeywordMatchTypeEnum, match_type)

    operation = utils.get_googleads_type("AdGroupCriterionOperation")
    operation.create = criterion

    try:
        response = service.mutate_ad_group_criteria(
            customer_id=customer_id, operations=[operation]
        )
        return response.results[0].resource_name
    except GoogleAdsException as ex:
        raise ToolError(
            f"Request ID: {ex.request_id}\n"
            + "\n".join(e.message for e in ex.failure.errors)
        )


@mcp.tool()
def create_negative_keyword(
    customer_id: str,
    ad_group_resource_name: str,
    keyword_text: str,
    match_type: str,
) -> str:
    """Creates a negative keyword at the ad group level.

    Args:
        customer_id: Google Ads customer ID (digits only, no hyphens).
        ad_group_resource_name: Ad group resource name from create_ad_group.
        keyword_text: The negative keyword text (e.g. "free").
        match_type: Match type -- "EXACT", "PHRASE", or "BROAD".

    Returns:
        Resource name of the created criterion.
    """
    if match_type not in _VALID_MATCH_TYPES:
        raise ToolError(
            f"match_type must be one of {_VALID_MATCH_TYPES}, got: {match_type}"
        )

    client = utils.get_googleads_client()
    service = utils.get_googleads_service("AdGroupCriterionService")

    criterion = utils.get_googleads_type("AdGroupCriterion")
    criterion.ad_group = ad_group_resource_name
    criterion.negative = True
    criterion.keyword.text = keyword_text
    criterion.keyword.match_type = getattr(client.enums.KeywordMatchTypeEnum, match_type)

    operation = utils.get_googleads_type("AdGroupCriterionOperation")
    operation.create = criterion

    try:
        response = service.mutate_ad_group_criteria(
            customer_id=customer_id, operations=[operation]
        )
        return response.results[0].resource_name
    except GoogleAdsException as ex:
        raise ToolError(
            f"Request ID: {ex.request_id}\n"
            + "\n".join(e.message for e in ex.failure.errors)
        )


@mcp.tool()
def create_campaign_negative_keyword(
    customer_id: str,
    campaign_resource_name: str,
    keyword_text: str,
    match_type: str,
) -> str:
    """Creates a negative keyword at the campaign level (applies across all ad groups).

    Args:
        customer_id: Google Ads customer ID (digits only, no hyphens).
        campaign_resource_name: Campaign resource name from create_campaign.
        keyword_text: The negative keyword text (e.g. "free trial").
        match_type: Match type -- "EXACT", "PHRASE", or "BROAD".

    Returns:
        Resource name of the created campaign criterion.
    """
    if match_type not in _VALID_MATCH_TYPES:
        raise ToolError(
            f"match_type must be one of {_VALID_MATCH_TYPES}, got: {match_type}"
        )

    client = utils.get_googleads_client()
    service = utils.get_googleads_service("CampaignCriterionService")

    criterion = utils.get_googleads_type("CampaignCriterion")
    criterion.campaign = campaign_resource_name
    criterion.negative = True
    criterion.keyword.text = keyword_text
    criterion.keyword.match_type = getattr(client.enums.KeywordMatchTypeEnum, match_type)

    operation = utils.get_googleads_type("CampaignCriterionOperation")
    operation.create = criterion

    try:
        response = service.mutate_campaign_criteria(
            customer_id=customer_id, operations=[operation]
        )
        return response.results[0].resource_name
    except GoogleAdsException as ex:
        raise ToolError(
            f"Request ID: {ex.request_id}\n"
            + "\n".join(e.message for e in ex.failure.errors)
        )
