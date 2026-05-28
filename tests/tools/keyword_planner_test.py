import unittest
from unittest.mock import MagicMock, patch, call


class TestKeywordPlanner(unittest.TestCase):

    @patch("ads_mcp.utils.get_googleads_client")
    @patch("ads_mcp.utils.get_googleads_type")
    @patch("ads_mcp.utils.get_googleads_service")
    def test_generate_keyword_ideas_keyword_seed(self, mock_get_svc, mock_get_type, mock_get_client):
        mock_service = MagicMock()
        mock_get_svc.return_value = mock_service

        mock_request = MagicMock()
        mock_get_type.return_value = mock_request

        mock_idea = MagicMock()
        mock_idea.text = "running shoes"
        mock_idea.keyword_idea_metrics.avg_monthly_searches = 1000
        mock_idea.keyword_idea_metrics.competition.name = "MEDIUM"
        mock_idea.keyword_idea_metrics.low_top_of_page_bid_micros = 500000
        mock_idea.keyword_idea_metrics.high_top_of_page_bid_micros = 1500000
        mock_service.generate_keyword_ideas.return_value = [mock_idea]

        from ads_mcp.tools.keyword_planner import generate_keyword_ideas
        result = generate_keyword_ideas(
            customer_id="1234567890",
            keywords=["running shoes", "athletic footwear"],
            language_id=1000,
            geo_target_ids=[2036],
        )

        mock_get_svc.assert_called_once_with("KeywordPlanIdeaService")
        mock_service.generate_keyword_ideas.assert_called_once()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["text"], "running shoes")
        self.assertEqual(result[0]["avg_monthly_searches"], 1000)
        self.assertEqual(result[0]["competition"], "MEDIUM")
        self.assertEqual(result[0]["low_top_of_page_bid_micros"], 500000)
        self.assertEqual(result[0]["high_top_of_page_bid_micros"], 1500000)

    @patch("ads_mcp.utils.get_googleads_client")
    @patch("ads_mcp.utils.get_googleads_type")
    @patch("ads_mcp.utils.get_googleads_service")
    def test_generate_keyword_ideas_url_seed(self, mock_get_svc, mock_get_type, mock_get_client):
        mock_service = MagicMock()
        mock_get_svc.return_value = mock_service
        mock_get_type.return_value = MagicMock()
        mock_service.generate_keyword_ideas.return_value = []

        from ads_mcp.tools.keyword_planner import generate_keyword_ideas
        generate_keyword_ideas(
            customer_id="1234567890",
            keywords=[],
            language_id=1000,
            geo_target_ids=[2036],
            url="https://example.com",
        )

        mock_service.generate_keyword_ideas.assert_called_once()

    @patch("ads_mcp.utils.get_googleads_client")
    @patch("ads_mcp.utils.get_googleads_type")
    @patch("ads_mcp.utils.get_googleads_service")
    def test_generate_keyword_historical_metrics(self, mock_get_svc, mock_get_type, mock_get_client):
        mock_service = MagicMock()
        mock_get_svc.return_value = mock_service
        mock_get_type.return_value = MagicMock()

        mock_result = MagicMock()
        mock_result.text = "best running shoes"
        mock_result.keyword_metrics.avg_monthly_searches = 2400
        mock_result.keyword_metrics.competition.name = "HIGH"
        mock_result.keyword_metrics.low_top_of_page_bid_micros = 800000
        mock_result.keyword_metrics.high_top_of_page_bid_micros = 3000000
        mock_response = MagicMock()
        mock_response.results = [mock_result]
        mock_service.generate_keyword_historical_metrics.return_value = mock_response

        from ads_mcp.tools.keyword_planner import generate_keyword_historical_metrics
        result = generate_keyword_historical_metrics(
            customer_id="1234567890",
            keywords=["best running shoes"],
            language_id=1000,
            geo_target_ids=[2036],
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["text"], "best running shoes")
        self.assertEqual(result[0]["avg_monthly_searches"], 2400)

    @patch("ads_mcp.utils.get_googleads_client")
    @patch("ads_mcp.utils.get_googleads_type")
    @patch("ads_mcp.utils.get_googleads_service")
    def test_generate_ad_group_themes(self, mock_get_svc, mock_get_type, mock_get_client):
        mock_service = MagicMock()
        mock_get_svc.return_value = mock_service
        mock_get_type.return_value = MagicMock()

        mock_theme = MagicMock()
        mock_theme.display_name = "Trail Running"
        mock_theme.keywords = ["trail running shoes", "off road running"]
        mock_response = MagicMock()
        mock_response.ad_group_themes = [mock_theme]
        mock_service.generate_ad_group_themes.return_value = mock_response

        from ads_mcp.tools.keyword_planner import generate_ad_group_themes
        result = generate_ad_group_themes(
            customer_id="1234567890",
            keywords=["trail running shoes", "off road running", "road running shoes"],
            language_id=1000,
            geo_target_ids=[2036],
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["display_name"], "Trail Running")


if __name__ == "__main__":
    unittest.main()
