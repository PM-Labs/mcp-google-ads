"""Tools for adding targeting criteria to campaigns."""

from typing import List
from ads_mcp.coordinator import mcp
import ads_mcp.utils as utils
from google.ads.googleads.errors import GoogleAdsException
from fastmcp.exceptions import ToolError


@mcp.tool()
def add_location_targets(
    customer_id: str,
    campaign_resource_name: str,
    geo_target_ids: List[int],
    negative: bool = False,
) -> List[str]:
    """Adds location targeting to a campaign.

    To find geo_target_ids, query the geo_target_constant resource via the search tool.
    Common IDs: Australia=2036, United Kingdom=2826, United States=2840.

    Args:
        customer_id: Google Ads customer ID (digits only, no hyphens).
        campaign_resource_name: Campaign resource name from create_campaign.
        geo_target_ids: List of geo target constant IDs to target.
        negative: If True, adds as excluded locations. Default False (included).

    Returns:
        List of resource names of the created campaign criteria.
    """
    service = utils.get_googleads_service("CampaignCriterionService")

    operations = []
    for geo_id in geo_target_ids:
        criterion = utils.get_googleads_type("CampaignCriterion")
        criterion.campaign = campaign_resource_name
        criterion.negative = negative
        criterion.location.geo_target_constant = f"geoTargetConstants/{geo_id}"

        operation = utils.get_googleads_type("CampaignCriterionOperation")
        operation.create = criterion
        operations.append(operation)

    try:
        response = service.mutate_campaign_criteria(
            customer_id=customer_id, operations=operations
        )
        return [r.resource_name for r in response.results]
    except GoogleAdsException as ex:
        raise ToolError(
            f"Request ID: {ex.request_id}\n"
            + "\n".join(e.message for e in ex.failure.errors)
        )


@mcp.tool()
def add_language_targets(
    customer_id: str,
    campaign_resource_name: str,
    language_ids: List[int],
) -> List[str]:
    """Adds language targeting to a campaign.

    To find language_ids, query the language_constant resource via the search tool.
    Common IDs: English=1000, Spanish=1003, French=1002.

    Args:
        customer_id: Google Ads customer ID (digits only, no hyphens).
        campaign_resource_name: Campaign resource name from create_campaign.
        language_ids: List of language constant IDs to target.

    Returns:
        List of resource names of the created campaign criteria.
    """
    service = utils.get_googleads_service("CampaignCriterionService")

    operations = []
    for lang_id in language_ids:
        criterion = utils.get_googleads_type("CampaignCriterion")
        criterion.campaign = campaign_resource_name
        criterion.language.language_constant = f"languageConstants/{lang_id}"

        operation = utils.get_googleads_type("CampaignCriterionOperation")
        operation.create = criterion
        operations.append(operation)

    try:
        response = service.mutate_campaign_criteria(
            customer_id=customer_id, operations=operations
        )
        return [r.resource_name for r in response.results]
    except GoogleAdsException as ex:
        raise ToolError(
            f"Request ID: {ex.request_id}\n"
            + "\n".join(e.message for e in ex.failure.errors)
        )
