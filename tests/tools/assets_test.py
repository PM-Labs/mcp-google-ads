# tests/tools/assets_test.py
import unittest
from unittest.mock import MagicMock, patch


class TestAssets(unittest.TestCase):

    @patch("ads_mcp.utils.get_googleads_client")
    @patch("ads_mcp.utils.get_googleads_type")
    @patch("ads_mcp.utils.get_googleads_service")
    def test_create_sitelink(self, mock_get_svc, mock_get_type, mock_get_client):
        mock_asset_svc = MagicMock()
        mock_campaign_asset_svc = MagicMock()
        mock_get_svc.side_effect = lambda n: (
            mock_asset_svc if n == "AssetService" else mock_campaign_asset_svc
        )
        mock_get_type.return_value = MagicMock()
        mock_client = MagicMock()
        mock_client.enums.AssetFieldTypeEnum.SITELINK = 2
        mock_get_client.return_value = mock_client

        mock_asset_response = MagicMock()
        mock_asset_response.results[0].resource_name = "customers/123/assets/555"
        mock_asset_svc.mutate_assets.return_value = mock_asset_response

        mock_link_response = MagicMock()
        mock_link_response.results[0].resource_name = "customers/123/campaignAssets/789~555~2"
        mock_campaign_asset_svc.mutate_campaign_assets.return_value = mock_link_response

        from ads_mcp.tools.assets import create_sitelink
        result = create_sitelink(
            customer_id="123",
            campaign_resource_name="customers/123/campaigns/789",
            link_text="Free Quote",
            final_url="https://example.com/quote",
            description1="Get a quote today",
            description2="No obligation required",
        )

        self.assertEqual(result, "customers/123/assets/555")
        mock_asset_svc.mutate_assets.assert_called_once()
        mock_campaign_asset_svc.mutate_campaign_assets.assert_called_once()

    @patch("ads_mcp.utils.get_googleads_client")
    @patch("ads_mcp.utils.get_googleads_type")
    @patch("ads_mcp.utils.get_googleads_service")
    def test_create_callout(self, mock_get_svc, mock_get_type, mock_get_client):
        mock_asset_svc = MagicMock()
        mock_campaign_asset_svc = MagicMock()
        mock_get_svc.side_effect = lambda n: (
            mock_asset_svc if n == "AssetService" else mock_campaign_asset_svc
        )
        mock_get_type.return_value = MagicMock()
        mock_client = MagicMock()
        mock_client.enums.AssetFieldTypeEnum.CALLOUT = 3
        mock_get_client.return_value = mock_client

        mock_asset_response = MagicMock()
        mock_asset_response.results[0].resource_name = "customers/123/assets/666"
        mock_asset_svc.mutate_assets.return_value = mock_asset_response

        mock_link_response = MagicMock()
        mock_link_response.results[0].resource_name = "customers/123/campaignAssets/789~666~3"
        mock_campaign_asset_svc.mutate_campaign_assets.return_value = mock_link_response

        from ads_mcp.tools.assets import create_callout
        result = create_callout(
            customer_id="123",
            campaign_resource_name="customers/123/campaigns/789",
            callout_text="Award Winning Service",
        )

        self.assertEqual(result, "customers/123/assets/666")


if __name__ == "__main__":
    unittest.main()
