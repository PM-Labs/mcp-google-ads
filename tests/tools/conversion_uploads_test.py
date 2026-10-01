import subprocess
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from google.ads.googleads.v25.errors.types.errors import (
    ErrorLocation,
    GoogleAdsError,
    GoogleAdsFailure,
)
from google.rpc import status_pb2

PATCHES = (
    "ads_mcp.utils.get_googleads_service",
    "ads_mcp.utils.get_googleads_type",
    "ads_mcp.utils.get_googleads_client",
)

GOOD_TIME = "2026-10-01 10:30:00+08:00"
NO_FAILURE = SimpleNamespace(code=0, details=[])


class Recording:
    """Records assigned fields so tests can see exactly what was sent."""

    def __init__(self):
        object.__setattr__(self, "assigned", set())

    def __setattr__(self, name, value):
        self.assigned.add(name)
        object.__setattr__(self, name, value)


def _partial_failure(index, message, field_name="gclid"):
    failure = GoogleAdsFailure(
        errors=[
            GoogleAdsError(
                message=message,
                location=ErrorLocation(
                    field_path_elements=[
                        ErrorLocation.FieldPathElement(
                            field_name="conversions", index=index
                        ),
                        ErrorLocation.FieldPathElement(field_name=field_name),
                    ]
                ),
            )
        ]
    )
    status = status_pb2.Status(code=3, message="Partial failure")
    status.details.add().Pack(GoogleAdsFailure.pb(failure))
    return status


def _wire(mock_get_client, mock_get_type, mock_get_svc, response=None):
    """Returns (upload service mock, list of ClickConversion/CallConversion made)."""
    made = []

    def make(name):
        if name == "GoogleAdsFailure":
            return GoogleAdsFailure()
        obj = Recording()
        made.append(obj)
        return obj

    mock_get_type.side_effect = make
    client = MagicMock()
    upload = client.get_service.return_value
    response = response or SimpleNamespace(
        partial_failure_error=NO_FAILURE, results=[]
    )
    upload.upload_click_conversions.return_value = response
    upload.upload_call_conversions.return_value = response
    mock_get_client.return_value = client
    return upload, made


def _click(**overrides):
    row = {"gclid": "g-1", "conversion_date_time": GOOD_TIME}
    row.update(overrides)
    return row


def _call(**overrides):
    row = {
        "caller_id": "+61400000000",
        "call_start_date_time": GOOD_TIME,
        "conversion_date_time": GOOD_TIME,
    }
    row.update(overrides)
    return row


class TestUploadValidation(unittest.TestCase):
    """Every bad input is refused before any API call is made."""

    def _assert_rejected(self, kind, conversions, **extra):
        from ads_mcp.tools.conversion_uploads import upload_offline_conversions
        from fastmcp.exceptions import ToolError

        with patch(PATCHES[0]) as svc, patch(PATCHES[1]) as typ, patch(
            PATCHES[2]
        ) as cli:
            upload, _ = _wire(cli, typ, svc)
            with self.assertRaises(ToolError) as ctx:
                upload_offline_conversions(
                    customer_id="123",
                    conversion_action_id="789",
                    conversions=conversions,
                    kind=kind,
                    **extra,
                )
            upload.upload_click_conversions.assert_not_called()
            upload.upload_call_conversions.assert_not_called()
        return str(ctx.exception)

    def test_bad_kind(self):
        self._assert_rejected("sms", [_click()])

    def test_empty_list(self):
        self._assert_rejected("click", [])

    def test_too_many_rows(self):
        self._assert_rejected("click", [_click()] * 2001)

    def test_click_needs_a_click_id(self):
        msg = self._assert_rejected(
            "click", [{"conversion_date_time": GOOD_TIME}]
        )
        self.assertIn("row 0", msg)

    def test_click_rejects_two_click_ids(self):
        self._assert_rejected("click", [_click(wbraid="w-1")])

    def test_click_needs_conversion_time(self):
        self._assert_rejected("click", [{"gclid": "g-1"}])

    def test_bad_time_format_names_the_row(self):
        msg = self._assert_rejected(
            "click", [_click(), _click(conversion_date_time="2026-10-01T10:30:00Z")]
        )
        self.assertIn("row 1", msg)

    def test_unknown_key_is_refused_not_ignored(self):
        msg = self._assert_rejected("click", [_click(gclidd="typo")])
        self.assertIn("gclidd", msg)

    def test_call_needs_caller_id(self):
        row = _call()
        del row["caller_id"]
        self._assert_rejected("call", [row])

    def test_call_rejects_click_fields(self):
        self._assert_rejected("call", [_call(gclid="g-1")])


class TestUploadHappyPaths(unittest.TestCase):

    @patch(PATCHES[0])
    @patch(PATCHES[1])
    @patch(PATCHES[2])
    def test_click_upload_builds_rows_and_requests_partial_failure(
        self, cli, typ, svc
    ):
        response = SimpleNamespace(
            partial_failure_error=NO_FAILURE,
            results=[SimpleNamespace(gclid="g-1")],
        )
        upload, made = _wire(cli, typ, svc, response)

        from ads_mcp.tools.conversion_uploads import upload_offline_conversions
        result = upload_offline_conversions(
            customer_id="123-456",
            conversion_action_id="789",
            conversions=[
                _click(conversion_value=50.0, currency_code="AUD", order_id="o-1")
            ],
        )

        kwargs = upload.upload_click_conversions.call_args.kwargs
        self.assertEqual(kwargs["customer_id"], "123456")
        self.assertIs(kwargs["partial_failure"], True)
        self.assertIs(kwargs["validate_only"], False)
        row = kwargs["conversions"][0]
        self.assertEqual(row.gclid, "g-1")
        self.assertEqual(row.conversion_action, "customers/123456/conversionActions/789")
        self.assertEqual(row.conversion_date_time, GOOD_TIME)
        self.assertEqual(row.conversion_value, 50.0)
        self.assertEqual(row.currency_code, "AUD")
        self.assertEqual(row.order_id, "o-1")
        # Optional fields not supplied must not be assigned.
        self.assertNotIn("gbraid", row.assigned)
        self.assertEqual(result["submitted"], 1)
        self.assertEqual(result["succeeded"], 1)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(result["results"][0]["status"], "ok")

    @patch(PATCHES[0])
    @patch(PATCHES[1])
    @patch(PATCHES[2])
    def test_call_upload_uses_the_call_service_method(self, cli, typ, svc):
        response = SimpleNamespace(
            partial_failure_error=NO_FAILURE,
            results=[SimpleNamespace(caller_id="+61400000000")],
        )
        upload, _ = _wire(cli, typ, svc, response)

        from ads_mcp.tools.conversion_uploads import upload_offline_conversions
        result = upload_offline_conversions(
            customer_id="123",
            conversion_action_id="789",
            conversions=[_call(conversion_value=10.0)],
            kind="call",
        )

        upload.upload_click_conversions.assert_not_called()
        row = upload.upload_call_conversions.call_args.kwargs["conversions"][0]
        self.assertEqual(row.caller_id, "+61400000000")
        self.assertEqual(row.call_start_date_time, GOOD_TIME)
        self.assertEqual(row.conversion_value, 10.0)
        self.assertEqual(result["succeeded"], 1)

    @patch(PATCHES[0])
    @patch(PATCHES[1])
    @patch(PATCHES[2])
    def test_validate_only_is_passed_through_and_labelled(self, cli, typ, svc):
        upload, _ = _wire(cli, typ, svc)

        from ads_mcp.tools.conversion_uploads import upload_offline_conversions
        result = upload_offline_conversions(
            customer_id="123",
            conversion_action_id="789",
            conversions=[_click()],
            validate_only=True,
        )

        self.assertIs(
            upload.upload_click_conversions.call_args.kwargs["validate_only"], True
        )
        self.assertTrue(result["validate_only"])
        self.assertEqual(result["results"][0]["status"], "validated")


class TestUploadPartialFailure(unittest.TestCase):

    @patch(PATCHES[0])
    @patch(PATCHES[1])
    @patch(PATCHES[2])
    def test_failed_row_is_reported_by_index_and_others_succeed(
        self, cli, typ, svc
    ):
        response = SimpleNamespace(
            partial_failure_error=_partial_failure(1, "Unparseable gclid."),
            results=[SimpleNamespace(gclid="g-0"), SimpleNamespace(gclid="")],
        )
        _wire(cli, typ, svc, response)

        from ads_mcp.tools.conversion_uploads import upload_offline_conversions
        result = upload_offline_conversions(
            customer_id="123",
            conversion_action_id="789",
            conversions=[_click(gclid="g-0"), _click(gclid="bad")],
        )

        self.assertEqual(result["submitted"], 2)
        self.assertEqual(result["succeeded"], 1)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["results"][0]["status"], "ok")
        self.assertEqual(result["results"][1]["status"], "error")
        self.assertIn("Unparseable gclid.", result["results"][1]["errors"][0])
        self.assertIn("gclid", result["results"][1]["errors"][0])

    @patch(PATCHES[0])
    @patch(PATCHES[1])
    @patch(PATCHES[2])
    def test_whole_request_failure_names_the_field(self, cli, typ, svc):
        upload, _ = _wire(cli, typ, svc)
        element = MagicMock()
        element.field_name = "conversion_action"
        error = MagicMock()
        error.message = "The conversion action is not eligible for uploads."
        error.location.field_path_elements = [element]
        failure = MagicMock()
        failure.errors = [error]
        from google.ads.googleads.errors import GoogleAdsException
        upload.upload_click_conversions.side_effect = GoogleAdsException(
            None, None, failure, "req-9"
        )

        from ads_mcp.tools.conversion_uploads import upload_offline_conversions
        from fastmcp.exceptions import ToolError
        with self.assertRaises(ToolError) as ctx:
            upload_offline_conversions(
                customer_id="123",
                conversion_action_id="789",
                conversions=[_click()],
            )
        self.assertIn("[field: conversion_action]", str(ctx.exception))


class TestImportOrder(unittest.TestCase):
    """Either conversion module may be imported first without a circular import.

    The coordinator auto-loads every tool module, so a tool module that imports
    a sibling tool module only works if the sibling happens to load first.
    """

    def _import(self, module):
        result = subprocess.run(
            [sys.executable, "-c", f"import {module}"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-800:])

    def test_conversions_first(self):
        self._import("ads_mcp.tools.conversions")

    def test_conversion_uploads_first(self):
        self._import("ads_mcp.tools.conversion_uploads")


if __name__ == "__main__":
    unittest.main()
