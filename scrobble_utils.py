"""
Smart scrobbling utilities with improved timestamp distribution and error handling
Based on ytmusic-scrobbler-web worker implementation
"""
import time
import math
from enum import Enum
from typing import Dict, List, Optional
import hashlib
import xml.etree.ElementTree as ET
import lastpy


class FailureType(Enum):
    AUTH = "AUTH"
    NETWORK = "NETWORK"
    TEMPORARY = "TEMPORARY"  # For 503, rate limits, and other temporary issues
    LASTFM = "LASTFM"
    UNKNOWN = "UNKNOWN"


class ScrobbleTimestampCalculator:
    """Smart timestamp calculator with different distribution strategies"""
    
    @staticmethod
    def calculate_scrobble_timestamp(
        songs_scrobbled_so_far: int,
        total_songs_to_scrobble: int,
        is_pro_user: bool = False,
        is_first_time_scrobbling: bool = False
    ) -> str:
        """
        Calculate timestamp for scrobbling with smart distribution
        
        Three-case approach:
        1. First-time scrobbling: logarithmic distribution over 24 hours
        2. Free user (not first time): logarithmic distribution over 1 hour
        3. Pro user (not first time): linear distribution over 5 minutes
        """
        now = int(time.time())
        
        # If only one song, place it 30 seconds ago
        if total_songs_to_scrobble == 1:
            return str(now - 30)
        
        use_linear_distribution = False
        
        # Determine distribution strategy and time window
        if is_first_time_scrobbling:
            # Case 1: First-time scrobbling - use logarithmic with max 1 day (24 hours)
            distribution_seconds = 24 * 60 * 60  # 86400 seconds
        elif not is_pro_user:
            # Case 2: Free user (not first time) - use logarithmic with max 1 hour
            distribution_seconds = 60 * 60  # 3600 seconds
        else:
            # Case 3: Pro user (not first time) - use linear with max 5 minutes
            distribution_seconds = 5 * 60  # 300 seconds
            use_linear_distribution = True
        
        min_offset = 30  # Minimum 30 seconds ago
        
        # Calculate position ratio (0 = most recent, 1 = oldest)
        position_ratio = songs_scrobbled_so_far / (total_songs_to_scrobble - 1)
        
        if use_linear_distribution:
            # Linear distribution for pro users: evenly space songs across the time window
            interval_seconds = distribution_seconds / total_songs_to_scrobble
            offset = min_offset + (interval_seconds * songs_scrobbled_so_far)
        else:
            # Logarithmic distribution for first-time and free users
            # This places more recent songs closer together and spreads older ones further back
            max_offset = distribution_seconds
            
            # Use logarithmic scaling to concentrate recent songs
            # Most recent songs get clustered near min_offset
            # Older songs get distributed across the full time window
            log_scale = math.log(1 + position_ratio * (math.e - 1))
            offset = min_offset + (max_offset - min_offset) * log_scale
        
        return str(int(now - offset))


class ErrorCategorizer:
    """Categorize different types of errors for smart handling"""
    
    @staticmethod
    def categorize_error(error: Exception) -> FailureType:
        """Categorize error type based on error message"""
        error_message = str(error)
        
        # Authentication errors
        if any(keyword in error_message for keyword in [
            "401", "UNAUTHENTICATED", "authentication credential",
            "Headers.append", "invalid header value", "__Secure-3PAPISID"
        ]):
            return FailureType.AUTH
        
        # Temporary service errors (503, 502, 429, rate limits)
        if any(keyword in error_message for keyword in [
            "503", "Service Unavailable", "502", "Bad Gateway",
            "429", "Too Many Requests", "rate limit",
            "temporarily unavailable", "try again later"
        ]):
            return FailureType.TEMPORARY
        
        # Network/YouTube Music errors
        if any(keyword in error_message for keyword in [
            "Failed to fetch", "network", "timeout",
            "ECONNRESET", "ENOTFOUND", "ConnectionError"
        ]):
            return FailureType.NETWORK
        
        # Last.fm specific errors
        if any(keyword in error_message for keyword in [
            "audioscrobbler", "last.fm", "scrobble"
        ]):
            return FailureType.LASTFM
        
        return FailureType.UNKNOWN
    
    @staticmethod
    def should_deactivate_user(failure_type: FailureType, consecutive_failures: int) -> bool:
        """Determine if user should be deactivated based on failure type and count"""
        thresholds = {
            FailureType.AUTH: 3,      # Auth issues are persistent
            FailureType.NETWORK: 8,   # Network issues might be temporary
            FailureType.TEMPORARY: 15, # Temporary issues should rarely deactivate users
            FailureType.LASTFM: 5,    # Last.fm issues might be temporary
            FailureType.UNKNOWN: 7,   # Give more chances for unknown errors
        }
        
        return consecutive_failures >= thresholds.get(failure_type, 7)


class SmartScrobbler:
    """Enhanced scrobbler with smart features"""
    
    def __init__(self, last_fm_api_key: str, last_fm_api_secret: str):
        self.last_fm_api_key = last_fm_api_key
        self.last_fm_api_secret = last_fm_api_secret
        self.timestamp_calculator = ScrobbleTimestampCalculator()
        self.error_categorizer = ErrorCategorizer()
    
    def _sanitize_string(self, s: str) -> str:
        """Sanitize string for Last.fm API"""
        # Decode Unicode escape sequences
        import re
        s = re.sub(r'\\u([0-9A-Fa-f]{4})', lambda m: chr(int(m.group(1), 16)), s)
        
        # Replace specific Unicode characters
        replacements = {
            '\u2026': '...',  # ellipsis
            '\u2013': '-',    # en dash
            '\u2014': '-',    # em dash
            '\u2018': "'",    # left single quotation mark
            '\u2019': "'",    # right single quotation mark
            '\u201C': '"',    # left double quotation mark
            '\u201D': '"',    # right double quotation mark
        }
        
        for old, new in replacements.items():
            s = s.replace(old, new)
        
        # Remove control characters and invalid Unicode
        s = re.sub(r'[\u0000-\u001F\u007F\uFFFE\uFFFF]', '', s)
        
        return s
    
    def _hash_request(self, params: Dict[str, str]) -> str:
        """Create MD5 hash for Last.fm API request"""
        string = ""
        for key in sorted(params.keys()):
            string += key + params[key]
        string += self.last_fm_api_secret
        return hashlib.md5(string.encode('utf-8')).hexdigest()
    
    def scrobble_song(
        self,
        song: Dict[str, str],
        last_fm_session_key: str,
        timestamp: str
    ) -> bool:
        """
        Scrobble a single song to Last.fm
        
        Args:
            song: Dict with title, artist, album keys
            last_fm_session_key: User's Last.fm session key
            timestamp: Unix timestamp as string
            
        Returns:
            True if scrobble was successful, False otherwise
        """
        params = {
            'album': self._sanitize_string(song['album']),
            'api_key': self.last_fm_api_key,
            'method': 'track.scrobble',
            'timestamp': timestamp,
            'track': self._sanitize_string(song['title']),
            'artist': self._sanitize_string(song['artist']),
            'sk': last_fm_session_key,
        }
        
        # Create API signature
        api_sig = self._hash_request(params)
        
        try:
            # Use lastpy for scrobbling (assuming it's available)
            xml_response = lastpy.scrobble(
                params['track'],
                params['artist'],
                params['album'],
                last_fm_session_key,
                timestamp
            )

            # Parse XML response
            root = ET.fromstring(xml_response)
            scrobbles = root.find('scrobbles')

            if scrobbles is not None:
                accepted = scrobbles.get('accepted', '0')
                ignored = scrobbles.get('ignored', '0')

                # Log detailed response for debugging
                print(f"  [Last.fm Response] accepted={accepted}, ignored={ignored}")

                # Parse individual scrobble details
                scrobble_elements = scrobbles.findall('scrobble')
                for scrobble in scrobble_elements:
                    track_elem = scrobble.find('track')
                    artist_elem = scrobble.find('artist')
                    timestamp_elem = scrobble.find('timestamp')
                    ignored_message = scrobble.find('ignoredMessage')

                    track_corrected = track_elem.get('corrected', '0') if track_elem is not None else '0'
                    artist_corrected = artist_elem.get('corrected', '0') if artist_elem is not None else '0'

                    print(f"  [Scrobble Details]")
                    print(f"    Track: {track_elem.text if track_elem is not None else 'N/A'} (corrected: {track_corrected})")
                    print(f"    Artist: {artist_elem.text if artist_elem is not None else 'N/A'} (corrected: {artist_corrected})")
                    print(f"    Timestamp: {timestamp_elem.text if timestamp_elem is not None else 'N/A'}")

                    if ignored_message is not None and ignored_message.text:
                        print(f"    ⚠️  Ignored: {ignored_message.text}")
                        code = ignored_message.get('code', 'unknown')
                        print(f"    Ignore code: {code}")

                # Return True if at least one scrobble was accepted (keeping original logic)
                return accepted != '0' or ignored == '0'

            print(f"  [Last.fm Response] No scrobbles element found in XML response")
            print(f"  [Raw XML] {xml_response}")
            return False

        except Exception as e:
            # Log the error but don't raise it - let caller handle it
            print(f"Scrobble error for '{song['title']}' by {song['artist']}: {str(e)}")
            raise e
    
    def calculate_timestamp(
        self,
        position: int,
        total: int,
        is_pro_user: bool = False,
        is_first_time: bool = False
    ) -> str:
        """Calculate timestamp for scrobbling at given position"""
        return self.timestamp_calculator.calculate_scrobble_timestamp(
            position, total, is_pro_user, is_first_time
        )
    
    def categorize_error(self, error: Exception) -> FailureType:
        """Categorize an error for smart handling"""
        return self.error_categorizer.categorize_error(error)
    
    def should_deactivate_user(self, failure_type: FailureType, consecutive_failures: int) -> bool:
        """Check if user should be deactivated"""
        return self.error_categorizer.should_deactivate_user(failure_type, consecutive_failures)


class PositionTracker:
    """Track song positions for detecting re-reproductions"""
    
    def __init__(self):
        pass
    
    @staticmethod
    def detect_songs_to_scrobble(
        today_songs: List[Dict[str, str]],
        database_songs: List[Dict],
        is_first_time: bool = False,
        max_first_time_songs: int = 10
    ) -> List[Dict]:
        """
        Determine which songs should be scrobbled based on position tracking
        
        Args:
            today_songs: Songs from today's history (with position index)
            database_songs: Songs already in database with max_array_position
            is_first_time: Whether this is first time scrobbling for user
            max_first_time_songs: Maximum songs to scrobble for first-time users
            
        Returns:
            List of songs that should be scrobbled with their info
        """
        songs_to_scrobble = []
        
        if is_first_time:
            # First time: scrobble recent songs up to the limit
            for i, song in enumerate(today_songs[:max_first_time_songs]):
                songs_to_scrobble.append({
                    'song': song,
                    'position': i + 1,
                    'reason': 'first_time',
                    'should_scrobble': True
                })
            
            # Add remaining songs to database without scrobbling
            for i, song in enumerate(today_songs[max_first_time_songs:], max_first_time_songs):
                songs_to_scrobble.append({
                    'song': song,
                    'position': i + 1,
                    'reason': 'first_time_no_scrobble',
                    'should_scrobble': False
                })
        else:
            # Regular processing: check for new songs and re-reproductions
            for i, song in enumerate(today_songs):
                current_position = i + 1
                
                # Find matching song in database
                saved_song = None
                for db_song in database_songs:
                    if (db_song['title'] == song['title'] and 
                        db_song['artist'] == song['artist'] and 
                        db_song['album'] == song['album']):
                        saved_song = db_song
                        break
                
                if not saved_song:
                    # New song - scrobble it
                    songs_to_scrobble.append({
                        'song': song,
                        'position': current_position,
                        'reason': 'new_song',
                        'should_scrobble': True
                    })
                elif current_position < saved_song.get('array_position', float('inf')):
                    # Re-reproduction - song moved up in the list (better position than previous session)
                    songs_to_scrobble.append({
                        'song': song,
                        'position': current_position,
                        'reason': 'reproduction',
                        'should_scrobble': True,
                        'previous_position': saved_song.get('array_position')
                    })
                else:
                    # Song exists and hasn't moved up - just update position
                    songs_to_scrobble.append({
                        'song': song,
                        'position': current_position,
                        'reason': 'position_update',
                        'should_scrobble': False
                    })
        
        return songs_to_scrobble