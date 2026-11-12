import unittest
from unittest.mock import Mock, patch

from streamkey.app import StreamKeyWindow
from streamkey.credentials import Credentials
from streamkey.streamlabs import TikTokCategory
from streamkey.token_store import TokenStoreError, WindowsTokenStore


class WindowActionTests(unittest.TestCase):
    def setUp(self):
        self.app = StreamKeyWindow.__new__(StreamKeyWindow)
        for name in (
            "root", "status", "detail", "account_status",
            "server_display", "key_display", "web_button", "save_button",
            "start_button", "stop_button", "copy_server", "copy_key",
            "forget_button", "title_entry", "category_entry",
            "audience_dropdown", "category_list", "category_hint",
            "live_title", "live_game", "live_audience",
        ):
            setattr(self.app, name, Mock())
        self.app._client = Mock()
        self.app._client.token = "example-streamlabs-token"
        self.app._stream_id = ""
        self.app._busy = False
        self.app.credentials = None
        self.app.clipboard_value = None
        self.app.token_store = Mock()
        self.app.live_title.get.return_value = "My LIVE"
        self.app.live_game.get.return_value = "Rust"
        self.app.live_audience.get.return_value = "Everyone"
        self.app._selected_category = TikTokCategory("Rust", "rust-id")
        self.app._category_generation = 0
        self.app._category_after = None
        self.app._category_candidates = []
        self.app._setting_category = False
        self.app._events = Mock()
        self.app._client.get_account.return_value.can_go_live = True

    def test_save_stores_token_only(self):
        self.app.credentials = Credentials.parse("rtmps://example.test/live", "stream-key")
        self.app.save_token()
        self.app.token_store.save.assert_called_once_with("example-streamlabs-token")
        self.app.token_store.clear.assert_not_called()

    def test_save_failure_does_not_claim_success(self):
        self.app.token_store.save.side_effect = TokenStoreError("unavailable")
        self.app.save_token()
        self.app.status.set.assert_called_with("Save failed")

    def test_copy_only_generated_fields(self):
        self.app.copy("key")
        self.app.root.clipboard_append.assert_not_called()
        self.app.credentials = Credentials.parse("rtmps://example.test/live", "stream-key")
        self.app.copy("server")
        self.app.root.clipboard_append.assert_called_with("rtmps://example.test/live")
        self.app.copy("key")
        self.app.root.clipboard_append.assert_called_with("stream-key")

    def test_clear_credentials_preserves_unrelated_clipboard(self):
        self.app.credentials = Credentials.parse("rtmps://example.test/live", "stream-key")
        self.app.clipboard_value = "stream-key"
        self.app.root.clipboard_get.return_value = "someone else's clipboard"
        self.app.clear_credentials()
        self.app.root.clipboard_clear.assert_not_called()
        self.app.server_display.set.assert_called_with("Not generated")
        self.app.key_display.set.assert_called_with("Not generated")

    def test_expired_session_clears_saved_token(self):
        client = self.app._client
        self.app._invalidate_token()
        self.app.token_store.clear.assert_called_once()
        client.disconnect.assert_called_once()
        self.assertIsNone(self.app._client)
        self.app.status.set.assert_called_with("Streamlabs session expired")

    def test_forget_saved_token(self):
        self.app.forget_saved()
        self.app.token_store.clear.assert_called_once()
        self.assertIsNone(self.app._client)

    def test_saved_session_restoration_calls_account(self):
        self.app.token_store.load.return_value = "saved-token"
        with patch("streamkey.app.StreamlabsTikTok") as client_type:
            client_type.return_value.get_account.return_value = "account"
            result = self.app._restore_saved_worker()
        self.assertEqual(result, ("saved-token", "account"))
        client_type.return_value.disconnect.assert_called_once()

    def test_start_sends_title_selected_game_and_everyone(self):
        self.app._task = Mock()
        self.app.start_live()
        action, work = self.app._task.call_args.args
        self.assertEqual(action, "start")
        work()
        self.app._client.start_live.assert_called_once_with(
            "My LIVE", "Rust", False, category_id="rust-id")

    def test_start_sends_18_plus_as_mature(self):
        self.app._task = Mock()
        self.app.live_audience.get.return_value = "18+"
        self.app.start_live()
        self.app._task.call_args.args[1]()
        self.app._client.start_live.assert_called_once_with(
            "My LIVE", "Rust", True, category_id="rust-id")

    def test_start_requires_title_and_selected_game(self):
        self.app._task = Mock()
        self.app.live_title.get.return_value = " "
        self.app.start_live()
        self.app.status.set.assert_called_with("LIVE title required")
        self.app._task.assert_not_called()
        self.app.live_title.get.return_value = "My LIVE"
        self.app._selected_category = None
        self.app.start_live()
        self.app.status.set.assert_called_with("Select a game")
        self.app._task.assert_not_called()

    def test_editing_game_invalidates_selection_and_schedules_search(self):
        self.app._selected_category = TikTokCategory("Rust", "rust-id")
        self.app.live_game.get.return_value = "Rain"
        self.app._category_changed()
        self.assertIsNone(self.app._selected_category)
        self.app.root.after.assert_called_once()
        self.assertEqual(self.app.root.after.call_args.args[0], 300)

    def test_stale_search_does_not_update_picker(self):
        self.app._category_generation = 3
        self.app._receive_categories(
            (2, "Rust", self.app._client, [TikTokCategory("Rust", "id")]), None)
        self.app.category_list.insert.assert_not_called()

    def test_current_search_displays_suggestions(self):
        self.app._category_generation = 3
        self.app._receive_categories(
            (3, "Rust", self.app._client, [TikTokCategory("Rust", "id")]), None)
        self.app.category_list.insert.assert_called_once()
        self.app.category_list.grid.assert_called_once()

    def test_close_does_not_end_live_or_erase_saved_token(self):
        self.app.close()
        self.app.token_store.clear.assert_not_called()
        self.app._client.disconnect.assert_called_once()
        self.app.root.destroy.assert_called_once()


if __name__ == "__main__":
    unittest.main()
