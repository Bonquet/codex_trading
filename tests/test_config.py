import os
import unittest
from pathlib import Path

from xauusd_scalp_master.config import load_env_file, redact


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


if __name__ == "__main__":
    unittest.main()
