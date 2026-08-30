import unittest
from unittest.mock import patch

from common.k12_workspace import join_workspaces, normalize_workspace_ids, send_workspace_invite


class K12WorkspaceTests(unittest.TestCase):
    def test_normalize_workspace_ids_deduplicates_and_accepts_newlines(self):
        self.assertEqual(
            normalize_workspace_ids("one, two\none\n three "),
            ["one", "two", "three"],
        )

    @patch("common.k12_workspace.requests.post")
    def test_send_workspace_invite_redacts_credentials_from_result(self, post):
        post.return_value.ok = True
        post.return_value.status_code = 200
        post.return_value.text = "ok"
        result = send_workspace_invite("secret-token", "workspace-1", "accept")
        self.assertEqual(result["workspace_id"], "workspace-1")
        self.assertEqual(result["route"], "accept")
        self.assertNotIn("secret-token", result["body"])
        post.assert_called_once()
        self.assertIn("Bearer secret-token", post.call_args.kwargs["headers"]["authorization"])

    @patch("common.k12_workspace.send_workspace_invite")
    def test_join_workspaces_keeps_order(self, send):
        send.side_effect = lambda token, workspace, route, **kwargs: {
            "workspace_id": workspace,
            "route": route,
            "ok": True,
        }
        result = join_workspaces("token", ["a", "b"], "request", interval=0)
        self.assertEqual([item["workspace_id"] for item in result], ["a", "b"])
        self.assertEqual(send.call_count, 2)


if __name__ == "__main__":
    unittest.main()
