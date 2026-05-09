import os
import unittest
from pathlib import Path

from xauusd_scalp_master.config import env_bool, load_env_file, missing_keys, quote_required_keys, redact


class ConfigTests(unittest.TestCase):
    def test_load_env_file_sets_missing_values(self):
        env_path = Path(__file__).with_name("_tmp_config.env")
        env_path.write_text(
            "CALLMEBOT_WHATSAPP_PHONE=12068145743\n"
            "CALLMEBOT_WHATSAPP_APIKEY='7448772'\n",
            encoding="utf-8",
        )
        original_phone = os.environ.pop("CALLMEBOT_WHATSAPP_PHONE", None)
        original_key = os.environ.pop("CALLMEBOT_WHATSAPP_APIKEY", None)
        try:
            load_env_file(env_path)
            self.assertEqual(os.environ["CALLMEBOT_WHATSAPP_PHONE"], "12068145743")
            self.assertEqual(os.environ["CALLMEBOT_WHATSAPP_APIKEY"], "7448772")
        finally:
            env_path.unlink(missing_ok=True)
            os.environ.pop("CALLMEBOT_WHATSAPP_PHONE", None)
            os.environ.pop("CALLMEBOT_WHATSAPP_APIKEY", None)
            if original_phone is not None:
                os.environ["CALLMEBOT_WHATSAPP_PHONE"] = original_phone
            if original_key is not None:
                os.environ["CALLMEBOT_WHATSAPP_APIKEY"] = original_key

    def test_redact(self):
        self.assertEqual(redact("7448772"), "74...72")
        self.assertEqual(redact("12068145743"), "1206...5743")

    def test_missing_keys_and_env_bool(self):
        original = os.environ.pop("XAU_TEST_BOOL", None)
        try:
            self.assertIn("XAU_TEST_BOOL", missing_keys(["XAU_TEST_BOOL"]))
            os.environ["XAU_TEST_BOOL"] = "true"
            self.assertTrue(env_bool("XAU_TEST_BOOL"))
            self.assertEqual(missing_keys(["XAU_TEST_BOOL"]), [])
        finally:
            os.environ.pop("XAU_TEST_BOOL", None)
            if original is not None:
                os.environ["XAU_TEST_BOOL"] = original

    def test_quote_required_keys_prefers_goldapi_net_source(self):
        originals = {key: os.environ.get(key) for key in ["QUOTE_SOURCE", "GOLDAPI_KEY", "GOLDAPI_NET_KEY"]}
        try:
            os.environ["QUOTE_SOURCE"] = "goldapi-net"
            os.environ.pop("GOLDAPI_KEY", None)
            os.environ.pop("GOLDAPI_NET_KEY", None)
            self.assertEqual(quote_required_keys(), ["GOLDAPI_NET_KEY"])
        finally:
            for key, value in originals.items():
                os.environ.pop(key, None)
                if value is not None:
                    os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
