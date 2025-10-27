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
        
        # HiFi returns an array: [album_metadata, track_list]
        # track_list has format: {"items": [{"item": track}, ...]}
        if isinstance(data, list) and len(data) >= 2:
            album_data = data[0]
            track_list = data[1]
            
            # Extract tracks from the wrapped format
            if "items" in track_list:
                # Unwrap tracks from {"item": track} format
                tracks = [item["item"] for item in track_list["items"] if "item" in item]
                album_data["tracks"] = tracks
        elif isinstance(data, list) and len(data) > 0:
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
        
        # HiFi returns an array: [artist_metadata, image_data]
        # We only need the artist metadata (first element)
        if isinstance(data, list) and len(data) > 0:
            artist_data = data[0]
        else:
            artist_data = data
        
        # HiFi artist endpoint doesn't include albums list
        # Return empty albums list - streamrip will handle this gracefully
        artist_data["albums"] = []
        
        logger.debug(f"Artist metadata (albums not available via HiFi): {artist_data}")
        logger.info(f"Note: HiFi API doesn't support artist discography. Artist '{artist_data.get('name')}' will have no albums listed.")
        return artist_data

    async def search(self, media_type: str, query: str, limit: int = 100) -> list[dict]:
        """Search for tracks, albums, playlists, or artists.

        Args:
            media_type: One of "track", "album", "playlist", "artist"
            query: Search query string
            limit: Maximum number of results

        Returns:
            List of search results
        """
        assert media_type in ("track", "album", "playlist", "artist"), media_type
        
        url = f"{self.base_url}/search/"
        
        # Use specific search parameters based on media type
        if media_type == "artist":
            params = {"a": query, "li": limit}
        elif media_type == "album":
            params = {"al": query, "li": limit}
        elif media_type == "playlist":
            params = {"p": query, "li": limit}
        else:  # track
            params = {"s": query, "li": limit}
        
        async with self.rate_limiter:
            async with self.session.get(url, params=params) as resp:
                if resp.status != 200:
                    logger.debug(f"Search request failed with status {resp.status}")
                    return []
                data = await resp.json()
        
        # HiFi search returns different formats:
        # - Artist search: returns a list with one dict
        # - Other searches: return a dict directly
        if isinstance(data, list) and len(data) > 0:
            data = data[0]
        elif not isinstance(data, dict):
            return []
        
        media_type_key = f"{media_type}s"
        if media_type_key not in data:
            return []
        
        results_data = data[media_type_key]
        
        # Results are in format: {"items": [...], "limit": x, "offset": y, "totalNumberOfItems": z}
        if isinstance(results_data, dict) and "items" in results_data:
            items = results_data["items"]
            logger.debug(f"Search returned {len(items)} {media_type}s")
            
            if len(items) > 0:
                return [{"items": items}]
        
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
