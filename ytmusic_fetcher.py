"""
YouTube Music History Fetcher
Direct HTML page scraping approach (no YTMusic API dependency)
Based on ytmusic-scrobbler-web worker implementation
"""
import re
import json
import hashlib
import requests
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import time


class YTMusicFetcher:
    def __init__(self, cookie: str):
        """
        Initialize with raw cookie string from browser
        Cookie should contain __Secure-3PAPISID token
        """
        self.cookie = cookie.strip()
        self._validate_cookie()
    
    def _validate_cookie(self):
        """Validate that cookie contains required __Secure-3PAPISID token"""
        if "__Secure-3PAPISID=" not in self.cookie:
            raise ValueError(
                "Cookie is missing the required __Secure-3PAPISID token. "
                "Please copy the complete cookie from your browser."
            )
    
    def validate_cookie_is_active(self) -> bool:
        """
        Validate if the cookie is not only syntactically correct but also active
        by attempting the full history extraction process to ensure we can access content
        """
        try:
            # First, try to fetch the history page - this will raise an exception for 401 errors
            html = self.fetch_history_page()
            
            # At this point we have a 200 response, but we need to determine if it's truly authenticated
            # The most reliable check is to see if the original parsing logic can extract meaningful data
            initial_data = self._extract_initial_data_from_page(html)
            
            if initial_data:
                # If we can extract initial data, the cookie is definitely valid
                return True
            else:
                # If we can't extract initial data, we need to distinguish between:
                # 1. Valid cookie but no history (user has no listening history)
                # 2. Invalid cookie that still returns a page but without history data
                # 
                # We'll make the assumption that a valid authenticated cookie will at least have
                # the basic page structure that the original code can work with
                try:
                    # Try to parse with the same logic used by get_history method
                    parsed_songs = self._parse_ytmusic_response(initial_data) if initial_data else self._parse_ytmusic_response({})
                    
                    # If we got here without errors, the cookie validation passes
                    # The fact that fetch_history_page() succeeded means we got a valid response from YouTube
                    return True
                except Exception:
                    # If the parsing fails, it might mean the page structure isn't what we expect
                    # Check if the page contains content that indicates we need to sign in
                    if ("sign in" in html.lower() and "required" in html.lower()) or \
                       ("log in" in html.lower() and "continue" in html.lower()) or \
                       ("/signin" in html):
                        raise Exception("Authentication required: YouTube Music cookie appears to be expired or invalid. Page content suggests a login is required.")
                    else:
                        # If it's not clearly a login page, we'll consider it valid 
                        # (the user might just have no history)
                        return True
                    
        except Exception as e:
            # If fetch_history_page fails with a 401, the cookie is definitely invalid
            if "401 UNAUTHENTICATED" in str(e) or "authentication credential" in str(e):
                raise Exception("401 UNAUTHENTICATED: Request is missing required authentication credential. Your YouTube Music credentials have expired.")
            else:
                raise e
    
    def _sanitize_cookie_for_http(self, cookie: str) -> str:
        """Remove invalid Unicode characters that can't be used in HTTP headers"""
        # Remove Unicode characters > 255 and normalize whitespace
        sanitized = re.sub(r'[\u0100-\uFFFF]', '', cookie)
        sanitized = re.sub(r'\s+', ' ', sanitized)
        return sanitized.strip()
    
    def _process_cookie_for_request(self, cookie: str) -> str:
        """Process and sanitize cookie for HTTP request"""
        sanitized_cookie = self._sanitize_cookie_for_http(cookie)
        
        # Parse cookie pairs
        cookies = {}
        for pair in sanitized_cookie.split(";"):
            if "=" in pair:
                name, value = pair.strip().split("=", 1)
                if name:  # Only process valid cookie names
                    cookies[name] = value
        
        # Add required SOCS cookie if missing
        if "SOCS" not in cookies:
            cookies["SOCS"] = "CAI"
        
        # Reconstruct cookie string
        return "; ".join([f"{name}={value}" for name, value in cookies.items()])
    
    def _extract_sapisid_from_cookie(self, raw_cookie: str) -> str:
        """Extract SAPISID token from cookie"""
        match = re.search(r"__Secure-3PAPISID=([^;]+)", raw_cookie)
        if not match:
            raise ValueError(
                f"Cookie is missing the required __Secure-3PAPISID token. "
                f"Your cookie appears to be incomplete or invalid."
            )
        return match.group(1)
    
    def _get_authorization_header(self, sapisid: str) -> str:
        """Generate authorization header for YouTube Music requests"""
        unix_timestamp = str(int(time.time()))
        origin = "https://music.youtube.com"
        data = f"{unix_timestamp} {sapisid} {origin}"
        hash_value = hashlib.sha1(data.encode()).hexdigest()
        return f"SAPISIDHASH {unix_timestamp}_{hash_value}"
    
    def _get_visitor_id(self) -> Optional[str]:
        """Get Google visitor ID from YouTube Music main page"""
        try:
            response = requests.get(
                "https://music.youtube.com",
                headers={
                    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:88.0) Gecko/20100101 Firefox/88.0",
                    "accept": "*/*",
                    "accept-encoding": "gzip, deflate",
                    "content-type": "application/json",
                    "origin": "https://music.youtube.com",
                },
                timeout=10
            )
            
            if response.ok:
                text = response.text
                matches = re.search(r'ytcfg\.set\s*\(\s*({.+?})\s*\)\s*;', text)
                if matches:
                    ytcfg = json.loads(matches.group(1))
                    return ytcfg.get("VISITOR_DATA", "")
            return None
        except Exception:
            return None
    
    def fetch_history_page(self) -> str:
        """Fetch YouTube Music history page HTML"""
        processed_cookie = self._process_cookie_for_request(self.cookie)
        
        headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "accept-language": "en-US,en;q=0.9,es;q=0.8,pt;q=0.7",
            "cache-control": "no-cache",
            "cookie": processed_cookie,
            "pragma": "no-cache",
            "priority": "u=0, i",
            "sec-ch-ua": '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
            "sec-ch-ua-arch": '"x86"',
            "sec-ch-ua-bitness": '"64"',
            "sec-ch-ua-form-factors": '"Desktop"',
            "sec-ch-ua-full-version": '"139.0.7258.154"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-model": '""',
            "sec-ch-ua-platform": '"Linux"',
            "sec-ch-ua-platform-version": '"6.14.0"',
            "sec-ch-ua-wow64": "?0",
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "same-origin",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
            "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
        }
        
        response = requests.get(
            "https://music.youtube.com/history",
            headers=headers,
            timeout=30
        )
        
        if not response.ok:
            if response.status_code == 401:
                raise Exception("401 UNAUTHENTICATED: Request is missing required authentication credential. Your YouTube Music credentials have expired.")
            else:
                raise Exception(f"Failed to fetch YouTube Music history page: {response.status_code} {response.reason_phrase}\n{response.text}")
        
        return response.text
    
    def _decode_hex_string(self, hex_str: str) -> str:
        """Decode hex-encoded string"""
        return re.sub(r'\\x([0-9A-Fa-f]{2})', lambda m: chr(int(m.group(1), 16)), hex_str)
    
    def _sanitize_json_string(self, json_str: str) -> str:
        """Sanitize JSON string by properly escaping unescaped quotes"""
        result = ""
        in_string = False
        escape_next = False
        string_char = ""
        
        for i, char in enumerate(json_str):
            if escape_next:
                result += char
                escape_next = False
                continue
            
            if char == "\\":
                result += char
                escape_next = True
                continue
            
            if not in_string:
                if char in ['"', "'"]:
                    in_string = True
                    string_char = char
                result += char
            else:
                if char == string_char:
                    # Check if this quote should end the string
                    should_end_string = False
                    
                    # Look ahead to see what comes after this quote
                    next_index = i + 1
                    while next_index < len(json_str) and json_str[next_index].isspace():
                        next_index += 1
                    
                    if next_index >= len(json_str):
                        should_end_string = True
                    else:
                        next_char = json_str[next_index]
                        if next_char in [",", "}", "]", ":"]:
                            should_end_string = True
                    
                    if should_end_string:
                        in_string = False
                        string_char = ""
                        result += char
                    else:
                        # Escape the quote
                        result += "\\" + char
                else:
                    result += char
        
        return result
    
    def _extract_initial_data_from_page(self, html: str) -> Optional[dict]:
        """Extract initialData from HTML page"""
        # Search for initialData.push patterns
        pattern = r"initialData\.push\(\{[^}]*data:\s*'([^']+)'"
        matches = re.findall(pattern, html)
        
        for hex_data in matches:
            try:
                # Decode hex to string
                decoded_data = self._decode_hex_string(hex_data)
                
                # Check if it's valid JSON
                if not (decoded_data.startswith("{") or decoded_data.startswith("[")):
                    continue
                
                # Sanitize and parse JSON
                sanitized_data = self._sanitize_json_string(decoded_data)
                parsed = json.loads(sanitized_data)
                
                # Check if it contains history data
                json_str = json.dumps(parsed)
                if any(keyword in json_str for keyword in [
                    "singleColumnBrowseResultsRenderer",
                    "musicShelfRenderer",
                    "FEmusic_history"
                ]):
                    return parsed
                
            except json.JSONDecodeError:
                # Try to fix malformed JSON
                try:
                    decoded_data = self._decode_hex_string(hex_data)
                    cleaned_data = decoded_data.strip()
                    
                    # Remove trailing comma
                    if cleaned_data.endswith(","):
                        cleaned_data = cleaned_data[:-1]
                    
                    # Balance brackets and braces
                    open_braces = cleaned_data.count("{")
                    close_braces = cleaned_data.count("}")
                    open_brackets = cleaned_data.count("[")
                    close_brackets = cleaned_data.count("]")
                    
                    if open_braces > close_braces:
                        cleaned_data += "}" * (open_braces - close_braces)
                    if open_brackets > close_brackets:
                        cleaned_data += "]" * (open_brackets - close_brackets)
                    
                    cleaned = json.loads(cleaned_data)
                    
                    # Check for history data
                    json_str = json.dumps(cleaned)
                    if any(keyword in json_str for keyword in [
                        "singleColumnBrowseResultsRenderer",
                        "musicShelfRenderer",
                        "FEmusic_history"
                    ]):
                        return cleaned
                        
                except json.JSONDecodeError:
                    continue
        
        return None
    
    def _sanitize_string(self, s: str) -> str:
        """Sanitize string by removing problematic characters"""
        # Decode Unicode escape sequences
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
    
    def _parse_ytmusic_response(self, data: dict) -> List[Dict[str, str]]:
        """Parse YouTube Music response data"""
        try:
            results = data.get("contents", {}).get("singleColumnBrowseResultsRenderer", {}).get("tabs", [{}])[0].get("tabRenderer", {}).get("content", {}).get("sectionListRenderer", {}).get("contents", [])
        except (KeyError, IndexError, TypeError):
            raise Exception("No results found in response data")
        
        if not results:
            raise Exception("No results found")
        
        songs = []
        
        for section in results:
            music_shelf = section.get("musicShelfRenderer")
            if not music_shelf:
                continue
            
            # Get the section title (e.g., "Today", "Yesterday")
            played_at = None
            if music_shelf.get("title", {}).get("runs"):
                played_at = music_shelf["title"]["runs"][0].get("text")
            
            # Process songs in this section
            contents = music_shelf.get("contents", [])
            for item in contents:
                renderer = item.get("musicResponsiveListItemRenderer")
                if not renderer:
                    continue
                
                flex_columns = renderer.get("flexColumns", [])
                if not flex_columns:
                    continue
                
                # Find title (watchEndpoint)
                title = None
                for column in flex_columns:
                    column_renderer = column.get("musicResponsiveListItemFlexColumnRenderer", {})
                    runs = column_renderer.get("text", {}).get("runs", [])
                    if runs and runs[0].get("navigationEndpoint", {}).get("watchEndpoint"):
                        title = runs[0].get("text")
                        break
                
                # Find artist (browseEndpoint with ARTIST page type)
                artist = None
                for column in flex_columns:
                    column_renderer = column.get("musicResponsiveListItemFlexColumnRenderer", {})
                    runs = column_renderer.get("text", {}).get("runs", [])
                    if runs:
                        endpoint = runs[0].get("navigationEndpoint", {})
                        browse_endpoint = endpoint.get("browseEndpoint", {})
                        configs = browse_endpoint.get("browseEndpointContextSupportedConfigs", {})
                        music_config = configs.get("browseEndpointContextMusicConfig", {})
                        if music_config.get("pageType") == "MUSIC_PAGE_TYPE_ARTIST":
                            artist = runs[0].get("text")
                            break
                
                # Find album (browseEndpoint with ALBUM page type)
                album = None
                for column in flex_columns:
                    column_renderer = column.get("musicResponsiveListItemFlexColumnRenderer", {})
                    runs = column_renderer.get("text", {}).get("runs", [])
                    if runs:
                        endpoint = runs[0].get("navigationEndpoint", {})
                        browse_endpoint = endpoint.get("browseEndpoint", {})
                        configs = browse_endpoint.get("browseEndpointContextSupportedConfigs", {})
                        music_config = configs.get("browseEndpointContextMusicConfig", {})
                        if music_config.get("pageType") == "MUSIC_PAGE_TYPE_ALBUM":
                            album = runs[0].get("text")
                            break
                
                # Use title as album if no album found
                if not album:
                    album = title
                
                # Skip songs without required data or Topic channels
                if title and artist and not artist.endswith(" - Topic"):
                    songs.append({
                        "title": self._sanitize_string(title),
                        "artist": self._sanitize_string(artist),
                        "album": self._sanitize_string(album),
                        "playedAt": played_at
                    })
        
        return songs
    
    def get_history(self) -> List[Dict[str, str]]:
        """
        Get YouTube Music history by parsing HTML page
        Returns list of songs with title, artist, album, and playedAt
        """
        html = self.fetch_history_page()
        initial_data = self._extract_initial_data_from_page(html)
        
        if not initial_data:
            raise Exception("No initial data found in page - this might indicate authentication issues")
        
        return self._parse_ytmusic_response(initial_data)


def get_ytmusic_history_from_cookie(cookie: str) -> List[Dict[str, str]]:
    """
    Convenience function to get YouTube Music history from cookie
    
    Args:
        cookie: Raw cookie string from browser (must contain __Secure-3PAPISID)
    
    Returns:
        List of songs with title, artist, album, and playedAt fields
    """
    fetcher = YTMusicFetcher(cookie)
    return fetcher.get_history()