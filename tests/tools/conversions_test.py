import unittest
from unittest.mock import MagicMock, patch


class RecordingConversionAction:
    """Stub that records exactly which fields were assigned.

    A MagicMock cannot answer "was this field set?" -- reading any attribute
    auto-creates it. These tests exist specifically to assert that unset
    optional fields are never written to the create operation, so assignment
    has to be observable.
    """

    def __init__(self):
        object.__setattr__(self, "assigned", set())
        object.__setattr__(self, "value_settings", MagicMock())

    def __setattr__(self, name, value):
        self.assigned.add(name)
        object.__setattr__(self, name, value)


def _mock_client():
    client = MagicMock()
    client.enums.ConversionActionCategoryEnum.__getitem__.return_value = 7
    client.enums.ConversionActionTypeEnum.__getitem__.return_value = 2
    client.enums.ConversionActionStatusEnum.__getitem__.return_value = 2
    client.enums.ConversionActionCountingTypeEnum.__getitem__.return_value = 3
    return client


def _mock_mutate_response(resource_name="customers/123/conversionActions/456"):
    response = MagicMock()
    response.results[0].resource_name = resource_name
    return response


class TestCreateConversionAction(unittest.TestCase):

    @patch("ads_mcp.utils.get_googleads_service")
    @patch("ads_mcp.utils.get_googleads_type")
    @patch("ads_mcp.utils.get_googleads_client")
    def test_omits_optional_fields_when_not_supplied(
        self, mock_get_client, mock_get_type, mock_get_svc
    ):
        """Regression guard for the IMMUTABLE_FIELD bug (fixed 2026-08-14).

        The tool previously set include_in_conversions_metric, counting_type
        and both lookback windows unconditionally. include_in_conversions_metric
        is not settable at create under Google's conversion-goals model, so
        EVERY call failed with IMMUTABLE_FIELD regardless of arguments. Only
        caller-supplied fields may be assigned.
        """
        conversion_action = RecordingConversionAction()
        mock_get_type.side_effect = (
            lambda n: conversion_action if n == "ConversionAction" else MagicMock()
        )
        client = _mock_client()
        client.get_service.return_value.mutate_conversion_actions.return_value = (
            _mock_mutate_response()
        )
        mock_get_client.return_value = client
        mock_get_svc.return_value.search_stream.return_value = []

        from ads_mcp.tools.conversions import create_conversion_action
        create_conversion_action(
            customer_id="123",
            name="PM | Purchase",
            category="PURCHASE",
        )

        self.assertNotIn(
            "include_in_conversions_metric",
            conversion_action.assigned,
            "include_in_conversions_metric must never be set on create -- "
            "the API rejects it with IMMUTABLE_FIELD",
        )
        self.assertNotIn("counting_type", conversion_action.assigned)
        self.assertNotIn(
            "click_through_lookback_window_days", conversion_action.assigned
        )
        self.assertNotIn(
            "view_through_lookback_window_days", conversion_action.assigned
        )
        # The always-required fields are still set.
        self.assertIn("name", conversion_action.assigned)
        self.assertIn("category", conversion_action.assigned)
        self.assertIn("type_", conversion_action.assigned)
        self.assertIn("status", conversion_action.assigned)

    @patch("ads_mcp.utils.get_googleads_service")
    @patch("ads_mcp.utils.get_googleads_type")
    @patch("ads_mcp.utils.get_googleads_client")
    def test_sets_optional_fields_when_supplied(
        self, mock_get_client, mock_get_type, mock_get_svc
    ):
        conversion_action = RecordingConversionAction()
        mock_get_type.side_effect = (
            lambda n: conversion_action if n == "ConversionAction" else MagicMock()
        )
        client = _mock_client()
        client.get_service.return_value.mutate_conversion_actions.return_value = (
            _mock_mutate_response()
        )
        mock_get_client.return_value = client
        mock_get_svc.return_value.search_stream.return_value = []

        from ads_mcp.tools.conversions import create_conversion_action
        create_conversion_action(
            customer_id="123",
            name="PM | Purchase",
            category="PURCHASE",
            counting_type="MANY_PER_CLICK",
            click_through_lookback_window_days=90,
            view_through_lookback_window_days=30,
        )

        self.assertIn("counting_type", conversion_action.assigned)
        self.assertEqual(conversion_action.click_through_lookback_window_days, 90)
        self.assertEqual(conversion_action.view_through_lookback_window_days, 30)

    @patch("ads_mcp.utils.get_googleads_service")
    @patch("ads_mcp.utils.get_googleads_type")
    @patch("ads_mcp.utils.get_googleads_client")
    def test_invalid_category_raises_tool_error(
        self, mock_get_client, mock_get_type, mock_get_svc
    ):
        client = MagicMock()
        client.enums.ConversionActionCategoryEnum.__getitem__.side_effect = KeyError
        client.enums.ConversionActionCategoryEnum.__iter__.return_value = iter([])
        mock_get_client.return_value = client
        mock_get_type.return_value = MagicMock()
        mock_get_svc.return_value = MagicMock()

        from ads_mcp.tools.conversions import create_conversion_action
        from fastmcp.exceptions import ToolError

        with self.assertRaises(ToolError):
            create_conversion_action(
                customer_id="123", name="x", category="NOT_A_CATEGORY"
            )


class TestFormatGoogleAdsError(unittest.TestCase):

    def test_includes_field_path(self):
        """A field-level failure must name the offending field.

        "The field attempted to be mutated is immutable." on its own is not
        actionable -- it cost a full diagnose-and-redeploy cycle once already.
        """
        from ads_mcp.tools.conversions import _format_googleads_error

        element = MagicMock()
        element.field_name = "include_in_conversions_metric"
        error = MagicMock()
        error.message = "The field attempted to be mutated is immutable."
        error.location.field_path_elements = [element]

        ex = MagicMock()
        ex.request_id = "abc123"
        ex.failure.errors = [error]

        result = _format_googleads_error(ex)

        self.assertIn("abc123", result)
        self.assertIn("immutable", result)
        self.assertIn("[field: include_in_conversions_metric]", result)

    def test_handles_missing_location(self):
        from ads_mcp.tools.conversions import _format_googleads_error

        error = MagicMock()
        error.message = "Something broke."
        error.location.field_path_elements = []

        ex = MagicMock()
        ex.request_id = "xyz789"
        ex.failure.errors = [error]

        result = _format_googleads_error(ex)

        self.assertIn("Something broke.", result)
        self.assertNotIn("[field:", result)


if __name__ == "__main__":
    unittest.main()
