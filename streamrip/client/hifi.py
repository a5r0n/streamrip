"""HiFi client implementation.

HiFi is a Tidal proxy API that provides access to Tidal's music catalog
without requiring authentication. It's available at https://hifi.401658.xyz/
"""

import logging

from ..config import Config
from ..exceptions import NonStreamableError
from .client import Client
from .downloadable import BasicDownloadable

logger = logging.getLogger("streamrip")

QUALITY_MAP = {
    0: "LOW",        # AAC 96 kbps
    1: "HIGH",       # AAC 320 kbps
    2: "LOSSLESS",   # FLAC 16/44.1
    3: "HI_RES",     # MQA/HI_RES_LOSSLESS
}


class HifiClient(Client):
    """HiFi client for Tidal proxy API."""

    source = "hifi"
    max_quality = 3

    def __init__(self, config: Config):
        self.logged_in = False
        self.global_config = config
        self.config = config.session.hifi
        self.rate_limiter = self.get_rate_limiter(
            config.session.downloads.requests_per_minute,
        )
        self.base_url = self.config.base_url

    async def login(self):
        """Login to HiFi API.
        
        HiFi doesn't require authentication - it's a public Tidal proxy.
        """
        self.session = await self.get_session(
            verify_ssl=self.global_config.session.downloads.verify_ssl
        )
        self.logged_in = True
        logger.info("HiFi client initialized (no authentication required)")

    async def get_metadata(self, item_id: str, media_type: str) -> dict:
        """Get metadata for a track, album, playlist, or artist.

        Args:
            item_id: The ID of the item
            media_type: One of "track", "album", "playlist", "artist"

        Returns:
            Dictionary containing the metadata
        """
        assert media_type in ("track", "album", "playlist", "artist"), media_type

        if media_type == "track":
            return await self._get_track(item_id)
        elif media_type == "album":
            return await self._get_album(item_id)
        elif media_type == "playlist":
            return await self._get_playlist(item_id)
        elif media_type == "artist":
            return await self._get_artist(item_id)

    async def _get_track(self, track_id: str) -> dict:
        """Get track metadata from HiFi API."""
        url = f"{self.base_url}/track/"
        params = {"id": track_id}
        
        async with self.rate_limiter:
            async with self.session.get(url, params=params) as resp:
                if resp.status != 200:
                    raise NonStreamableError(f"Failed to get track {track_id}: {resp.status}")
                data = await resp.json()
        
        logger.debug(f"Track metadata: {data}")
        return data

    async def _get_album(self, album_id: str) -> dict:
        """Get album metadata from HiFi API."""
        url = f"{self.base_url}/album/"
        params = {"id": album_id}
        
        async with self.rate_limiter:
            async with self.session.get(url, params=params) as resp:
                if resp.status != 200:
                    raise NonStreamableError(f"Failed to get album {album_id}: {resp.status}")
                data = await resp.json()
        
        logger.debug(f"Album metadata: {data}")
        return data

    async def _get_playlist(self, playlist_id: str) -> dict:
        """Get playlist metadata from HiFi API."""
        url = f"{self.base_url}/playlist/"
        params = {"id": playlist_id}
        
        async with self.rate_limiter:
            async with self.session.get(url, params=params) as resp:
                if resp.status != 200:
                    raise NonStreamableError(f"Failed to get playlist {playlist_id}: {resp.status}")
                data = await resp.json()
        
        logger.debug(f"Playlist metadata: {data}")
        return data

    async def _get_artist(self, artist_id: str) -> dict:
        """Get artist metadata from HiFi API."""
        url = f"{self.base_url}/artist/"
        params = {"id": artist_id}
        
        async with self.rate_limiter:
            async with self.session.get(url, params=params) as resp:
                if resp.status != 200:
                    raise NonStreamableError(f"Failed to get artist {artist_id}: {resp.status}")
                data = await resp.json()
        
        logger.debug(f"Artist metadata: {data}")
        return data

    async def search(self, media_type: str, query: str, limit: int = 100) -> list[dict]:
        """Search for tracks, albums, playlists, or artists.

        Args:
            media_type: One of "track", "album", "playlist", "artist"
            query: Search query string
            limit: Maximum number of results (not used by HiFi API)

        Returns:
            List of search results
        """
        assert media_type in ("track", "album", "playlist", "artist"), media_type
        
        url = f"{self.base_url}/search/"
        params = {"s": query}
        
        async with self.rate_limiter:
            async with self.session.get(url, params=params) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
        
        # HiFi returns all types in the response, filter by requested type
        # The API returns data in format: {"tracks": [...], "albums": [...], ...}
        media_type_key = f"{media_type}s" if media_type != "artist" else "artists"
        
        if media_type_key in data and len(data[media_type_key]) > 0:
            return [data]
        
        return []

    async def get_downloadable(self, track_id: str, quality: int):
        """Get downloadable stream URL for a track.

        Args:
            track_id: The track ID
            quality: Quality level (0-3)

        Returns:
            Downloadable object with stream URL
        """
        quality_str = QUALITY_MAP.get(quality, "LOSSLESS")
        
        # HiFi uses /dash/ endpoint for streaming
        # This returns a DASH manifest that can be streamed directly
        url = f"{self.base_url}/dash/"
        
        # The /dash/ endpoint returns the manifest directly, which can be used as a stream URL
        # We'll use it as the download URL
        stream_url = f"{url}?id={track_id}&quality={quality_str}"
        
        logger.debug(f"Stream URL: {stream_url}")
        
        # Determine extension from quality
        if quality >= 2:
            extension = "flac"
        else:
            extension = "m4a"
        
        return BasicDownloadable(
            session=self.session,
            url=stream_url,
            extension=extension,
        )
