"""Opt-in Windows Credential Manager storage for one Streamlabs session token.

The credential is scoped to the signed-in Windows user. StreamKey never writes
it to plaintext configuration files or exports it to the T0G Nexus backend.
"""
import ctypes
from ctypes import wintypes
import sys

TARGET = "T0G.StreamKey.StreamlabsToken"
CRED_TYPE_GENERIC = 1
CRED_PERSIST_LOCAL_MACHINE = 2
ERROR_NOT_FOUND = 1168


class TokenStoreError(RuntimeError):
    pass


class FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]


class CREDENTIAL(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", FILETIME),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


PCREDENTIAL = ctypes.POINTER(CREDENTIAL)


class WindowsTokenStore:
    def __init__(self, api=None):
        if api is None:
            if sys.platform != "win32":
                raise TokenStoreError("Saved sessions require Windows Credential Manager.")
            api = ctypes.WinDLL("Advapi32", use_last_error=True)
        self._api = api
        self._api.CredWriteW.argtypes = [PCREDENTIAL, wintypes.DWORD]
        self._api.CredWriteW.restype = wintypes.BOOL
        self._api.CredReadW.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
            ctypes.POINTER(PCREDENTIAL),
        ]
        self._api.CredReadW.restype = wintypes.BOOL
        self._api.CredDeleteW.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
        ]
        self._api.CredDeleteW.restype = wintypes.BOOL
        self._api.CredFree.argtypes = [ctypes.c_void_p]
        self._api.CredFree.restype = None

    @staticmethod
    def _error(action):
        return TokenStoreError(
            f"Windows Credential Manager could not {action} the token "
            f"(error {ctypes.get_last_error()})."
        )

    def save(self, token: str):
        if not isinstance(token, str) or not token.strip() or "\x00" in token:
            raise TokenStoreError("No valid Streamlabs token is connected.")
        raw = token.strip().encode("utf-16-le")
        if len(raw) > 2560:
            raise TokenStoreError("The Streamlabs token is too large to save securely.")
        buffer = ctypes.create_string_buffer(raw)
        record = CREDENTIAL()
        record.Type = CRED_TYPE_GENERIC
        record.TargetName = TARGET
        record.UserName = "T0G StreamKey"
        record.CredentialBlobSize = len(raw)
        record.CredentialBlob = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))
        record.Persist = CRED_PERSIST_LOCAL_MACHINE
        if not self._api.CredWriteW(ctypes.byref(record), 0):
            raise self._error("save")

    def load(self) -> str | None:
        credential = PCREDENTIAL()
        if not self._api.CredReadW(
            TARGET, CRED_TYPE_GENERIC, 0, ctypes.byref(credential)
        ):
            if ctypes.get_last_error() == ERROR_NOT_FOUND:
                return None
            raise self._error("read")
        try:
            size = credential.contents.CredentialBlobSize
            if not size or size % 2 or size > 2560:
                raise TokenStoreError("Saved Streamlabs session data is invalid.")
            raw = ctypes.string_at(credential.contents.CredentialBlob, size)
            return raw.decode("utf-16-le")
        except (UnicodeError, ValueError) as exc:
            raise TokenStoreError("Saved Streamlabs session data is invalid.") from exc
        finally:
            self._api.CredFree(credential)

    def clear(self):
        if not self._api.CredDeleteW(TARGET, CRED_TYPE_GENERIC, 0):
            if ctypes.get_last_error() != ERROR_NOT_FOUND:
                raise self._error("delete")
