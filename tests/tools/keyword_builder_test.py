import unittest
from unittest.mock import MagicMock, patch


class TestKeywordBuilder(unittest.TestCase):

    @patch("ads_mcp.utils.get_googleads_client")
    @patch("ads_mcp.utils.get_googleads_type")
    @patch("ads_mcp.utils.get_googleads_service")
    def test_create_keyword_exact_match(self, mock_get_svc, mock_get_type, mock_get_client):
        mock_service = MagicMock()
        mock_get_svc.return_value = mock_service
        mock_criterion = MagicMock()
        mock_get_type.side_effect = (
            lambda n: mock_criterion if n == "AdGroupCriterion" else MagicMock()
        )
        mock_client = MagicMock()
        mock_client.enums.KeywordMatchTypeEnum.EXACT = 3
        mock_get_client.return_value = mock_client
        mock_response = MagicMock()
        mock_response.results[0].resource_name = "customers/123/adGroupCriteria/456~789"
        mock_service.mutate_ad_group_criteria.return_value = mock_response

        from ads_mcp.tools.keyword_builder import create_keyword
        result = create_keyword(
            customer_id="123",
            ad_group_resource_name="customers/123/adGroups/456",
            keyword_text="running shoes",
            match_type="EXACT",
        )

        self.assertEqual(result, "customers/123/adGroupCriteria/456~789")
        self.assertEqual(mock_criterion.keyword.text, "running shoes")
        self.assertEqual(mock_criterion.keyword.match_type, 3)

    @patch("ads_mcp.utils.get_googleads_client")
    @patch("ads_mcp.utils.get_googleads_type")
    @patch("ads_mcp.utils.get_googleads_service")
    def test_create_keyword_invalid_match_type(self, mock_get_svc, mock_get_type, mock_get_client):
        mock_get_svc.return_value = MagicMock()
        mock_get_type.return_value = MagicMock()
        mock_get_client.return_value = MagicMock()

        from ads_mcp.tools.keyword_builder import create_keyword
        from fastmcp.exceptions import ToolError

        with self.assertRaises(ToolError):
            create_keyword(
                customer_id="123",
                ad_group_resource_name="customers/123/adGroups/456",
                keyword_text="running shoes",
                match_type="INVALID",
            )

    @patch("ads_mcp.utils.get_googleads_client")
    @patch("ads_mcp.utils.get_googleads_type")
    @patch("ads_mcp.utils.get_googleads_service")
    def test_create_negative_keyword(self, mock_get_svc, mock_get_type, mock_get_client):
        mock_service = MagicMock()
        mock_get_svc.return_value = mock_service
        mock_criterion = MagicMock()
        mock_get_type.side_effect = (
            lambda n: mock_criterion if n == "AdGroupCriterion" else MagicMock()
        )
        mock_get_client.return_value = MagicMock()
        mock_response = MagicMock()
        mock_response.results[0].resource_name = "customers/123/adGroupCriteria/456~999"
        mock_service.mutate_ad_group_criteria.return_value = mock_response

        from ads_mcp.tools.keyword_builder import create_negative_keyword
        result = create_negative_keyword(
            customer_id="123",
            ad_group_resource_name="customers/123/adGroups/456",
            keyword_text="free",
            match_type="BROAD",
        )

        self.assertEqual(result, "customers/123/adGroupCriteria/456~999")
        # Verify negative flag is set
        self.assertEqual(mock_criterion.negative, True)

    @patch("ads_mcp.utils.get_googleads_client")
    @patch("ads_mcp.utils.get_googleads_type")
    @patch("ads_mcp.utils.get_googleads_service")
    def test_create_campaign_negative_keyword(self, mock_get_svc, mock_get_type, mock_get_client):
        mock_service = MagicMock()
        mock_get_svc.return_value = mock_service
        mock_criterion = MagicMock()
        mock_get_type.side_effect = (
            lambda n: mock_criterion if n == "CampaignCriterion" else MagicMock()
        )
        mock_get_client.return_value = MagicMock()
        mock_response = MagicMock()
        mock_response.results[0].resource_name = "customers/123/campaignCriteria/789~1"
        mock_service.mutate_campaign_criteria.return_value = mock_response

        from ads_mcp.tools.keyword_builder import create_campaign_negative_keyword
        result = create_campaign_negative_keyword(
            customer_id="123",
            campaign_resource_name="customers/123/campaigns/789",
            keyword_text="free trial",
            match_type="PHRASE",
        )

        self.assertEqual(result, "customers/123/campaignCriteria/789~1")
        self.assertEqual(mock_criterion.negative, True)


if __name__ == "__main__":
    unittest.main()
