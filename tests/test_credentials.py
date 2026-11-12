import unittest
from unittest.mock import Mock

from streamkey.app import StreamKeyWindow
from streamkey.credentials import Credentials


class CredentialTests(unittest.TestCase):
    def test_valid_credentials_and_redacted_repr(self):
        for scheme in ("rtmp", "rtmps"):
            with self.subTest(scheme=scheme):
                url = f"{scheme}://ingest.example:443/live?token=example"
                pair = Credentials.parse(f" {url} ", " sample-key ")
                self.assertEqual(pair.server, url)
                self.assertEqual(pair.key, "sample-key")
                self.assertNotIn(url, repr(pair))
                self.assertNotIn(pair.key, repr(pair))

    def test_invalid_servers(self):
        for url in ("", "https://example.test", "rtmp:///live", "rtmp://user:pass@example.test",
                    "rtmp://bad host/live", "rtmp://example.test:99999",
                    "rtmp://example.test:0", "rtmp://[broken", "rtmp://example.test/#fragment",
                    "rtmp://example.test/a\\b", "rtmp://example.test/a\nb"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                Credentials.parse(url, "sample-key")

    def test_invalid_keys(self):
        for key in ("", "bad key", "bad\nkey", "bad\x00key"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                Credentials.parse("rtmp://example.test/live", key)


class WindowActionTests(unittest.TestCase):
    def setUp(self):
        self.app = StreamKeyWindow.__new__(StreamKeyWindow)
        for name in ("root", "server", "key", "status", "detail", "copy_server", "copy_key",
                     "key_entry", "visibility", "settings_status"):
            setattr(self.app, name, Mock())
        self.app.credentials = None
        self.app.clipboard_value = None
        self.app.revealed = False
        self.app.server.get.return_value = "rtmps://example.test/live"
        self.app.key.get.return_value = "sample-key"

    def test_apply_and_copy(self):
        self.app.apply()
        self.app.copy("server")
        self.app.root.clipboard_append.assert_called_with("rtmps://example.test/live")
        self.app.copy("key")
        self.app.root.clipboard_append.assert_called_with("sample-key")

    def test_edit_invalidates_previous_pair(self):
        self.app.apply()
        self.app.on_edit()
        self.app.copy("key")
        self.app.root.clipboard_append.assert_not_called()
        self.app.copy_key.state.assert_called_with(["disabled"])

    def test_clear_hides_key_and_removes_owned_clipboard_value(self):
        self.app.apply()
        self.app.copy("key")
        self.app.root.clipboard_get.return_value = "sample-key"
        self.app.toggle_key()
        self.app.key_entry.configure.assert_called_with(show="")
        self.app.root.clipboard_clear.reset_mock()
        self.app.clear_session()
        self.app.root.clipboard_clear.assert_called_once()
        self.app.server.set.assert_called_with("")
        self.app.key.set.assert_called_with("")
        self.app.key_entry.configure.assert_called_with(show="•")

    def test_clear_preserves_other_clipboard_value(self):
        self.app.clipboard_value = "sample-key"
        self.app.root.clipboard_get.return_value = "new clipboard content"
        self.app.clear_data()
        self.app.root.clipboard_clear.assert_not_called()

    def test_close_clears_local_state(self):
        self.app.close()
        self.app.key.set.assert_called_with("")
        self.app.root.destroy.assert_called_once()


if __name__ == "__main__":
    unittest.main()
