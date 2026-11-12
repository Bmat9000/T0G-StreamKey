"""On Windows CI this verifies the actual Credential Manager round trip.

No account credentials are used; the credential value is a dummy test string.
"""
import sys
import unittest

from streamkey.token_store import WindowsTokenStore, TokenStoreError


@unittest.skipUnless(sys.platform == "win32", "Requires Windows Credential Manager")
class TokenStoreIntegrationTests(unittest.TestCase):
    def test_save_load_and_delete(self):
        store = WindowsTokenStore()
        # Restore prior value if one exists, without ever displaying it.
        previous = store.load()
        try:
            store.save("unit-test-only-t0g-streamkey")
            self.assertEqual(store.load(), "unit-test-only-t0g-streamkey")
            store.clear()
            self.assertIsNone(store.load())
        finally:
            if previous is None:
                store.clear()
            else:
                store.save(previous)

    def test_reject_empty_token(self):
        store = WindowsTokenStore()
        with self.assertRaises(TokenStoreError):
            store.save("  ")
