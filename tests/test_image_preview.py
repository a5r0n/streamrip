"""Tests for image preview functionality."""

import asyncio
import os
import tempfile
from pathlib import Path

import pytest
from PIL import Image

from streamrip.utils.image_preview import ImagePreview


@pytest.fixture
def temp_cache_dir():
    """Create a temporary cache directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_image():
    """Create a sample image for testing."""
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        img = Image.new("RGB", (100, 100), color="red")
        img.save(f.name)
        yield f.name
    os.unlink(f.name)


def test_image_preview_init(temp_cache_dir):
    """Test ImagePreview initialization."""
    preview = ImagePreview(cache_dir=temp_cache_dir)
    assert preview.cache_dir == Path(temp_cache_dir)
    assert preview.cache_dir.exists()


def test_create_ascii_art(sample_image):
    """Test ASCII art creation from image."""
    preview = ImagePreview()
    ascii_art = preview.create_ascii_art(sample_image, width=20)
    
    assert isinstance(ascii_art, str)
    assert len(ascii_art) > 0
    # Should contain ASCII characters
    assert any(c in ascii_art for c in " .:-=+*#%@")


def test_create_ascii_art_with_different_width(sample_image):
    """Test ASCII art with different widths."""
    preview = ImagePreview()
    ascii_art_small = preview.create_ascii_art(sample_image, width=10)
    ascii_art_large = preview.create_ascii_art(sample_image, width=40)
    
    # Larger width should produce more characters
    assert len(ascii_art_large) > len(ascii_art_small)


def test_create_terminal_image_fallback(sample_image):
    """Test terminal image creation falls back to ASCII."""
    preview = ImagePreview()
    result = preview.create_terminal_image(sample_image, max_width=20)
    
    assert isinstance(result, str)
    assert len(result) > 0


def test_cleanup_cache(temp_cache_dir):
    """Test cache cleanup."""
    preview = ImagePreview(cache_dir=temp_cache_dir)
    
    # Create some test files
    test_file = preview.cache_dir / "test.jpg"
    test_file.write_bytes(b"test")
    
    # Cleanup shouldn't remove fresh files
    preview.cleanup_cache(max_age_hours=1)
    assert test_file.exists()
    
    # Modify timestamp to be old
    import time
    old_time = time.time() - (25 * 3600)  # 25 hours ago
    os.utime(test_file, (old_time, old_time))
    
    # Now cleanup should remove it
    preview.cleanup_cache(max_age_hours=24)
    assert not test_file.exists()


def test_ascii_art_handles_invalid_image():
    """Test that invalid image path is handled gracefully."""
    preview = ImagePreview()
    result = preview.create_ascii_art("/nonexistent/image.jpg", width=20)
    
    # Should return empty string on error
    assert result == ""
