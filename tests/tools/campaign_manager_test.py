import unittest
from unittest.mock import MagicMock, patch


class TestCampaignManager(unittest.TestCase):

    @patch("ads_mcp.utils.get_googleads_client")
    @patch("ads_mcp.utils.get_googleads_type")
    @patch("ads_mcp.utils.get_googleads_service")
    def test_pause_campaign(self, mock_get_svc, mock_get_type, mock_get_client):
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

        from ads_mcp.tools.campaign_manager import pause_campaign
        result = pause_campaign(
            customer_id="123",
            campaign_resource_name="customers/123/campaigns/789",
        )

        self.assertEqual(result, "customers/123/campaigns/789")
        self.assertEqual(mock_campaign.status, 3)
        self.assertEqual(mock_campaign.resource_name, "customers/123/campaigns/789")
        # Verify field mask contains only "status"
        mock_op.update_mask.paths.extend.assert_called_once_with(["status"])

    @patch("ads_mcp.utils.get_googleads_client")
    @patch("ads_mcp.utils.get_googleads_type")
    @patch("ads_mcp.utils.get_googleads_service")
    def test_remove_keyword(self, mock_get_svc, mock_get_type, mock_get_client):
        mock_service = MagicMock()
        mock_get_svc.return_value = mock_service
        mock_op = MagicMock()
        mock_get_type.return_value = mock_op
        mock_get_client.return_value = MagicMock()
        mock_response = MagicMock()
        mock_response.results[0].resource_name = "customers/123/adGroupCriteria/456~789"
        mock_service.mutate_ad_group_criteria.return_value = mock_response

        from ads_mcp.tools.campaign_manager import remove_keyword
        result = remove_keyword(
            customer_id="123",
            ad_group_criterion_resource_name="customers/123/adGroupCriteria/456~789",
        )

        self.assertEqual(result, "customers/123/adGroupCriteria/456~789")
        self.assertEqual(mock_op.remove, "customers/123/adGroupCriteria/456~789")

    @patch("ads_mcp.utils.get_googleads_client")
    @patch("ads_mcp.utils.get_googleads_type")
    @patch("ads_mcp.utils.get_googleads_service")
    def test_remove_ad(self, mock_get_svc, mock_get_type, mock_get_client):
        mock_service = MagicMock()
        mock_get_svc.return_value = mock_service
        mock_op = MagicMock()
        mock_get_type.return_value = mock_op
        mock_get_client.return_value = MagicMock()
        mock_response = MagicMock()
        mock_response.results[0].resource_name = "customers/123/adGroupAds/222~333"
        mock_service.mutate_ad_group_ads.return_value = mock_response

        from ads_mcp.tools.campaign_manager import remove_ad
        result = remove_ad(
            customer_id="123",
            ad_group_ad_resource_name="customers/123/adGroupAds/222~333",
        )

        self.assertEqual(result, "customers/123/adGroupAds/222~333")
        self.assertEqual(mock_op.remove, "customers/123/adGroupAds/222~333")


if __name__ == "__main__":
    unittest.main()
