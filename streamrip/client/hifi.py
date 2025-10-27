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
        
        # HiFi returns an array: [track_metadata, stream_info, ...]
        # We only need the track metadata (first element)
        if isinstance(data, list) and len(data) > 0:
            track_data = data[0]
        else:
            track_data = data
        
        logger.debug(f"Track metadata: {track_data}")
        return track_data

    async def _get_album(self, album_id: str) -> dict:
        """Get album metadata from HiFi API."""
        url = f"{self.base_url}/album/"
        params = {"id": album_id}
        
        async with self.rate_limiter:
            async with self.session.get(url, params=params) as resp:
                if resp.status != 200:
                    raise NonStreamableError(f"Failed to get album {album_id}: {resp.status}")
                data = await resp.json()
        
        # HiFi returns an array: [album_metadata, ...]
        # We only need the album metadata (first element)
        if isinstance(data, list) and len(data) > 0:
            album_data = data[0]
        else:
            album_data = data
        
        logger.debug(f"Album metadata: {album_data}")
        return album_data

    async def _get_playlist(self, playlist_id: str) -> dict:
        """Get playlist metadata from HiFi API."""
        url = f"{self.base_url}/playlist/"
        params = {"id": playlist_id}
        
        async with self.rate_limiter:
            async with self.session.get(url, params=params) as resp:
                if resp.status != 200:
                    raise NonStreamableError(f"Failed to get playlist {playlist_id}: {resp.status}")
                data = await resp.json()
        
        # HiFi returns an array: [playlist_metadata, ...]
        # We only need the playlist metadata (first element)
        if isinstance(data, list) and len(data) > 0:
            playlist_data = data[0]
        else:
            playlist_data = data
        
        logger.debug(f"Playlist metadata: {playlist_data}")
        return playlist_data

    async def _get_artist(self, artist_id: str) -> dict:
        """Get artist metadata from HiFi API."""
        url = f"{self.base_url}/artist/"
        params = {"id": artist_id}
        
        async with self.rate_limiter:
            async with self.session.get(url, params=params) as resp:
                if resp.status != 200:
                    raise NonStreamableError(f"Failed to get artist {artist_id}: {resp.status}")
                data = await resp.json()
        
        # HiFi returns an array: [artist_metadata, ...]
        # We only need the artist metadata (first element)
        if isinstance(data, list) and len(data) > 0:
            artist_data = data[0]
        else:
            artist_data = data
        
        logger.debug(f"Artist metadata: {artist_data}")
        return artist_data

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
                    logger.debug(f"Search request failed with status {resp.status}")
                    return []
                data = await resp.json()
        
        logger.debug(f"Search returned {data.get('totalNumberOfItems', 0)} total items")
        
        # HiFi search API returns tracks in {"items": [...]} format
        # For different media types, we need to extract relevant information
        if "items" not in data or len(data["items"]) == 0:
            return []
        
        if media_type == "track":
            # Return tracks as-is
            return [data]
        elif media_type == "artist":
            # Extract unique artists from track results
            artists_dict = {}
            for item in data["items"]:
                if "artist" in item:
                    artist = item["artist"]
                    artist_id = artist.get("id")
                    if artist_id and artist_id not in artists_dict:
                        artists_dict[artist_id] = artist
                # Also check featured artists
                if "artists" in item:
                    for artist in item["artists"]:
                        artist_id = artist.get("id")
                        if artist_id and artist_id not in artists_dict:
                            artists_dict[artist_id] = artist
            
            if artists_dict:
                # Return in format expected by streamrip
                return [{"items": list(artists_dict.values())}]
            return []
        elif media_type == "album":
            # Extract unique albums from track results
            albums_dict = {}
            for item in data["items"]:
                if "album" in item:
                    album = item["album"]
                    album_id = album.get("id")
                    if album_id and album_id not in albums_dict:
                        albums_dict[album_id] = album
            
            if albums_dict:
                return [{"items": list(albums_dict.values())}]
            return []
        elif media_type == "playlist":
            # HiFi search doesn't return playlists directly
            logger.warning("HiFi search does not support playlist search")
            return []
        
        return []

    async def get_downloadable(self, track_id: str, quality: int):
        """Get downloadable stream URL for a track.

        Args:
            track_id: The track ID
            quality: Quality level (0-3)

        Returns:
            Downloadable object with stream URL
        """
        import base64
        import json
        
        quality_str = QUALITY_MAP.get(quality, "LOSSLESS")
        
        # Get track info which includes the manifest
        url = f"{self.base_url}/track/"
        params = {
            "id": track_id,
            "quality": quality_str,
        }
        
        async with self.rate_limiter:
            async with self.session.get(url, params=params) as resp:
                if resp.status != 200:
                    # Try lower quality if current quality fails
                    if quality > 0:
                        logger.warning(
                            f"Failed to get quality {quality_str} for track {track_id}, trying lower quality"
                        )
                        return await self.get_downloadable(track_id, quality - 1)
                    raise NonStreamableError(f"Failed to get track {track_id}: {resp.status}")
                
                data = await resp.json()
        
        logger.debug(f"Download info: {data}")
        
        # HiFi returns an array: [track_metadata, stream_info, ...]
        # stream_info contains the base64 encoded manifest
        if not isinstance(data, list) or len(data) < 2:
            raise NonStreamableError(f"Invalid response format for track {track_id}")
        
        stream_info = data[1]
        manifest_b64 = stream_info.get("manifest")
        if not manifest_b64:
            raise NonStreamableError(f"No manifest found for track {track_id}")
        
        # Decode the base64 manifest
        try:
            manifest = json.loads(base64.b64decode(manifest_b64).decode("utf-8"))
        except (json.JSONDecodeError, KeyError) as e:
            raise NonStreamableError(f"Failed to decode manifest for track {track_id}: {e}")
        
        logger.debug(f"Manifest: {manifest}")
        
        # Get the stream URL from manifest
        if "urls" not in manifest or len(manifest["urls"]) == 0:
            raise NonStreamableError(f"No stream URL found in manifest for track {track_id}")
        
        stream_url = manifest["urls"][0]
        
        # Determine extension and codec from manifest
        mime_type = manifest.get("mimeType", "")
        if "flac" in mime_type.lower():
            extension = "flac"
        elif "mp4" in mime_type.lower() or "aac" in mime_type.lower():
            extension = "m4a"
        else:
            # Fallback based on quality
            extension = "flac" if quality >= 2 else "m4a"
        
        logger.debug(f"Stream URL: {stream_url}, extension: {extension}")
        
        return BasicDownloadable(
            session=self.session,
            url=stream_url,
            extension=extension,
        )
