"""
Image utility functions for processing and saving generated images.

Pillow is an optional dependency — import lazily so the core package
works without it.  Install via: pip install 'eq-chatbot-core[image]'
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path


def parse_size(s: str) -> tuple[int, int]:
    """Parse a WxH size string into (width, height).

    Args:
        s: Size string, e.g. '1024x768'

    Returns:
        Tuple of (width, height) as integers

    Raises:
        ValueError: If the string cannot be parsed
    """
    parts = s.lower().split("x")
    if len(parts) != 2:
        raise ValueError(f"Invalid size format '{s}'. Expected 'WxH' (e.g. '1024x1024')")
    try:
        w, h = int(parts[0]), int(parts[1])
    except ValueError as exc:
        raise ValueError(f"Invalid size format '{s}': dimensions must be integers") from exc
    if w <= 0 or h <= 0:
        raise ValueError(f"Invalid size '{s}': dimensions must be positive integers")
    return w, h


def save_png(data: bytes, path: str | Path, base_dir: str | Path | None = None) -> Path:
    """Write raw image bytes to a file.

    Does not require Pillow — writes bytes directly.

    Args:
        data: Raw image bytes (PNG or other format)
        path: Destination file path
        base_dir: Optional containing directory. When given, ``path`` must resolve
            to a location inside ``base_dir``; otherwise a ``ValueError`` is raised.
            Pass this whenever the filename portion of ``path`` originates from
            untrusted input (e.g. a model response or an asset spec) to prevent
            path traversal / absolute-path escapes.

    Returns:
        Resolved Path of the written file

    Raises:
        ValueError: If ``base_dir`` is given and the resolved destination falls
            outside it.
    """
    dest = Path(path).resolve()

    if base_dir is not None:
        base = Path(base_dir).resolve()
        if base != dest and base not in dest.parents:
            raise ValueError(f"Refusing to write outside the base directory: '{dest}' is not within '{base}'.")

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return dest


def _require_pillow():
    """Import and return PIL.Image, raising a clear error if not installed."""
    try:
        from PIL import Image  # type: ignore[import]

        return Image
    except ImportError as exc:
        raise ImportError(
            "Pillow is required for image processing. Install with: pip install 'eq-chatbot-core[image]'"
        ) from exc


def fit_to(data: bytes, width: int, height: int, mode: str = "cover") -> bytes:
    """Resize image bytes to the target dimensions.

    Args:
        data: Input image bytes
        width: Target width in pixels
        height: Target height in pixels
        mode:
            - 'cover'   — center-crop to target aspect ratio, then resize (fills frame)
            - 'contain' — fit inside target with transparent padding (letterbox)
            - 'stretch' — resize directly without maintaining aspect ratio

    Returns:
        PNG image bytes at the requested dimensions

    Raises:
        ImportError: If Pillow is not installed
        ValueError: If mode is not one of 'cover', 'contain', 'stretch'
    """
    Image = _require_pillow()

    if mode not in ("cover", "contain", "stretch"):
        raise ValueError(f"Invalid mode '{mode}'. Expected 'cover', 'contain', or 'stretch'")

    src = Image.open(BytesIO(data))

    if mode == "stretch":
        result = src.resize((width, height), Image.LANCZOS)

    elif mode == "cover":
        # Center-crop to match the target aspect ratio, then resize.
        src_w, src_h = src.size
        target_ratio = width / height
        src_ratio = src_w / src_h

        if src_ratio > target_ratio:
            # Source is wider — crop left/right
            new_w = int(src_h * target_ratio)
            left = (src_w - new_w) // 2
            cropped = src.crop((left, 0, left + new_w, src_h))
        else:
            # Source is taller — crop top/bottom
            new_h = int(src_w / target_ratio)
            top = (src_h - new_h) // 2
            cropped = src.crop((0, top, src_w, top + new_h))

        result = cropped.resize((width, height), Image.LANCZOS)

    else:  # contain
        # Fit inside the target box, preserving aspect ratio, with transparent padding.
        src.thumbnail((width, height), Image.LANCZOS)
        result = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        paste_x = (width - src.size[0]) // 2
        paste_y = (height - src.size[1]) // 2
        # Convert to RGBA for compositing if needed
        src_rgba = src.convert("RGBA")
        result.paste(src_rgba, (paste_x, paste_y), src_rgba)

    buf = BytesIO()
    result.save(buf, format="PNG")
    return buf.getvalue()
