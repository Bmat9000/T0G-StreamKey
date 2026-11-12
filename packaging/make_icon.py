"""Generate the StreamKey Windows icon from the app's original key mark."""

import struct
import sys
from pathlib import Path

SIZE = 48
BACKGROUND = bytes.fromhex("173a39")
ACCENT = bytes.fromhex("80ebcf")


def near_segment(x, y, start, end):
    dx, dy = end[0] - start[0], end[1] - start[1]
    fraction = ((x - start[0]) * dx + (y - start[1]) * dy) / (dx * dx + dy * dy)
    fraction = max(0, min(1, fraction))
    return (x - start[0] - fraction * dx) ** 2 + (y - start[1] - fraction * dy) ** 2 <= 4


def pixel(x, y):
    ring = 6 ** 2 <= (x - 17) ** 2 + (y - 18) ** 2 <= 10 ** 2
    segments = (((23, 24), (37, 38)), ((37, 38), (41, 34)), ((32, 33), (36, 29)))
    return ACCENT if ring or any(near_segment(x, y, a, b) for a, b in segments) else BACKGROUND


def make_icon(path):
    # Windows DIBs store rows bottom-up in BGRA order.
    pixels = b"".join(
        pixel(x, y)[::-1] + bytes([255])
        for y in reversed(range(SIZE))
        for x in range(SIZE)
    )
    mask_stride = ((SIZE + 31) // 32) * 4
    mask = bytes(mask_stride * SIZE)
    dib = struct.pack("<IiiHHIIiiII", 40, SIZE, SIZE * 2, 1, 32, 0, len(pixels), 0, 0, 0, 0)
    payload = dib + pixels + mask
    header = struct.pack("<HHH", 0, 1, 1)
    entry = struct.pack("<BBBBHHII", SIZE, SIZE, 0, 0, 1, 32, len(payload), 22)
    path.write_bytes(header + entry + payload)


if __name__ == "__main__":
    make_icon(Path(sys.argv[1]))
