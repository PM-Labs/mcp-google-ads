# tests/tools/negative_lists_test.py
import unittest
from unittest.mock import MagicMock, patch


class TestNegativeLists(unittest.TestCase):

    @patch("ads_mcp.utils.get_googleads_client")
    @patch("ads_mcp.utils.get_googleads_type")
    @patch("ads_mcp.utils.get_googleads_service")
    def test_create_shared_negative_keyword_list(self, mock_get_svc, mock_get_type, mock_get_client):
        mock_shared_set_svc = MagicMock()
        mock_shared_criterion_svc = MagicMock()
        mock_get_svc.side_effect = lambda n: (
            mock_shared_set_svc if n == "SharedSetService" else mock_shared_criterion_svc
        )
        mock_get_type.return_value = MagicMock()
        mock_client = MagicMock()
        mock_client.enums.SharedSetTypeEnum.NEGATIVE_KEYWORDS = 2
        mock_get_client.return_value = mock_client

        mock_set_response = MagicMock()
        mock_set_response.results[0].resource_name = "customers/123/sharedSets/999"
        mock_shared_set_svc.mutate_shared_sets.return_value = mock_set_response

        from ads_mcp.tools.negative_lists import create_shared_negative_keyword_list
        result = create_shared_negative_keyword_list(
            customer_id="123",
            name="Brand Negatives",
            keywords=[
                {"text": "free", "match_type": "BROAD"},
                {"text": "cheap", "match_type": "BROAD"},
            ],
        )

        self.assertEqual(result, "customers/123/sharedSets/999")
        # SharedCriterionService should have been called with 2 operations
        call_args = mock_shared_criterion_svc.mutate_shared_criteria.call_args
        self.assertEqual(len(call_args[1]["operations"]), 2)

    @patch("ads_mcp.utils.get_googleads_client")
    @patch("ads_mcp.utils.get_googleads_type")
    @patch("ads_mcp.utils.get_googleads_service")
    def test_apply_shared_negative_list(self, mock_get_svc, mock_get_type, mock_get_client):
        mock_service = MagicMock()
        mock_get_svc.return_value = mock_service
        mock_get_type.return_value = MagicMock()
        mock_get_client.return_value = MagicMock()
        mock_response = MagicMock()
        mock_response.results[0].resource_name = "customers/123/campaignSharedSets/789~999"
        mock_service.mutate_campaign_shared_sets.return_value = mock_response

        from ads_mcp.tools.negative_lists import apply_shared_negative_list
        result = apply_shared_negative_list(
            customer_id="123",
            campaign_resource_name="customers/123/campaigns/789",
            shared_set_resource_name="customers/123/sharedSets/999",
        )

        self.assertEqual(result, "customers/123/campaignSharedSets/789~999")


if __name__ == "__main__":
    unittest.main()
