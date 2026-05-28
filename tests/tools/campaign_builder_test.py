import unittest
from unittest.mock import MagicMock, patch


class TestCampaignBuilder(unittest.TestCase):

    @patch("ads_mcp.utils.get_googleads_client")
    @patch("ads_mcp.utils.get_googleads_type")
    @patch("ads_mcp.utils.get_googleads_service")
    def test_create_campaign_budget(self, mock_get_svc, mock_get_type, mock_get_client):
        mock_service = MagicMock()
        mock_get_svc.return_value = mock_service
        mock_budget = MagicMock()
        mock_op = MagicMock()
        mock_get_type.side_effect = lambda n: mock_budget if n == "CampaignBudget" else mock_op
        mock_response = MagicMock()
        mock_response.results[0].resource_name = "customers/123/campaignBudgets/456"
        mock_service.mutate_campaign_budgets.return_value = mock_response

        from ads_mcp.tools.campaign_builder import create_campaign_budget
        result = create_campaign_budget(
            customer_id="123",
            name="Test Budget",
            amount_micros=10_000_000,
        )

        self.assertEqual(result, "customers/123/campaignBudgets/456")
        self.assertEqual(mock_budget.amount_micros, 10_000_000)
        self.assertEqual(mock_budget.name, "Test Budget")

    @patch("ads_mcp.utils.get_googleads_client")
    @patch("ads_mcp.utils.get_googleads_type")
    @patch("ads_mcp.utils.get_googleads_service")
    def test_create_campaign_always_paused(self, mock_get_svc, mock_get_type, mock_get_client):
        mock_service = MagicMock()
        mock_get_svc.return_value = mock_service
        mock_campaign = MagicMock()
        mock_op = MagicMock()
        mock_get_type.side_effect = lambda n: mock_campaign if n == "Campaign" else mock_op
        mock_client = MagicMock()
        mock_client.enums.CampaignStatusEnum.PAUSED = 3
        mock_get_client.return_value = mock_client
        mock_response = MagicMock()
        mock_response.results[0].resource_name = "customers/123/campaigns/789"
        mock_service.mutate_campaigns.return_value = mock_response

        from ads_mcp.tools.campaign_builder import create_campaign
        create_campaign(
            customer_id="123",
            name="Test Campaign",
            budget_resource_name="customers/123/campaignBudgets/456",
        )

        # CRITICAL: status must always be PAUSED regardless of input
        self.assertEqual(mock_campaign.status, 3)

    @patch("ads_mcp.utils.get_googleads_client")
    @patch("ads_mcp.utils.get_googleads_type")
    @patch("ads_mcp.utils.get_googleads_service")
    def test_create_ad_group_always_paused(self, mock_get_svc, mock_get_type, mock_get_client):
        mock_service = MagicMock()
        mock_get_svc.return_value = mock_service
        mock_ad_group = MagicMock()
        mock_op = MagicMock()
        mock_get_type.side_effect = lambda n: mock_ad_group if n == "AdGroup" else mock_op
        mock_client = MagicMock()
        mock_client.enums.AdGroupStatusEnum.PAUSED = 3
        mock_get_client.return_value = mock_client
        mock_response = MagicMock()
        mock_response.results[0].resource_name = "customers/123/adGroups/111"
        mock_service.mutate_ad_groups.return_value = mock_response

        from ads_mcp.tools.campaign_builder import create_ad_group
        create_ad_group(
            customer_id="123",
            name="Test Ad Group",
            campaign_resource_name="customers/123/campaigns/789",
        )

        self.assertEqual(mock_ad_group.status, 3)

    @patch("ads_mcp.utils.get_googleads_client")
    @patch("ads_mcp.utils.get_googleads_type")
    @patch("ads_mcp.utils.get_googleads_service")
    def test_create_rsa_always_paused(self, mock_get_svc, mock_get_type, mock_get_client):
        mock_service = MagicMock()
        mock_get_svc.return_value = mock_service
        mock_ad_group_ad = MagicMock()
        mock_op = MagicMock()
        mock_get_type.side_effect = (
            lambda n: mock_ad_group_ad if n == "AdGroupAd" else mock_op
        )
        mock_client = MagicMock()
        mock_client.enums.AdGroupAdStatusEnum.PAUSED = 3
        mock_get_client.return_value = mock_client
        mock_response = MagicMock()
        mock_response.results[0].resource_name = "customers/123/adGroupAds/222"
        mock_service.mutate_ad_group_ads.return_value = mock_response

        from ads_mcp.tools.campaign_builder import create_responsive_search_ad
        create_responsive_search_ad(
            customer_id="123",
            ad_group_resource_name="customers/123/adGroups/111",
            headlines=["Headline 1", "Headline 2", "Headline 3"],
            descriptions=["Description 1", "Description 2"],
            final_urls=["https://example.com"],
        )

        self.assertEqual(mock_ad_group_ad.status, 3)

    @patch("ads_mcp.utils.get_googleads_client")
    @patch("ads_mcp.utils.get_googleads_type")
    @patch("ads_mcp.utils.get_googleads_service")
    def test_create_rsa_validates_headlines(self, mock_get_svc, mock_get_type, mock_get_client):
        mock_get_svc.return_value = MagicMock()
        mock_get_type.return_value = MagicMock()
        mock_get_client.return_value = MagicMock()

        from ads_mcp.tools.campaign_builder import create_responsive_search_ad
        from fastmcp.exceptions import ToolError

        with self.assertRaises(ToolError):
            create_responsive_search_ad(
                customer_id="123",
                ad_group_resource_name="customers/123/adGroups/111",
                headlines=["Only One Headline"],  # minimum 3
                descriptions=["Desc 1", "Desc 2"],
                final_urls=["https://example.com"],
            )

    @patch("ads_mcp.utils.get_googleads_client")
    @patch("ads_mcp.utils.get_googleads_type")
    @patch("ads_mcp.utils.get_googleads_service")
    def test_create_campaign_google_ads_exception(self, mock_get_svc, mock_get_type, mock_get_client):
        from google.ads.googleads.errors import GoogleAdsException
        from fastmcp.exceptions import ToolError

        mock_service = MagicMock()
        mock_get_svc.return_value = mock_service
        mock_get_type.return_value = MagicMock()
        mock_get_client.return_value = MagicMock()

        mock_error = MagicMock()
        mock_error.message = "Campaign name already in use"
        mock_failure = MagicMock()
        mock_failure.errors = [mock_error]
        ex = GoogleAdsException(MagicMock(), MagicMock(), MagicMock(), MagicMock())
        ex.failure = mock_failure
        ex.request_id = "req-abc"
        mock_service.mutate_campaigns.side_effect = ex

        from ads_mcp.tools.campaign_builder import create_campaign
        with self.assertRaises(ToolError) as ctx:
            create_campaign(
                customer_id="123",
                name="Duplicate Name",
                budget_resource_name="customers/123/campaignBudgets/456",
            )

        self.assertIn("Campaign name already in use", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
