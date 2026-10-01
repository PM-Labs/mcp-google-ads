import unittest
from types import SimpleNamespace
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


class RecordingResource:
    """Records which fields were assigned; value_settings is recorded too."""

    def __init__(self):
        object.__setattr__(self, "assigned", set())
        object.__setattr__(self, "value_settings", RecordingValueSettings())

    def __setattr__(self, name, value):
        self.assigned.add(name)
        object.__setattr__(self, name, value)


class RecordingValueSettings:
    def __init__(self):
        object.__setattr__(self, "assigned", set())

    def __setattr__(self, name, value):
        self.assigned.add(name)
        object.__setattr__(self, name, value)


class FakeOperation:
    def __init__(self):
        self.create = None
        self.update = None
        self.remove = None
        self.update_mask = SimpleNamespace(paths=[])


def _readback_row(**overrides):
    row = MagicMock()
    ca = row.conversion_action
    ca.id = overrides.get("id", 789)
    ca.name = overrides.get("name", "PM | Test")
    ca.status.name = overrides.get("status", "ENABLED")
    ca.type_.name = overrides.get("type", "WEBPAGE")
    ca.category.name = overrides.get("category", "SUBMIT_LEAD_FORM")
    ca.primary_for_goal = overrides.get("primary_for_goal", True)
    ca.phone_call_duration_seconds = overrides.get("phone_call_duration_seconds", 0)
    return row


def _batch(*rows):
    return SimpleNamespace(results=list(rows))


def _wire(mock_get_client, mock_get_type, mock_get_svc, rows=None):
    """Wires the three util mocks; returns (client, action, operation)."""
    action = RecordingResource()
    operation = FakeOperation()
    types = {"ConversionAction": action, "ConversionActionOperation": operation}
    mock_get_type.side_effect = lambda n: types.get(n, MagicMock())
    client = _mock_client()
    client.get_service.return_value.mutate_conversion_actions.return_value = (
        _mock_mutate_response("customers/123/conversionActions/789")
    )
    mock_get_client.return_value = client
    rows = [_readback_row()] if rows is None else rows
    mock_get_svc.return_value.search_stream.return_value = (
        [_batch(*rows)] if rows else []
    )
    return client, action, operation


PATCHES = (
    "ads_mcp.utils.get_googleads_service",
    "ads_mcp.utils.get_googleads_type",
    "ads_mcp.utils.get_googleads_client",
)


class TestCreateConversionActionPhoneAndPrimary(unittest.TestCase):

    @patch(PATCHES[0])
    @patch(PATCHES[1])
    @patch(PATCHES[2])
    def test_phone_call_duration_and_primary_set_when_supplied(
        self, mock_get_client, mock_get_type, mock_get_svc
    ):
        _, action, _ = _wire(mock_get_client, mock_get_type, mock_get_svc)

        from ads_mcp.tools.conversions import create_conversion_action
        create_conversion_action(
            customer_id="123",
            name="PM | Calls",
            category="PHONE_CALL_LEAD",
            type="WEBSITE_CALL",
            phone_call_duration_seconds=60,
            primary_for_goal=False,
        )

        self.assertEqual(action.phone_call_duration_seconds, 60)
        # False is a real value, not "omitted".
        self.assertIn("primary_for_goal", action.assigned)
        self.assertIs(action.primary_for_goal, False)

    @patch(PATCHES[0])
    @patch(PATCHES[1])
    @patch(PATCHES[2])
    def test_phone_duration_and_primary_omitted_when_not_supplied(
        self, mock_get_client, mock_get_type, mock_get_svc
    ):
        _, action, _ = _wire(mock_get_client, mock_get_type, mock_get_svc)

        from ads_mcp.tools.conversions import create_conversion_action
        create_conversion_action(
            customer_id="123", name="PM | Form", category="SUBMIT_LEAD_FORM"
        )

        self.assertNotIn("phone_call_duration_seconds", action.assigned)
        self.assertNotIn("primary_for_goal", action.assigned)

    @patch(PATCHES[0])
    @patch(PATCHES[1])
    @patch(PATCHES[2])
    def test_all_supported_types_accepted(
        self, mock_get_client, mock_get_type, mock_get_svc
    ):
        from ads_mcp.tools.conversions import create_conversion_action
        for t in (
            "WEBPAGE", "WEBSITE_CALL", "AD_CALL", "CLICK_TO_CALL",
            "UPLOAD_CLICKS", "UPLOAD_CALLS",
        ):
            with self.subTest(type=t), patch("ads_mcp.tools.conversions.time.sleep"):
                _, _, _ = _wire(mock_get_client, mock_get_type, mock_get_svc)
                result = create_conversion_action(
                    customer_id="123", name="x", category="CONTACT", type=t
                )
                self.assertEqual(result["id"], "789")

    @patch(PATCHES[0])
    @patch(PATCHES[1])
    @patch(PATCHES[2])
    def test_unsupported_type_rejected_before_any_api_call(
        self, mock_get_client, mock_get_type, mock_get_svc
    ):
        client, _, _ = _wire(mock_get_client, mock_get_type, mock_get_svc)

        from ads_mcp.tools.conversions import create_conversion_action
        from fastmcp.exceptions import ToolError
        with self.assertRaises(ToolError) as ctx:
            create_conversion_action(
                customer_id="123", name="x", category="CONTACT",
                type="GOOGLE_ANALYTICS_4_CUSTOM",
            )
        self.assertIn("WEBSITE_CALL", str(ctx.exception))
        client.get_service.return_value.mutate_conversion_actions.assert_not_called()

    @patch(PATCHES[0])
    @patch(PATCHES[1])
    @patch(PATCHES[2])
    def test_types_without_a_tag_skip_the_snippet_retry(
        self, mock_get_client, mock_get_type, mock_get_svc
    ):
        _wire(mock_get_client, mock_get_type, mock_get_svc)

        from ads_mcp.tools.conversions import create_conversion_action
        with patch("ads_mcp.tools.conversions.time.sleep") as sleep:
            result = create_conversion_action(
                customer_id="123", name="x", category="QUALIFIED_LEAD",
                type="UPLOAD_CLICKS",
            )
        sleep.assert_not_called()
        self.assertIsNone(result["snippets_ready"])
        self.assertEqual(result["status"], "ENABLED")

    @patch(PATCHES[0])
    @patch(PATCHES[1])
    @patch(PATCHES[2])
    def test_webpage_still_retries_for_snippets(
        self, mock_get_client, mock_get_type, mock_get_svc
    ):
        _wire(mock_get_client, mock_get_type, mock_get_svc, rows=[])

        from ads_mcp.tools.conversions import create_conversion_action
        with patch("ads_mcp.tools.conversions.time.sleep") as sleep:
            result = create_conversion_action(
                customer_id="123", name="x", category="CONTACT", type="WEBPAGE"
            )
        self.assertEqual(sleep.call_count, 5)
        self.assertFalse(result["snippets_ready"])


class TestUpdateConversionAction(unittest.TestCase):

    @patch(PATCHES[0])
    @patch(PATCHES[1])
    @patch(PATCHES[2])
    def test_updates_only_supplied_fields(
        self, mock_get_client, mock_get_type, mock_get_svc
    ):
        _, action, op = _wire(mock_get_client, mock_get_type, mock_get_svc)

        from ads_mcp.tools.conversions import update_conversion_action
        update_conversion_action(
            customer_id="123-456",
            conversion_action_id="789",
            name="New name",
            primary_for_goal=False,
        )

        self.assertEqual(
            action.resource_name, "customers/123456/conversionActions/789"
        )
        self.assertEqual(action.assigned - {"resource_name"}, {"name", "primary_for_goal"})
        self.assertIs(op.update, action)
        self.assertEqual(sorted(op.update_mask.paths), ["name", "primary_for_goal"])

    @patch(PATCHES[0])
    @patch(PATCHES[1])
    @patch(PATCHES[2])
    def test_value_settings_use_nested_mask_paths(
        self, mock_get_client, mock_get_type, mock_get_svc
    ):
        _, action, op = _wire(mock_get_client, mock_get_type, mock_get_svc)

        from ads_mcp.tools.conversions import update_conversion_action
        update_conversion_action(
            customer_id="123",
            conversion_action_id="789",
            default_value=50.0,
            default_currency_code="AUD",
            always_use_default_value=False,
        )

        self.assertEqual(
            sorted(op.update_mask.paths),
            [
                "value_settings.always_use_default_value",
                "value_settings.default_currency_code",
                "value_settings.default_value",
            ],
        )
        self.assertEqual(action.value_settings.default_value, 50.0)
        self.assertIs(action.value_settings.always_use_default_value, False)

    @patch(PATCHES[0])
    @patch(PATCHES[1])
    @patch(PATCHES[2])
    def test_no_fields_is_an_error_and_makes_no_api_call(
        self, mock_get_client, mock_get_type, mock_get_svc
    ):
        client, _, _ = _wire(mock_get_client, mock_get_type, mock_get_svc)

        from ads_mcp.tools.conversions import update_conversion_action
        from fastmcp.exceptions import ToolError
        with self.assertRaises(ToolError):
            update_conversion_action(customer_id="123", conversion_action_id="789")
        client.get_service.return_value.mutate_conversion_actions.assert_not_called()

    @patch(PATCHES[0])
    @patch(PATCHES[1])
    @patch(PATCHES[2])
    def test_removed_status_points_at_the_remove_tool(
        self, mock_get_client, mock_get_type, mock_get_svc
    ):
        client, _, _ = _wire(mock_get_client, mock_get_type, mock_get_svc)

        from ads_mcp.tools.conversions import update_conversion_action
        from fastmcp.exceptions import ToolError
        with self.assertRaises(ToolError) as ctx:
            update_conversion_action(
                customer_id="123", conversion_action_id="789", status="REMOVED"
            )
        self.assertIn("remove_conversion_action", str(ctx.exception))
        client.get_service.return_value.mutate_conversion_actions.assert_not_called()

    @patch(PATCHES[0])
    @patch(PATCHES[1])
    @patch(PATCHES[2])
    def test_returns_state_read_back_from_the_api(
        self, mock_get_client, mock_get_type, mock_get_svc
    ):
        _wire(
            mock_get_client, mock_get_type, mock_get_svc,
            rows=[_readback_row(name="Renamed", primary_for_goal=False)],
        )

        from ads_mcp.tools.conversions import update_conversion_action
        result = update_conversion_action(
            customer_id="123", conversion_action_id="789", name="Renamed"
        )
        self.assertEqual(result["name"], "Renamed")
        self.assertIs(result["primary_for_goal"], False)
        self.assertEqual(result["id"], "789")

    @patch(PATCHES[0])
    @patch(PATCHES[1])
    @patch(PATCHES[2])
    def test_api_error_names_the_offending_field(
        self, mock_get_client, mock_get_type, mock_get_svc
    ):
        client, _, _ = _wire(mock_get_client, mock_get_type, mock_get_svc)
        element = MagicMock()
        element.field_name = "primary_for_goal"
        error = MagicMock()
        error.message = "The field attempted to be mutated is immutable."
        error.location.field_path_elements = [element]
        failure = MagicMock()
        failure.errors = [error]
        from google.ads.googleads.errors import GoogleAdsException
        client.get_service.return_value.mutate_conversion_actions.side_effect = (
            GoogleAdsException(None, None, failure, "req-1")
        )

        from ads_mcp.tools.conversions import update_conversion_action
        from fastmcp.exceptions import ToolError
        with self.assertRaises(ToolError) as ctx:
            update_conversion_action(
                customer_id="123", conversion_action_id="789", primary_for_goal=True
            )
        self.assertIn("[field: primary_for_goal]", str(ctx.exception))


class TestIdValidationIsAsciiOnly(unittest.TestCase):
    """Unicode digits match \\d but are not valid ids; they must be refused."""

    @patch(PATCHES[0])
    @patch(PATCHES[1])
    @patch(PATCHES[2])
    def test_non_ascii_digits_rejected_in_id_and_customer(
        self, mock_get_client, mock_get_type, mock_get_svc
    ):
        client, _, _ = _wire(mock_get_client, mock_get_type, mock_get_svc)

        from ads_mcp.tools.conversions import update_conversion_action
        from fastmcp.exceptions import ToolError
        for customer, action in (
            ("123", "\u0667\u0667\u0662\u0660"),
            ("\uff11\uff12\uff13", "789"),
            ("123", "customers/123/conversionActions/\u0667\u0667"),
        ):
            with self.subTest(customer=customer, action=action):
                with self.assertRaises(ToolError):
                    update_conversion_action(
                        customer_id=customer,
                        conversion_action_id=action,
                        name="x",
                    )
        client.get_service.return_value.mutate_conversion_actions.assert_not_called()


class TestRemoveConversionAction(unittest.TestCase):

    @patch(PATCHES[0])
    @patch(PATCHES[1])
    @patch(PATCHES[2])
    def test_removes_by_id_and_reports_status_read_back(
        self, mock_get_client, mock_get_type, mock_get_svc
    ):
        client, _, op = _wire(
            mock_get_client, mock_get_type, mock_get_svc,
            rows=[_readback_row(status="REMOVED")],
        )

        from ads_mcp.tools.conversions import remove_conversion_action
        result = remove_conversion_action(customer_id="123", conversion_action_id="789")

        self.assertEqual(op.remove, "customers/123/conversionActions/789")
        client.get_service.return_value.mutate_conversion_actions.assert_called_once()
        self.assertEqual(result["status"], "REMOVED")
        self.assertEqual(result["id"], "789")

    @patch(PATCHES[0])
    @patch(PATCHES[1])
    @patch(PATCHES[2])
    def test_accepts_a_full_resource_name(
        self, mock_get_client, mock_get_type, mock_get_svc
    ):
        _, _, op = _wire(
            mock_get_client, mock_get_type, mock_get_svc,
            rows=[_readback_row(status="REMOVED")],
        )

        from ads_mcp.tools.conversions import remove_conversion_action
        remove_conversion_action(
            customer_id="123",
            conversion_action_id="customers/123/conversionActions/789",
        )
        self.assertEqual(op.remove, "customers/123/conversionActions/789")

    @patch(PATCHES[0])
    @patch(PATCHES[1])
    @patch(PATCHES[2])
    def test_refuses_a_resource_name_from_another_customer(
        self, mock_get_client, mock_get_type, mock_get_svc
    ):
        client, _, _ = _wire(mock_get_client, mock_get_type, mock_get_svc)

        from ads_mcp.tools.conversions import remove_conversion_action
        from fastmcp.exceptions import ToolError
        with self.assertRaises(ToolError):
            remove_conversion_action(
                customer_id="123",
                conversion_action_id="customers/999/conversionActions/789",
            )
        client.get_service.return_value.mutate_conversion_actions.assert_not_called()

    @patch(PATCHES[0])
    @patch(PATCHES[1])
    @patch(PATCHES[2])
    def test_rejects_a_non_numeric_id(
        self, mock_get_client, mock_get_type, mock_get_svc
    ):
        client, _, _ = _wire(mock_get_client, mock_get_type, mock_get_svc)

        from ads_mcp.tools.conversions import remove_conversion_action
        from fastmcp.exceptions import ToolError
        with self.assertRaises(ToolError):
            remove_conversion_action(
                customer_id="123", conversion_action_id="ZZZ | MCP WRITE TEST"
            )
        client.get_service.return_value.mutate_conversion_actions.assert_not_called()


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
