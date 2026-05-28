# tests/tools/targeting_test.py
import unittest
from unittest.mock import MagicMock, patch


class TestTargeting(unittest.TestCase):

    @patch("ads_mcp.utils.get_googleads_client")
    @patch("ads_mcp.utils.get_googleads_type")
    @patch("ads_mcp.utils.get_googleads_service")
    def test_add_location_targets(self, mock_get_svc, mock_get_type, mock_get_client):
        mock_service = MagicMock()
        mock_get_svc.return_value = mock_service
        mock_get_type.return_value = MagicMock()
        mock_get_client.return_value = MagicMock()
        mock_response = MagicMock()
        mock_response.results = [
            MagicMock(resource_name="customers/123/campaignCriteria/789~1"),
            MagicMock(resource_name="customers/123/campaignCriteria/789~2"),
        ]
        mock_service.mutate_campaign_criteria.return_value = mock_response

        from ads_mcp.tools.targeting import add_location_targets
        result = add_location_targets(
            customer_id="123",
            campaign_resource_name="customers/123/campaigns/789",
            geo_target_ids=[2036, 2152],
        )

        self.assertEqual(len(result), 2)
        # Two operations should have been sent (one per geo target)
        call_args = mock_service.mutate_campaign_criteria.call_args
        operations = call_args[1]["operations"]
        self.assertEqual(len(operations), 2)

    @patch("ads_mcp.utils.get_googleads_client")
    @patch("ads_mcp.utils.get_googleads_type")
    @patch("ads_mcp.utils.get_googleads_service")
    def test_add_language_targets(self, mock_get_svc, mock_get_type, mock_get_client):
        mock_service = MagicMock()
        mock_get_svc.return_value = mock_service
        mock_get_type.return_value = MagicMock()
        mock_get_client.return_value = MagicMock()
        mock_response = MagicMock()
        mock_response.results = [
            MagicMock(resource_name="customers/123/campaignCriteria/789~10"),
        ]
        mock_service.mutate_campaign_criteria.return_value = mock_response

        from ads_mcp.tools.targeting import add_language_targets
        result = add_language_targets(
            customer_id="123",
            campaign_resource_name="customers/123/campaigns/789",
            language_ids=[1000],
        )

        self.assertEqual(len(result), 1)


if __name__ == "__main__":
    unittest.main()
