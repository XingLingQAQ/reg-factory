import unittest
from unittest.mock import patch

import register
from webui.scripts import SCRIPTS


def _script(script_id):
    return next(item for item in SCRIPTS if item["id"] == script_id)


class RegistrationSchemaTests(unittest.TestCase):
    def test_both_grok_tasks_expose_sub2api_import(self):
        for script_id in ("register_grok", "register_grok_browser"):
            flags = {item["flag"] for item in _script(script_id)["args"]}
            self.assertIn("--sub2api", flags)
            self.assertIn("--sub2api-group", flags)

    def test_grok_browser_exposes_mailbox_rotation(self):
        args = {item["flag"]: item for item in _script("register_grok_browser")["args"]}
        self.assertEqual(args["--mailbox-attempts"]["default"], 6)

    def test_claude_defaults_to_latest_rt(self):
        args = {item["flag"]: item for item in _script("register_claude")["args"]}
        self.assertTrue(args["--latest-rt"]["default"])

    def test_claude_graph_reader_receives_client_and_timestamp(self):
        with patch("common.mailbox.get_link_by_token", return_value="https://claude.ai/magic-link#ok") as reader:
            result = register.get_magic_link_by_token(
                "user@example.com",
                "refresh-token",
                client_id="client-id",
                max_wait=12,
                received_after=123.0,
            )
        self.assertEqual(result, "https://claude.ai/magic-link#ok")
        self.assertEqual(reader.call_args.kwargs["client_id"], "client-id")
        self.assertEqual(reader.call_args.kwargs["received_after"], 123.0)


if __name__ == "__main__":
    unittest.main()
