"""Stable decorative profiles, independent of editorial content or data."""

from hashlib import sha256


def topography_style(route: str) -> str:
    """Give each address its own crop, scale, wash and slow motion period."""
    seed = sha256(str(route).encode("utf-8")).digest()
    return (
        "--topo-size: %dpx; --topo-offset: -%dpx; --topo-x: %d%%; "
        "--topo-flip: %d; --topo-wash-x: %d%%; --topo-wash-y: %d%%; "
        "--topo-duration: %ds"
    ) % (
        1160 + int.from_bytes(seed[:2], "big") % 560,
        int.from_bytes(seed[2:4], "big") % 720,
        20 + seed[4] % 61,
        -1 if seed[5] % 2 else 1,
        12 + seed[6] % 77,
        15 + seed[7] % 71,
        38 + seed[8] % 19,
    )
