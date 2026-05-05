import unittest
from urllib.parse import parse_qs, urlparse

from xauusd_scalp_master.callmebot import CallMeBotClient


class CallMeBotTests(unittest.TestCase):
    def test_send_whatsapp_builds_expected_request(self):
        seen = {}

        def opener(request, timeout):
            seen["url"] = request.full_url
            seen["timeout"] = timeout
            return b"Message queued"

        response = CallMeBotClient(opener=opener).send_whatsapp(
            "NO TRADE\nWait",
            phone="+15551234567",
            apikey="abc123",
            timeout=4,
        )
        parsed = urlparse(seen["url"])
        query = parse_qs(parsed.query)

        self.assertEqual(response, "Message queued")
        self.assertEqual(parsed.path, "/whatsapp.php")
        self.assertEqual(query["phone"], ["+15551234567"])
        self.assertEqual(query["text"], ["NO TRADE\nWait"])
        self.assertEqual(query["apikey"], ["abc123"])
        self.assertEqual(seen["timeout"], 4)

    def test_send_telegram_group_builds_expected_request(self):
        seen = {}

        def opener(request, timeout):
            seen["url"] = request.full_url
            return b"OK"

        response = CallMeBotClient(opener=opener).send_telegram_group(
            "Signal update",
            apikey="group-key",
            html=True,
        )
        parsed = urlparse(seen["url"])
        query = parse_qs(parsed.query)

        self.assertEqual(response, "OK")
        self.assertEqual(parsed.path, "/telegram/group.php")
        self.assertEqual(query["apikey"], ["group-key"])
        self.assertEqual(query["text"], ["Signal update"])
        self.assertEqual(query["html"], ["yes"])

    def test_register_whatsapp_query_builds_expected_request(self):
        seen = {}

        def opener(request, timeout):
            seen["url"] = request.full_url
            return b"Added"

        response = CallMeBotClient(opener=opener).register_whatsapp_query(
            "/signal",
            "https://example.ngrok-free.app/webhook?cmd=signal&token=abc",
            phone="12068145743",
            apikey="7448772",
        )
        parsed = urlparse(seen["url"])
        query = parse_qs(parsed.query)

        self.assertEqual(response, "Added")
        self.assertEqual(parsed.path, "/whatsapp_add.php")
        self.assertEqual(query["phone"], ["12068145743"])
        self.assertEqual(query["apikey"], ["7448772"])
        self.assertEqual(query["query"], ["/signal"])
        self.assertEqual(query["action"], ["https://example.ngrok-free.app/webhook?cmd=signal&token=abc"])


if __name__ == "__main__":
    unittest.main()
