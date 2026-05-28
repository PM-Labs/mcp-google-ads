"""Tools for creating ad extensions (assets) and linking them to campaigns."""

from typing import Optional
from ads_mcp.coordinator import mcp
import ads_mcp.utils as utils
from google.ads.googleads.errors import GoogleAdsException
from fastmcp.exceptions import ToolError


def _link_asset_to_campaign(
    customer_id: str,
    asset_resource_name: str,
    campaign_resource_name: str,
    field_type_enum_value,
) -> None:
    """Links an asset to a campaign."""
    service = utils.get_googleads_service("CampaignAssetService")

    campaign_asset = utils.get_googleads_type("CampaignAsset")
    campaign_asset.asset = asset_resource_name
    campaign_asset.campaign = campaign_resource_name
    campaign_asset.field_type = field_type_enum_value

    operation = utils.get_googleads_type("CampaignAssetOperation")
    operation.create = campaign_asset

    try:
        service.mutate_campaign_assets(customer_id=customer_id, operations=[operation])
    except GoogleAdsException as ex:
        raise ToolError(
            f"Asset created ({asset_resource_name}) but campaign link failed. "
            f"Request ID: {ex.request_id}\n"
            + "\n".join(e.message for e in ex.failure.errors)
        )


@mcp.tool()
def create_sitelink(
    customer_id: str,
    campaign_resource_name: str,
    link_text: str,
    final_url: str,
    description1: Optional[str] = None,
    description2: Optional[str] = None,
) -> str:
    """Creates a sitelink asset and links it to a campaign.

    The sitelink appears beneath the main ad in search results. The campaign must
    be paused or enabled — sitelinks only show on live campaigns.

    Args:
        customer_id: Google Ads customer ID (digits only, no hyphens).
        campaign_resource_name: Campaign resource name from create_campaign.
        link_text: The anchor text for the sitelink (max 25 chars).
        final_url: Landing page URL for this sitelink.
        description1: Optional first description line (max 35 chars).
        description2: Optional second description line (max 35 chars, requires description1).

    Returns:
        Resource name of the created asset.
    """
    if description2 and not description1:
        raise ToolError("description1 is required when description2 is provided.")

    client = utils.get_googleads_client()
    asset_service = utils.get_googleads_service("AssetService")

    asset = utils.get_googleads_type("Asset")
    asset.sitelink_asset.link_text = link_text
    asset.sitelink_asset.final_urls.append(final_url)
    if description1:
        asset.sitelink_asset.description1 = description1
    if description2:
        asset.sitelink_asset.description2 = description2

    operation = utils.get_googleads_type("AssetOperation")
    operation.create = asset

    try:
        response = asset_service.mutate_assets(
            customer_id=customer_id, operations=[operation]
        )
    except GoogleAdsException as ex:
        raise ToolError(
            f"Request ID: {ex.request_id}\n"
            + "\n".join(e.message for e in ex.failure.errors)
        )

    asset_resource_name = response.results[0].resource_name
    _link_asset_to_campaign(
        customer_id,
        asset_resource_name,
        campaign_resource_name,
        client.enums.AssetFieldTypeEnum.SITELINK,
    )
    return asset_resource_name


@mcp.tool()
def create_callout(
    customer_id: str,
    campaign_resource_name: str,
    callout_text: str,
) -> str:
    """Creates a callout asset and links it to a campaign.

    Callouts are short phrases that appear in ads to highlight features or offers
    (e.g. "Free Shipping", "24/7 Support"). Max 25 characters.

    Args:
        customer_id: Google Ads customer ID (digits only, no hyphens).
        campaign_resource_name: Campaign resource name from create_campaign.
        callout_text: Short callout phrase (max 25 chars).

    Returns:
        Resource name of the created asset.
    """
    client = utils.get_googleads_client()
    asset_service = utils.get_googleads_service("AssetService")

    asset = utils.get_googleads_type("Asset")
    asset.callout_asset.callout_text = callout_text

    operation = utils.get_googleads_type("AssetOperation")
    operation.create = asset

    try:
        response = asset_service.mutate_assets(
            customer_id=customer_id, operations=[operation]
        )
    except GoogleAdsException as ex:
        raise ToolError(
            f"Request ID: {ex.request_id}\n"
            + "\n".join(e.message for e in ex.failure.errors)
        )

    asset_resource_name = response.results[0].resource_name
    _link_asset_to_campaign(
        customer_id,
        asset_resource_name,
        campaign_resource_name,
        client.enums.AssetFieldTypeEnum.CALLOUT,
    )
    return asset_resource_name
