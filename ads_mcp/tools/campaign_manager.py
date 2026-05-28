"""Tools for managing existing Google Ads entities.

SAFETY INVARIANTS:
- Only pause operations exist. No enable/activate operations.
- Remove operations are permanent — data is retained but entity is gone.
- No bid or budget changes.
"""

from ads_mcp.coordinator import mcp
import ads_mcp.utils as utils
from google.ads.googleads.errors import GoogleAdsException
from fastmcp.exceptions import ToolError


@mcp.tool()
def pause_campaign(customer_id: str, campaign_resource_name: str) -> str:
    """Pauses an existing campaign. Cannot be used to enable — use the Google Ads UI to enable.

    Args:
        customer_id: Google Ads customer ID (digits only, no hyphens).
        campaign_resource_name: Campaign resource name (e.g. "customers/123/campaigns/789").

    Returns:
        Resource name of the updated campaign.
    """
    client = utils.get_googleads_client()
    service = utils.get_googleads_service("CampaignService")

    campaign = utils.get_googleads_type("Campaign")
    campaign.resource_name = campaign_resource_name
    campaign.status = client.enums.CampaignStatusEnum.PAUSED

    operation = utils.get_googleads_type("CampaignOperation")
    operation.update = campaign
    operation.update_mask.paths.extend(["status"])

    try:
        response = service.mutate_campaigns(customer_id=customer_id, operations=[operation])
        return response.results[0].resource_name
    except GoogleAdsException as ex:
        raise ToolError(
            f"Request ID: {ex.request_id}\n"
            + "\n".join(e.message for e in ex.failure.errors)
        )


@mcp.tool()
def pause_ad_group(customer_id: str, ad_group_resource_name: str) -> str:
    """Pauses an existing ad group. Cannot be used to enable — use the Google Ads UI to enable.

    Args:
        customer_id: Google Ads customer ID (digits only, no hyphens).
        ad_group_resource_name: Ad group resource name (e.g. "customers/123/adGroups/111").

    Returns:
        Resource name of the updated ad group.
    """
    client = utils.get_googleads_client()
    service = utils.get_googleads_service("AdGroupService")

    ad_group = utils.get_googleads_type("AdGroup")
    ad_group.resource_name = ad_group_resource_name
    ad_group.status = client.enums.AdGroupStatusEnum.PAUSED

    operation = utils.get_googleads_type("AdGroupOperation")
    operation.update = ad_group
    operation.update_mask.paths.extend(["status"])

    try:
        response = service.mutate_ad_groups(customer_id=customer_id, operations=[operation])
        return response.results[0].resource_name
    except GoogleAdsException as ex:
        raise ToolError(
            f"Request ID: {ex.request_id}\n"
            + "\n".join(e.message for e in ex.failure.errors)
        )


@mcp.tool()
def pause_ad(customer_id: str, ad_group_ad_resource_name: str) -> str:
    """Pauses an individual ad. Cannot be used to enable — use the Google Ads UI to enable.

    Args:
        customer_id: Google Ads customer ID (digits only, no hyphens).
        ad_group_ad_resource_name: AdGroupAd resource name (e.g. "customers/123/adGroupAds/111~222").

    Returns:
        Resource name of the updated ad.
    """
    client = utils.get_googleads_client()
    service = utils.get_googleads_service("AdGroupAdService")

    ad_group_ad = utils.get_googleads_type("AdGroupAd")
    ad_group_ad.resource_name = ad_group_ad_resource_name
    ad_group_ad.status = client.enums.AdGroupAdStatusEnum.PAUSED

    operation = utils.get_googleads_type("AdGroupAdOperation")
    operation.update = ad_group_ad
    operation.update_mask.paths.extend(["status"])

    try:
        response = service.mutate_ad_group_ads(customer_id=customer_id, operations=[operation])
        return response.results[0].resource_name
    except GoogleAdsException as ex:
        raise ToolError(
            f"Request ID: {ex.request_id}\n"
            + "\n".join(e.message for e in ex.failure.errors)
        )


@mcp.tool()
def pause_keyword(customer_id: str, ad_group_criterion_resource_name: str) -> str:
    """Pauses a keyword. Cannot be used to enable — use the Google Ads UI to enable.

    Args:
        customer_id: Google Ads customer ID (digits only, no hyphens).
        ad_group_criterion_resource_name: Criterion resource name (e.g. "customers/123/adGroupCriteria/111~222").

    Returns:
        Resource name of the updated criterion.
    """
    client = utils.get_googleads_client()
    service = utils.get_googleads_service("AdGroupCriterionService")

    criterion = utils.get_googleads_type("AdGroupCriterion")
    criterion.resource_name = ad_group_criterion_resource_name
    criterion.status = client.enums.AdGroupCriterionStatusEnum.PAUSED

    operation = utils.get_googleads_type("AdGroupCriterionOperation")
    operation.update = criterion
    operation.update_mask.paths.extend(["status"])

    try:
        response = service.mutate_ad_group_criteria(customer_id=customer_id, operations=[operation])
        return response.results[0].resource_name
    except GoogleAdsException as ex:
        raise ToolError(
            f"Request ID: {ex.request_id}\n"
            + "\n".join(e.message for e in ex.failure.errors)
        )


@mcp.tool()
def remove_keyword(customer_id: str, ad_group_criterion_resource_name: str) -> str:
    """Permanently removes a keyword from an ad group.

    WARNING: Removal is permanent. The keyword cannot be re-enabled — create a new one instead.
    Historical data is retained in reports. Use pause_keyword if unsure.

    Args:
        customer_id: Google Ads customer ID (digits only, no hyphens).
        ad_group_criterion_resource_name: Criterion resource name to remove.

    Returns:
        Resource name of the removed criterion.
    """
    service = utils.get_googleads_service("AdGroupCriterionService")

    operation = utils.get_googleads_type("AdGroupCriterionOperation")
    operation.remove = ad_group_criterion_resource_name

    try:
        response = service.mutate_ad_group_criteria(customer_id=customer_id, operations=[operation])
        return response.results[0].resource_name
    except GoogleAdsException as ex:
        raise ToolError(
            f"Request ID: {ex.request_id}\n"
            + "\n".join(e.message for e in ex.failure.errors)
        )


@mcp.tool()
def remove_ad(customer_id: str, ad_group_ad_resource_name: str) -> str:
    """Permanently removes an ad from an ad group.

    WARNING: Removal is permanent. Historical data is retained. Use pause_ad if unsure.

    Args:
        customer_id: Google Ads customer ID (digits only, no hyphens).
        ad_group_ad_resource_name: AdGroupAd resource name to remove.

    Returns:
        Resource name of the removed ad.
    """
    service = utils.get_googleads_service("AdGroupAdService")

    operation = utils.get_googleads_type("AdGroupAdOperation")
    operation.remove = ad_group_ad_resource_name

    try:
        response = service.mutate_ad_group_ads(customer_id=customer_id, operations=[operation])
        return response.results[0].resource_name
    except GoogleAdsException as ex:
        raise ToolError(
            f"Request ID: {ex.request_id}\n"
            + "\n".join(e.message for e in ex.failure.errors)
        )
