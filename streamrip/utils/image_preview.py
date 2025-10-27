"""Utility for displaying images in the terminal during search previews."""

import logging
import tempfile
from pathlib import Path

import aiohttp
from PIL import Image

logger = logging.getLogger("streamrip")


class ImagePreview:
    """Handler for terminal image previews."""

    def __init__(self, cache_dir: str | None = None):
        """Initialize image preview handler.

        Args:
        ----
            cache_dir: Directory to cache downloaded images. If None, uses temp directory.

        """
        if cache_dir is None:
            self.cache_dir = Path(tempfile.gettempdir()) / "streamrip_preview_cache"
        else:
            self.cache_dir = Path(cache_dir)

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Image preview cache dir: {self.cache_dir}")

    async def download_image(
        self, session: aiohttp.ClientSession, url: str
    ) -> str | None:
        """Download an image from a URL and cache it.

        Args:
        ----
            session: aiohttp session for downloading
            url: URL of the image to download

        Returns:
        -------
            Path to the cached image file, or None if download failed

        """
        # Generate cache filename from URL hash
        import hashlib

        url_hash = hashlib.md5(url.encode()).hexdigest()
        cache_path = self.cache_dir / f"{url_hash}.jpg"

        if cache_path.exists():
            logger.debug(f"Using cached image: {cache_path}")
            return str(cache_path)

        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status != 200:
                    logger.warning(f"Failed to download image from {url}: {resp.status}")
                    return None

                image_data = await resp.read()
                # Save to cache
                cache_path.write_bytes(image_data)
                logger.debug(f"Downloaded and cached image: {cache_path}")
                return str(cache_path)

        except Exception as e:
            logger.debug(f"Error downloading image from {url}: {e}")
            return None

    def create_ascii_art(self, image_path: str, width: int = 40) -> str:
        """Convert an image to ASCII art.

        Args:
        ----
            image_path: Path to the image file
            width: Width of the ASCII art in characters

        Returns:
        -------
            ASCII art representation of the image

        """
        try:
            img = Image.open(image_path)
            # Calculate height to maintain aspect ratio
            aspect_ratio = img.height / img.width
            height = int(width * aspect_ratio * 0.5)  # 0.5 factor for character aspect

            # Resize image
            img = img.resize((width, height))
            img = img.convert("L")  # Convert to grayscale

            # ASCII characters from dark to light
            ascii_chars = " .:-=+*#%@"

            ascii_art = []
            for y in range(height):
                line = ""
                for x in range(width):
                    pixel = img.getpixel((x, y))
                    # Map pixel value (0-255) to ASCII char
                    char_idx = pixel * len(ascii_chars) // 256
                    line += ascii_chars[char_idx]
                ascii_art.append(line)

            return "\n".join(ascii_art)

        except Exception as e:
            logger.debug(f"Error creating ASCII art: {e}")
            return ""

    def create_terminal_image(self, image_path: str, max_width: int = 40) -> str:
        """Create a terminal-renderable image representation.

        Uses term-image library for supported terminals, falls back to ASCII art.

        Args:
        ----
            image_path: Path to the image file
            max_width: Maximum width for the image in characters

        Returns:
        -------
            String representation that can be printed to terminal

        """
        try:
            # Try using term-image for better quality display
            from term_image.image import from_file

            try:
                img = from_file(image_path)
                # Set size (width in columns)
                img.set_size(width=max_width)
                # Get the string representation
                return str(img)
            except Exception as e:
                logger.debug(f"term-image rendering failed: {e}, falling back to ASCII")
                # Fall back to ASCII art
                return self.create_ascii_art(image_path, width=max_width)

        except ImportError:
            # term-image not available, use ASCII art
            logger.debug("term-image not installed, using ASCII art")
            return self.create_ascii_art(image_path, width=max_width)

    def cleanup_cache(self, max_age_hours: int = 24):
        """Remove cached images older than max_age_hours.

        Args:
        ----
            max_age_hours: Maximum age of cached images in hours

        """
        import time

        current_time = time.time()
        max_age_seconds = max_age_hours * 3600

        for file_path in self.cache_dir.glob("*.jpg"):
            if current_time - file_path.stat().st_mtime > max_age_seconds:
                try:
                    file_path.unlink()
                    logger.debug(f"Removed old cached image: {file_path}")
                except Exception as e:
                    logger.debug(f"Error removing cached image: {e}")


# Global instance for use across the application
_image_preview = None


def get_image_preview() -> ImagePreview:
    """Get or create the global ImagePreview instance."""
    global _image_preview
    if _image_preview is None:
        _image_preview = ImagePreview()
    return _image_preview
