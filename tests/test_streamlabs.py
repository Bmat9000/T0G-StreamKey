import base64
import hashlib
import os
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from streamkey.streamlabs import (
    AccountInfo, SessionRejected, StreamlabsError, StreamlabsTikTok,
    _pkce, load_token_from_pc,
)


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.transport = Mock()
        self.client = StreamlabsTikTok("test-only-token", session=self.transport)

    def response(self, json_body, code=200):
        response = Mock()
        response.status_code = code
        response.json.return_value = json_body
        self.transport.request.return_value = response

    def test_pkce_challenge_matches_verifier(self):
        verifier, challenge = _pkce()
        self.assertEqual(len(verifier), 128)
        self.assertEqual(base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()
        ).decode().rstrip("="), challenge)

    def test_account_and_category(self):
        self.response({
            "user": {"username": "exampleuser"},
            "application_status": {"status": "approved"},
            "can_be_live": True,
            "categories": [
                {"full_name": "Rust", "game_mask_id": "123"},
                {"full_name": "Other", "game_mask_id": ""},
            ],
        })
        self.assertEqual(self.client.get_account(), AccountInfo("exampleuser", "approved", True))
        self.assertEqual(self.client.resolve_category("rust"), "123")
        self.assertEqual(self.client.resolve_category("Unknown"), "123")
        self.assertEqual(self.client.resolve_category(""), "")

    def test_start_live_returns_key_without_exposing_it_in_repr(self):
        self.response({"id": 321, "rtmp": "rtmps://ingest.example/live", "key": "super-secret"})
        live = self.client.start_live("My stream", "", False)
        self.assertEqual(live.credentials.key, "super-secret")
        self.assertEqual(live.stream_id, "321")
        self.assertNotIn("super-secret", repr(live))
        _, args, kwargs = self.transport.request.mock_calls[-1]
        self.assertEqual(args[:2], ("POST", "https://streamlabs.com/api/v5/slobs/tiktok/stream/start"))
        self.assertIn(("audience_type", (None, "0")), kwargs["files"])
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-only-token")

    def test_bad_live_response_rejected(self):
        self.response({"message": "not permitted"})
        with self.assertRaisesRegex(StreamlabsError, "valid RTMP"):
            self.client.start_live("Test")

    def test_end_live(self):
        self.response({"success": True})
        self.client.end_live("321")
        self.assertEqual(self.transport.request.call_args.args[:2],
                         ("POST", "https://streamlabs.com/api/v5/slobs/tiktok/stream/321/end"))

    def test_rejected_session_erases_token(self):
        self.response({}, code=403)
        with self.assertRaises(SessionRejected):
            self.client.get_account()
        with self.assertRaises(SessionRejected):
            self.client.get_account()
        self.assertEqual(self.transport.request.call_count, 1)

    def test_local_desktop_token_scan_requires_explicit_invocation(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"APPDATA": folder}):
            location = Path(folder) / "slobs-client" / "Local Storage" / "leveldb"
            location.mkdir(parents=True)
            (location / "00001.log").write_text('{"apiToken":"cafebabe"}')
            self.assertEqual(load_token_from_pc(), "cafebabe")


if __name__ == "__main__":
    unittest.main()
