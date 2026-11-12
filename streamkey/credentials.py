"""Validate credentials locally without contacting the streaming service."""

from dataclasses import dataclass, field
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Credentials:
    server: str = field(repr=False)
    key: str = field(repr=False)

    @classmethod
    def parse(cls, server: str, key: str) -> "Credentials":
        server, key = server.strip(), key.strip()
        try:
            url = urlsplit(server)
            valid_server = (
                url.scheme in ("rtmp", "rtmps")
                and bool(url.hostname)
                and url.username is None
                and url.password is None
                and not url.fragment
                and url.port != 0
                and not any(character.isspace() or ord(character) < 32
                            or character in "\\\\" for character in server)
            )
        except ValueError:
            valid_server = False
        if not valid_server:
            raise ValueError("Enter an RTMP or RTMPS server URL with a valid host.")
        if not key or any(character.isspace() or ord(character) < 32
                          or ord(character) == 127 for character in key):
            raise ValueError("Enter a stream key without spaces or line breaks.")
        return cls(server, key)
