# Copyright 2026 Google LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tools for the Google Ads Keyword Plan Idea Service."""

from typing import Any, Dict, List, Optional
from ads_mcp.coordinator import mcp
import ads_mcp.utils as utils
from google.ads.googleads.errors import GoogleAdsException
from fastmcp.exceptions import ToolError


@mcp.tool()
def generate_keyword_ideas(
    customer_id: str,
    keywords: List[str],
    language_id: int,
    geo_target_ids: List[int],
    url: Optional[str] = None,
    include_adult_keywords: bool = False,
) -> List[Dict[str, Any]]:
    """Generates keyword ideas using the Google Ads Keyword Plan Idea Service.

    Returns keyword ideas with search volume, competition, and bid range data.
    Provide either keywords, a url, or both. At least one must be non-empty.

    Args:
        customer_id: Google Ads customer ID (digits only, no hyphens).
        keywords: Seed keywords to generate ideas from (e.g. ["running shoes"]).
        language_id: Language constant ID (e.g. 1000 = English, 1056 = Australian English).
        geo_target_ids: List of geo target constant IDs (e.g. [2036] = Australia).
        url: Optional seed URL. Ideas generated from page content at this URL.
        include_adult_keywords: Whether to include adult keywords. Default False.

    Returns:
        List of dicts with keys: text, avg_monthly_searches, competition,
        low_top_of_page_bid_micros, high_top_of_page_bid_micros.
        Monetary values are in micros (divide by 1,000,000 for dollars).
    """
    if not keywords and not url:
        raise ToolError("Provide at least one of: keywords (non-empty list) or url.")

    service = utils.get_googleads_service("KeywordPlanIdeaService")
    request = utils.get_googleads_type("GenerateKeywordIdeasRequest")

    request.customer_id = customer_id
    request.language = f"languageConstants/{language_id}"
    request.geo_target_constants.extend(
        [f"geoTargetConstants/{g}" for g in geo_target_ids]
    )
    request.include_adult_keywords = include_adult_keywords

    if keywords and url:
        request.keyword_and_url_seed.keywords.extend(keywords)
        request.keyword_and_url_seed.url = url
    elif keywords:
        request.keyword_seed.keywords.extend(keywords)
    else:
        request.url_seed.url = url

    try:
        response = service.generate_keyword_ideas(request=request)
        return [
            {
                "text": idea.text,
                "avg_monthly_searches": idea.keyword_idea_metrics.avg_monthly_searches,
                "competition": idea.keyword_idea_metrics.competition.name,
                "low_top_of_page_bid_micros": idea.keyword_idea_metrics.low_top_of_page_bid_micros,
                "high_top_of_page_bid_micros": idea.keyword_idea_metrics.high_top_of_page_bid_micros,
            }
            for idea in response
        ]
    except GoogleAdsException as ex:
        raise ToolError(
            f"Request ID: {ex.request_id}\n"
            + "\n".join(e.message for e in ex.failure.errors)
        )


@mcp.tool()
def generate_keyword_historical_metrics(
    customer_id: str,
    keywords: List[str],
    language_id: int,
    geo_target_ids: List[int],
) -> List[Dict[str, Any]]:
    """Returns historical search metrics for a specific list of keywords.

    Use this when you already have a keyword list and want volume/competition
    data for each, rather than generating new ideas.

    Args:
        customer_id: Google Ads customer ID (digits only, no hyphens).
        keywords: Exact keyword strings to fetch metrics for.
        language_id: Language constant ID (e.g. 1000 = English).
        geo_target_ids: List of geo target constant IDs (e.g. [2036] = Australia).

    Returns:
        List of dicts with keys: text, avg_monthly_searches, competition,
        low_top_of_page_bid_micros, high_top_of_page_bid_micros.
    """
    service = utils.get_googleads_service("KeywordPlanIdeaService")
    request = utils.get_googleads_type("GenerateKeywordHistoricalMetricsRequest")

    request.customer_id = customer_id
    request.keywords.extend(keywords)
    request.language = f"languageConstants/{language_id}"
    request.geo_target_constants.extend(
        [f"geoTargetConstants/{g}" for g in geo_target_ids]
    )

    try:
        response = service.generate_keyword_historical_metrics(request=request)
        return [
            {
                "text": result.text,
                "avg_monthly_searches": result.keyword_metrics.avg_monthly_searches,
                "competition": result.keyword_metrics.competition.name,
                "low_top_of_page_bid_micros": result.keyword_metrics.low_top_of_page_bid_micros,
                "high_top_of_page_bid_micros": result.keyword_metrics.high_top_of_page_bid_micros,
            }
            for result in response.results
        ]
    except GoogleAdsException as ex:
        raise ToolError(
            f"Request ID: {ex.request_id}\n"
            + "\n".join(e.message for e in ex.failure.errors)
        )


@mcp.tool()
def generate_ad_group_themes(
    customer_id: str,
    keywords: List[str],
    language_id: int,
    geo_target_ids: List[int],
) -> List[Dict[str, Any]]:
    """Groups a keyword list into suggested ad group themes.

    Useful for structuring a large keyword list into logical ad groups before building.

    Args:
        customer_id: Google Ads customer ID (digits only, no hyphens).
        keywords: Full keyword list to cluster into themes.
        language_id: Language constant ID (e.g. 1000 = English).
        geo_target_ids: List of geo target constant IDs (e.g. [2036] = Australia).

    Returns:
        List of dicts with keys: display_name, keywords (list of strings in this theme).
    """
    service = utils.get_googleads_service("KeywordPlanIdeaService")
    request = utils.get_googleads_type("GenerateAdGroupThemesRequest")

    request.customer_id = customer_id
    request.keywords.extend(keywords)
    request.language = f"languageConstants/{language_id}"
    request.geo_target_constants.extend(
        [f"geoTargetConstants/{g}" for g in geo_target_ids]
    )

    try:
        response = service.generate_ad_group_themes(request=request)
        return [
            {
                "display_name": theme.display_name,
                "keywords": list(theme.keywords),
            }
            for theme in response.ad_group_themes
        ]
    except GoogleAdsException as ex:
        raise ToolError(
            f"Request ID: {ex.request_id}\n"
            + "\n".join(e.message for e in ex.failure.errors)
        )
