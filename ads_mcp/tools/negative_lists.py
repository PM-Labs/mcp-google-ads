"""Tools for managing shared negative keyword lists."""

from typing import Dict, List
from ads_mcp.coordinator import mcp
import ads_mcp.utils as utils
from google.ads.googleads.errors import GoogleAdsException
from fastmcp.exceptions import ToolError

_VALID_MATCH_TYPES = ("EXACT", "PHRASE", "BROAD")


@mcp.tool()
def create_shared_negative_keyword_list(
    customer_id: str,
    name: str,
    keywords: List[Dict[str, str]],
) -> str:
    """Creates a shared negative keyword list and populates it with keywords.

    The list can then be applied to one or more campaigns via apply_shared_negative_list.

    Args:
        customer_id: Google Ads customer ID (digits only, no hyphens).
        name: Name for the shared set (must be unique in the account).
        keywords: List of dicts, each with "text" (str) and "match_type" (EXACT/PHRASE/BROAD).
                  Example: [{"text": "free", "match_type": "BROAD"}]

    Returns:
        Resource name of the created shared set.
    """
    for kw in keywords:
        if kw.get("match_type") not in _VALID_MATCH_TYPES:
            raise ToolError(
                f"Invalid match_type '{kw.get('match_type')}' for keyword '{kw.get('text')}'. "
                f"Must be one of {_VALID_MATCH_TYPES}."
            )

    client = utils.get_googleads_client()
    shared_set_service = utils.get_googleads_service("SharedSetService")
    shared_criterion_service = utils.get_googleads_service("SharedCriterionService")

    # Step 1: Create the shared set
    shared_set = utils.get_googleads_type("SharedSet")
    shared_set.name = name
    shared_set.type_ = client.enums.SharedSetTypeEnum.NEGATIVE_KEYWORDS

    set_operation = utils.get_googleads_type("SharedSetOperation")
    set_operation.create = shared_set

    try:
        set_response = shared_set_service.mutate_shared_sets(
            customer_id=customer_id, operations=[set_operation]
        )
    except GoogleAdsException as ex:
        raise ToolError(
            f"Failed to create shared set. Request ID: {ex.request_id}\n"
            + "\n".join(e.message for e in ex.failure.errors)
        )

    shared_set_resource_name = set_response.results[0].resource_name

    # Step 2: Add keywords to the shared set
    criterion_operations = []
    for kw in keywords:
        criterion = utils.get_googleads_type("SharedCriterion")
        criterion.shared_set = shared_set_resource_name
        criterion.keyword.text = kw["text"]
        criterion.keyword.match_type = getattr(client.enums.KeywordMatchTypeEnum, kw["match_type"])

        op = utils.get_googleads_type("SharedCriterionOperation")
        op.create = criterion
        criterion_operations.append(op)

    try:
        shared_criterion_service.mutate_shared_criteria(
            customer_id=customer_id, operations=criterion_operations
        )
    except GoogleAdsException as ex:
        raise ToolError(
            f"Shared set created ({shared_set_resource_name}) but keyword population failed. "
            f"Request ID: {ex.request_id}\n"
            + "\n".join(e.message for e in ex.failure.errors)
        )

    return shared_set_resource_name


@mcp.tool()
def apply_shared_negative_list(
    customer_id: str,
    campaign_resource_name: str,
    shared_set_resource_name: str,
) -> str:
    """Applies a shared negative keyword list to a campaign.

    Args:
        customer_id: Google Ads customer ID (digits only, no hyphens).
        campaign_resource_name: Campaign resource name from create_campaign.
        shared_set_resource_name: Shared set resource name from create_shared_negative_keyword_list.

    Returns:
        Resource name of the created campaign shared set link.
    """
    service = utils.get_googleads_service("CampaignSharedSetService")

    campaign_shared_set = utils.get_googleads_type("CampaignSharedSet")
    campaign_shared_set.campaign = campaign_resource_name
    campaign_shared_set.shared_set = shared_set_resource_name

    operation = utils.get_googleads_type("CampaignSharedSetOperation")
    operation.create = campaign_shared_set

    try:
        response = service.mutate_campaign_shared_sets(
            customer_id=customer_id, operations=[operation]
        )
        return response.results[0].resource_name
    except GoogleAdsException as ex:
        raise ToolError(
            f"Request ID: {ex.request_id}\n"
            + "\n".join(e.message for e in ex.failure.errors)
        )
