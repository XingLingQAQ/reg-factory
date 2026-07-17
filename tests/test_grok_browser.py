import unittest
import inspect
from unittest.mock import MagicMock, patch

import register_grok
import register_grok_http


class GrokBrowserTests(unittest.TestCase):
    def test_stealth_avoids_global_runtime_monkeypatches(self):
        script = register_grok.GROK_STEALTH_JS
        self.assertNotIn("Object.defineProperty =", script)
        self.assertNotIn("Error.prepareStackTrace", script)
        self.assertNotIn("HTMLIFrameElement.prototype", script)

    def test_browser_starts_at_xai_signup(self):
        self.assertEqual(
            register_grok.GROK_SIGNUP_URL,
            "https://accounts.x.ai/sign-up?redirect=grok-com&return_to=%2F",
        )

    def test_browser_uses_modern_native_fingerprint(self):
        fingerprint = register_grok.grok_browser_fingerprint()
        self.assertEqual(fingerprint["coreVersion"], "146")
        source = inspect.getsource(register_grok.register_one)
        self.assertNotIn("await inject_grok_stealth", source)
        self.assertIn("await arm_turnstile_hook", source)

    def test_yescaptcha_turnstile_solver_is_available(self):
        fake_solver = MagicMock()
        fake_solver.solve_turnstile.return_value = "token"
        with patch.object(register_grok, "YESCAPTCHA_API_KEY", "key"):
            with patch("xconsole_client.solver.YesCaptchaSolver", return_value=fake_solver):
                token = register_grok._solve_turnstile_yescaptcha(
                    "0x4-test", "https://accounts.x.ai/sign-up"
                )
        self.assertEqual(token, "token")
        self.assertTrue(fake_solver.solve_turnstile.call_args.kwargs["premium"])

    def test_protocol_flow_prefers_yescaptcha(self):
        fake_solver = MagicMock()
        fake_solver.solve_turnstile.return_value = "protocol-token"
        with patch.object(register_grok_http, "YESCAPTCHA_API_KEY", "key"):
            with patch("xconsole_client.solver.YesCaptchaSolver", return_value=fake_solver):
                token = register_grok_http.solve_turnstile(
                    "0x4-test", "https://accounts.x.ai/sign-up"
                )
        self.assertEqual(token, "protocol-token")
        self.assertTrue(fake_solver.solve_turnstile.call_args.kwargs["premium"])

    def test_current_compact_xai_code_format_is_accepted(self):
        import re

        self.assertEqual(re.search(register_grok.GROK_CODE_REGEX, "Code Q5137N").group(1), "Q5137N")
        self.assertEqual(re.search(register_grok.GROK_CODE_REGEX, "Code WIF-W23").group(1), "WIF-W23")


if __name__ == "__main__":
    unittest.main()
