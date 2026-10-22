"""Tests for the conversion-goal biddability tools.

Uses REAL v25 protobuf message types for the operations (see CLAUDE.md: a
mock-only upload test once accepted a call the real client rejects), and
mocks only the network-facing service + search.
"""

import unittest
from unittest.mock import MagicMock, patch

from fastmcp.exceptions import ToolError
from google.ads.googleads.v25.enums.types import (
    conversion_action_category,
    conversion_origin,
    goal_config_level,
)
from google.ads.googleads.v25.resources.types import (
    campaign_conversion_goal,
    conversion_goal_campaign_config,
    customer_conversion_goal,
)
from google.ads.googleads.v25.services.types import (
    campaign_conversion_goal_service,
    conversion_goal_campaign_config_service,
    customer_conversion_goal_service,
)

VERSION = "v25"

_TYPES = {
    "CustomerConversionGoal": customer_conversion_goal.CustomerConversionGoal,
    "CustomerConversionGoalOperation": customer_conversion_goal_service.CustomerConversionGoalOperation,
    "CampaignConversionGoal": campaign_conversion_goal.CampaignConversionGoal,
    "CampaignConversionGoalOperation": campaign_conversion_goal_service.CampaignConversionGoalOperation,
    "ConversionGoalCampaignConfig": conversion_goal_campaign_config.ConversionGoalCampaignConfig,
    "ConversionGoalCampaignConfigOperation": conversion_goal_campaign_config_service.ConversionGoalCampaignConfigOperation,
}


def _real_type(name):
    return _TYPES[name]()


class _Client:
    """Real enums, mocked services."""

    def __init__(self):
        self.enums = MagicMock()
        self.enums.ConversionActionCategoryEnum = (
            conversion_action_category.ConversionActionCategoryEnum.ConversionActionCategory
        )
        self.enums.ConversionOriginEnum = (
            conversion_origin.ConversionOriginEnum.ConversionOrigin
        )
        self.enums.GoalConfigLevelEnum = (
            goal_config_level.GoalConfigLevelEnum.GoalConfigLevel
        )
        self.service = MagicMock()

    def get_service(self, name):
        self.service_name = name
        return self.service


def _row(**kwargs):
    row = MagicMock()
    for k, v in kwargs.items():
        setattr(row, k, v)
    return row


class TestUpdateCustomerConversionGoal(unittest.TestCase):

    @patch("ads_mcp.utils.get_googleads_service")
    @patch("ads_mcp.utils.get_googleads_type", side_effect=_real_type)
    @patch("ads_mcp.utils.get_googleads_client")
    def test_builds_update_with_biddable_mask(self, mock_client, _t, mock_svc):
        client = _Client()
        mock_client.return_value = client
        goal = _real_type("CustomerConversionGoal")
        goal.category = client.enums.ConversionActionCategoryEnum.SUBMIT_LEAD_FORM
        goal.origin = client.enums.ConversionOriginEnum.WEBSITE
        goal.biddable = True
        batch = MagicMock()
        batch.results = [_row(customer_conversion_goal=goal)]
        mock_svc.return_value.search_stream.return_value = [batch]

        from ads_mcp.tools.conversion_goals import update_customer_conversion_goal

        out = update_customer_conversion_goal(
            "881-561-1199", "submit_lead_form", "WEBSITE", True
        )

        self.assertEqual(client.service_name, "CustomerConversionGoalService")
        kwargs = client.service.mutate_customer_conversion_goals.call_args.kwargs
        self.assertEqual(kwargs["customer_id"], "8815611199")
        op = kwargs["operations"][0]
        self.assertEqual(
            op.update.resource_name,
            "customers/8815611199/customerConversionGoals/SUBMIT_LEAD_FORM~WEBSITE",
        )
        self.assertTrue(op.update.biddable)
        self.assertEqual(list(op.update_mask.paths), ["biddable"])
        self.assertEqual(
            out,
            {
                "resource_name": "customers/8815611199/customerConversionGoals/SUBMIT_LEAD_FORM~WEBSITE",
                "category": "SUBMIT_LEAD_FORM",
                "origin": "WEBSITE",
                "biddable": True,
            },
        )

    @patch("ads_mcp.utils.get_googleads_service")
    @patch("ads_mcp.utils.get_googleads_type", side_effect=_real_type)
    @patch("ads_mcp.utils.get_googleads_client")
    def test_false_is_sent_and_masked(self, mock_client, _t, mock_svc):
        """biddable=False is a real value; it must still be in the mask."""
        client = _Client()
        mock_client.return_value = client
        mock_svc.return_value.search_stream.return_value = []

        from ads_mcp.tools.conversion_goals import update_customer_conversion_goal

        out = update_customer_conversion_goal("123", "OUTBOUND_CLICK", "WEBSITE", False)
        op = client.service.mutate_customer_conversion_goals.call_args.kwargs[
            "operations"
        ][0]
        self.assertFalse(op.update.biddable)
        self.assertEqual(list(op.update_mask.paths), ["biddable"])
        self.assertFalse(out["verified"])

    @patch("ads_mcp.utils.get_googleads_client")
    def test_rejects_bad_enum(self, mock_client):
        mock_client.return_value = _Client()
        from ads_mcp.tools.conversion_goals import update_customer_conversion_goal

        with self.assertRaises(ToolError) as ctx:
            update_customer_conversion_goal("123", "LEADS", "WEBSITE", True)
        self.assertIn("SUBMIT_LEAD_FORM", str(ctx.exception))
        with self.assertRaises(ToolError):
            update_customer_conversion_goal("123", "SUBMIT_LEAD_FORM", "SITE", True)


class TestUpdateCampaignConversionGoal(unittest.TestCase):

    @patch("ads_mcp.utils.get_googleads_service")
    @patch("ads_mcp.utils.get_googleads_type", side_effect=_real_type)
    @patch("ads_mcp.utils.get_googleads_client")
    def test_resource_name_includes_campaign(self, mock_client, _t, mock_svc):
        client = _Client()
        mock_client.return_value = client
        mock_svc.return_value.search_stream.return_value = []

        from ads_mcp.tools.conversion_goals import update_campaign_conversion_goal

        update_campaign_conversion_goal(
            "123", "456", "PHONE_CALL_LEAD", "CALL_FROM_ADS", True
        )
        self.assertEqual(client.service_name, "CampaignConversionGoalService")
        op = client.service.mutate_campaign_conversion_goals.call_args.kwargs[
            "operations"
        ][0]
        self.assertEqual(
            op.update.resource_name,
            "customers/123/campaignConversionGoals/456~PHONE_CALL_LEAD~CALL_FROM_ADS",
        )
        self.assertEqual(list(op.update_mask.paths), ["biddable"])

    @patch("ads_mcp.utils.get_googleads_client")
    def test_rejects_non_numeric_campaign(self, mock_client):
        mock_client.return_value = _Client()
        from ads_mcp.tools.conversion_goals import update_campaign_conversion_goal

        with self.assertRaises(ToolError):
            update_campaign_conversion_goal(
                "123", "Swept Path", "SUBMIT_LEAD_FORM", "WEBSITE", True
            )


class TestSetCampaignGoalConfigLevel(unittest.TestCase):

    @patch("ads_mcp.utils.get_googleads_service")
    @patch("ads_mcp.utils.get_googleads_type", side_effect=_real_type)
    @patch("ads_mcp.utils.get_googleads_client")
    def test_sets_level(self, mock_client, _t, mock_svc):
        client = _Client()
        mock_client.return_value = client
        mock_svc.return_value.search_stream.return_value = []

        from ads_mcp.tools.conversion_goals import set_campaign_goal_config_level

        set_campaign_goal_config_level("123", "456", "customer")
        self.assertEqual(client.service_name, "ConversionGoalCampaignConfigService")
        op = client.service.mutate_conversion_goal_campaign_configs.call_args.kwargs[
            "operations"
        ][0]
        self.assertEqual(
            op.update.resource_name, "customers/123/conversionGoalCampaignConfigs/456"
        )
        self.assertEqual(op.update.goal_config_level.name, "CUSTOMER")
        self.assertEqual(list(op.update_mask.paths), ["goal_config_level"])

    def test_rejects_bad_level(self):
        from ads_mcp.tools.conversion_goals import set_campaign_goal_config_level

        with self.assertRaises(ToolError):
            set_campaign_goal_config_level("123", "456", "ACCOUNT")


class TestRealClientSignatures(unittest.TestCase):
    """The mutate method names/kwargs used must exist on the real services."""

    def test_service_methods_exist(self):
        import importlib

        for module, cls, method in (
            ("customer_conversion_goal_service", "CustomerConversionGoalServiceClient", "mutate_customer_conversion_goals"),
            ("campaign_conversion_goal_service", "CampaignConversionGoalServiceClient", "mutate_campaign_conversion_goals"),
            ("conversion_goal_campaign_config_service", "ConversionGoalCampaignConfigServiceClient", "mutate_conversion_goal_campaign_configs"),
        ):
            mod = importlib.import_module(
                f"google.ads.googleads.{VERSION}.services.services.{module}"
            )
            client_cls = getattr(mod, cls)
            self.assertTrue(hasattr(client_cls, method), f"{cls}.{method} missing")
            import inspect

            params = inspect.signature(getattr(client_cls, method)).parameters
            self.assertIn("customer_id", params)
            self.assertIn("operations", params)


if __name__ == "__main__":
    unittest.main()
