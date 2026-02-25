"""Tests for daemon contracts and server stubs."""

import json
import unittest

from daemon.contracts import error_response, ok_response
from daemon.server import DaemonServiceBase
from daemon.validators import ValidationError, validate_port, validate_protocol, validate_zone


class TestDaemonDBusContracts(unittest.TestCase):
    """Validate daemon envelopes and basic server behavior."""

    def test_ok_response_serialization(self):
        payload = ok_response({"hello": "world"})
        parsed = json.loads(payload)
        self.assertTrue(parsed["ok"])
        self.assertEqual(parsed["data"]["hello"], "world")
        self.assertIsNone(parsed["error"])

    def test_error_response_serialization(self):
        payload = error_response("validation_error", "bad input")
        parsed = json.loads(payload)
        self.assertFalse(parsed["ok"])
        self.assertEqual(parsed["error"]["code"], "validation_error")

    def test_ping_base_service(self):
        svc = DaemonServiceBase()
        parsed = json.loads(svc.Ping())
        self.assertTrue(parsed["ok"])
        self.assertEqual(parsed["data"], "pong")

    def test_validators_reject_bad_values(self):
        with self.assertRaises(ValidationError):
            validate_port("99999")
        with self.assertRaises(ValidationError):
            validate_protocol("icmp")
        with self.assertRaises(ValidationError):
            validate_zone("../root")

