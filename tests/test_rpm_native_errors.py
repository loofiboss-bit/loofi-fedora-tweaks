"""Native libdnf5 SWIG exceptions must not escape the helper boundary."""
import json
import unittest
from unittest.mock import patch

from services.software import rpm_transaction_helper as helper
from services.software.rpm_transactions import ERROR_MESSAGES, request_args
from services.software import setup_sources_helper as source_helper


@unittest.skipUnless(helper._DNF_ERRORS, "requires the optional native DNF5 bindings")
class NativeRpmErrorTests(unittest.TestCase):
    @patch("services.software.rpm_transaction_helper.signal.alarm")
    @patch("services.software.rpm_transaction_helper.signal.signal")
    @patch("services.software.rpm_transaction_helper.RpmSession")
    @patch("builtins.print")
    def test_real_native_configuration_error_is_redacted(self, output, session, _signal, _alarm):
        import libdnf5.base

        # Construct only an in-memory option; do not load configuration, set up
        # a Base, read repositories or acquire the native package lock.
        base = libdnf5.base.Base()
        try:
            base.get_config().get_cacheonly_option().set("private-invalid-cache-mode")
        except helper._DNF_ERRORS as error:
            native_error = error
        else:
            self.fail("The native enum accepted an invalid value")
        self.assertNotIsInstance(native_error, (RuntimeError, OSError, ValueError))
        session.return_value.resolve.side_effect = native_error
        status = helper.main(["preview", *request_args("install", ("fixture",))])
        self.assertEqual(status, 1)
        output.assert_called_once()
        self.assertEqual(json.loads(output.call_args.args[0]), {
            "available": False, "error_code": "rpm_transaction_unavailable",
            "error": ERROR_MESSAGES["rpm_transaction_unavailable"],
        })
        self.assertNotIn("private", output.call_args.args[0])
        session.return_value.close.assert_called_once()


@unittest.skipUnless(source_helper._RPM_ERRORS, "requires the optional native RPM bindings")
class NativeSourceRpmErrorTests(unittest.TestCase):
    @patch("services.software.setup_sources_helper._rpm_state")
    def test_rpm_database_failure_is_unknown_without_exposing_backend_details(self, state):
        import rpm

        state.side_effect = rpm.error("private RPM database path is corrupt")
        result = source_helper.inspect_source("rpmfusion-free", "system")
        self.assertFalse(result.available)
        self.assertEqual(result.state, "unknown")
        self.assertEqual(result.evidence["state"], "unknown")
        self.assertNotIn("private", result.error)
