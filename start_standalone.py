#!/usr/bin/env python3
"""
Standalone YouTube Music Last.fm Scrobbler
- No external API dependencies (direct HTML page scraping)
- Multilingual date detection (50+ languages)  
- Smart timestamp distribution (logarithmic/linear)
- Better position tracking and re-reproduction detection
- Robust error handling and categorization
"""
import os
import time
import lastpy
import sqlite3
import webbrowser
import threading
import http.server
import socketserver
import xml.etree.ElementTree as ET
from dotenv import load_dotenv, set_key
from datetime import datetime
from typing import List, Dict, Optional

# Import our new modules
from ytmusic_fetcher import get_ytmusic_history_from_cookie, YTMusicFetcher
from date_detection import is_today_song, get_unknown_date_values, get_detected_languages
from scrobble_utils import SmartScrobbler, PositionTracker, FailureType

load_dotenv()


class TokenHandler(http.server.SimpleHTTPRequestHandler):
    def do_get_token(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b'<html><head><title>Token Received</title></head>')
        self.wfile.write(
            b'<body><p>Authentication successful! You can now close this window.</p></body></html>')
        self.server.token = self.path.split('?token=')[1]

    def do_GET(self):
        if self.path.startswith('/?token='):
            self.do_get_token()
        else:
            http.server.SimpleHTTPRequestHandler.do_GET(self)


class TokenServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    token = None


class ImprovedProcess:
    def __init__(self):
        self.api_key = os.environ.get('LAST_FM_API')
        self.api_secret = os.environ.get('LAST_FM_API_SECRET')
        if not self.api_key or not self.api_secret:
            raise ValueError("Missing LAST_FM_API or LAST_FM_API_SECRET environment variables")
        
        try:
            self.session = os.environ['LASTFM_SESSION']
        except KeyError:
            self.session = None

        # Initialize smart scrobbler
        self.scrobbler = SmartScrobbler(self.api_key, self.api_secret)
        self.position_tracker = PositionTracker()
        
        # Database connection with improved schema
        self.conn = sqlite3.connect('./data.db')
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scrobbles (
                id INTEGER PRIMARY KEY,
                track_name TEXT,
                artist_name TEXT,
                album_name TEXT,
                scrobbled_at TEXT DEFAULT CURRENT_TIMESTAMP,
                array_position INTEGER,
                max_array_position INTEGER,
                is_first_time_scrobble BOOLEAN DEFAULT FALSE
            )
        ''')
        
        # Add new columns if they don't exist (for backward compatibility)
        try:
            cursor.execute('ALTER TABLE scrobbles ADD COLUMN max_array_position INTEGER')
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        try:
            cursor.execute('ALTER TABLE scrobbles ADD COLUMN is_first_time_scrobble BOOLEAN DEFAULT FALSE')
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        self.conn.commit()
        cursor.close()

    def get_token(self):
        print("Waiting for Last.fm authentication...")
        auth_url = f"https://www.last.fm/api/auth/?api_key={self.api_key}&cb=http://localhost:5588"
        
        with TokenServer(('localhost', 5588), TokenHandler) as httpd:
            webbrowser.open(auth_url)
            thread = threading.Thread(target=httpd.serve_forever)
            thread.start()
            while True:
                if httpd.token:
                    token = httpd.token
                    httpd.shutdown()
                    break
                time.sleep(0.1)
        return token

    def get_session(self, token):
        print("Getting Last.fm session...")
        xml_response = lastpy.authorize(token)
        try:
            root = ET.fromstring(xml_response)
            session_key = root.find('session/key').text
            set_key('.env', 'LASTFM_SESSION', session_key)
            return session_key
        except Exception as e:
            print(f"Error getting session: {xml_response}")
            raise Exception(e)

    def get_cookie_from_env_or_input(self) -> str:
        """Get YouTube Music cookie from environment or user input"""
        cookie = os.environ.get('YTMUSIC_COOKIE')
        
        if not cookie:
            print("\\n" + "="*80)
            print("YouTube Music Cookie Required")
            print("="*80)
            print("Please copy your YouTube Music cookie from your browser.")
            print("\\nTo get your cookie:")
            print("1. Go to https://music.youtube.com in your browser")
            print("2. Open Developer Tools (F12)")
            print("3. Go to Network tab")
            print("4. Refresh the page")
            print("5. Find any request to music.youtube.com")
            print("6. Copy the entire 'Cookie' header value")
            print("\\nThe cookie should contain '__Secure-3PAPISID=' among other values.")
            print("-"*80)
            
            cookie = input("Paste your YouTube Music cookie here: ").strip()
            
            if cookie:
                # Optionally save it to .env for future use
                save_cookie = input("Save cookie to .env file for future use? (y/n): ").lower().startswith('y')
                if save_cookie:
                    set_key('.env', 'YTMUSIC_COOKIE', cookie)
                    print("Cookie saved to .env file")
        
        if not cookie:
            raise ValueError("YouTube Music cookie is required")
        
        return cookie

    def handle_authentication_error(self, error: Exception) -> bool:
        """Handle authentication errors and provide user guidance"""
        print(f"\\n❌ Authentication Error: {str(error)}")
        print("\\n" + "="*80)
        print("YouTube Music Authentication Failed")
        print("="*80)
        print("Your YouTube Music cookie appears to be expired or invalid.")
        print("\\nPlease update your cookie:")
        print("1. Go to https://music.youtube.com and sign in")
        print("2. Copy the new cookie from Developer Tools")
        print("3. Run this script again")
        print("\\nNote: Cookies typically expire after a few hours or days.")
        return False

    def execute(self):
        """Main execution logic with improved error handling and features"""
        # Get YouTube Music cookie
        try:
            cookie = self.get_cookie_from_env_or_input()
        except ValueError as e:
            print(f"Error: {e}")
            return False

        # Get Last.fm session if not available
        if not self.session:
            try:
                token = self.get_token()
                self.session = self.get_session(token)
            except Exception as e:
                print(f"Failed to authenticate with Last.fm: {e}")
                return False

        # Validate the YouTube Music cookie is still valid before proceeding
        print("🔍 Validating YouTube Music cookie...")
        try:
            fetcher = YTMusicFetcher(cookie)
            is_valid = fetcher.validate_cookie_is_active()
            if not is_valid:
                raise Exception("YouTube Music cookie validation failed - cookie appears to be invalid")
            print("✅ Cookie validation: PASSED")
        except Exception as error:
            return self._handle_auth_error(error, "validating cookie")

        print("🎵 Fetching YouTube Music history...")
        try:
            # Use our new HTML-based history fetcher (no YTMusic API dependency)
            history = get_ytmusic_history_from_cookie(cookie)
            print(f"📋 Retrieved: {len(history)} total songs from history")
        except Exception as error:
            return self._handle_auth_error(error, "fetching history")

        # Filter songs played today using multilingual detection
        print("📅 Filtering songs played today...")
        today_songs = [song for song in history if is_today_song(song.get('playedAt'))]
        
        # Log unknown date values for future expansion
        unknown_values = get_unknown_date_values(history)
        
        # Log detected languages
        detected_languages = get_detected_languages(history)
        if detected_languages:
            print(f"🌐 Languages detected: {', '.join(detected_languages)}")

        print(f"🎯 Found: {len(today_songs)} songs played today")

        if len(today_songs) == 0:
            print("😴 No songs played today. Nothing to scrobble.")
            return True

        # Get existing songs from database
        cursor = self.conn.cursor()
        db_songs = cursor.execute('''
            SELECT track_name, artist_name, album_name, array_position,
                   max_array_position, is_first_time_scrobble
            FROM scrobbles
        ''').fetchall()
        
        # Determine if this is first time scrobbling
        database_songs = []
        for row in db_songs:
            database_songs.append({
                'title': row[0],
                'artist': row[1],
                'album': row[2],
                'array_position': row[3],
                'max_array_position': row[4] or row[3],  # Use array_position if max is NULL
                'is_first_time': bool(row[5])
            })

        # Determine if this is first time scrobbling
        is_first_time = len(database_songs) == 0
        
        # Clean up database: remove songs not in today's history
        if database_songs:
            songs_to_delete = []
            for db_song in database_songs:
                found = False
                for today_song in today_songs:
                    if (today_song['title'] == db_song['title'] and 
                        today_song['artist'] == db_song['artist'] and 
                        today_song['album'] == db_song['album']):
                        found = True
                        break
                
                if not found:
                    songs_to_delete.append(db_song)
            
            if songs_to_delete:
                print(f"🧹 Removed {len(songs_to_delete)} outdated songs from database")
                for song in songs_to_delete:
                    cursor.execute('''
                        DELETE FROM scrobbles 
                        WHERE track_name = ? AND artist_name = ? AND album_name = ?
                    ''', (song['title'], song['artist'], song['album']))
                self.conn.commit()

        # Determine which songs to scrobble using smart position tracking
        max_first_time_songs = 10  # Can be made configurable
        songs_to_process = self.position_tracker.detect_songs_to_scrobble(
            today_songs, database_songs, is_first_time, max_first_time_songs
        )

        # Count how many will actually be scrobbled
        songs_to_scrobble = [s for s in songs_to_process if s['should_scrobble']]
        total_to_scrobble = len(songs_to_scrobble)

        # Prepare summary data
        scrobble_stats = {
            'new_songs': sum(1 for s in songs_to_process if s['reason'] == 'new_song'),
            'reproductions': sum(1 for s in songs_to_process if s['reason'] == 'reproduction'),
            'position_updates': sum(1 for s in songs_to_process if s['reason'] == 'position_update'),
            'first_time_no_scrobble': sum(1 for s in songs_to_process if s['reason'] == 'first_time_no_scrobble')
        }
        
        print(f"\n📋 PROCESSING PLAN:")
        print(f"   Songs in today's history: {len(today_songs):>3}")
        print(f"   Total to process: {len(songs_to_process):>11}")
        print(f"   └─ Songs to scrobble: {total_to_scrobble:>8}")
        print(f"   └─ DB updates only: {len(songs_to_process) - total_to_scrobble:>10}")
        print(f"\n📊 BREAKDOWN:")
        print(f"   New songs: {scrobble_stats['new_songs']:>16}")
        print(f"   Re-productions: {scrobble_stats['reproductions']:>11}")
        print(f"   Position updates: {scrobble_stats['position_updates']:>9}")
        
        # Process songs with tracking for reporting
        songs_scrobbled = 0
        scrobble_position = 0
        failed_songs = []
        scrobbled_tracks = []
        db_only_tracks = []

        for item in songs_to_process:
            song = item['song']
            position = item['position']
            should_scrobble = item['should_scrobble']
            reason = item['reason']
            
            try:
                if should_scrobble:
                    # Calculate smart timestamp
                    timestamp = self.scrobbler.calculate_timestamp(
                        scrobble_position,
                        total_to_scrobble,
                        is_pro_user=False,  # Can be made configurable
                        is_first_time=is_first_time
                    )
                    
                    # Scrobble the song
                    success = self.scrobbler.scrobble_song(song, self.session, timestamp)
                    
                    if success:
                        songs_scrobbled += 1
                        scrobble_position += 1
                        scrobbled_tracks.append(f"{song['title']} by {song['artist']}")
                    else:
                        failed_songs.append(f"{song['title']} by {song['artist']}")
                
                # Update/insert in database
                existing_song = cursor.execute('''
                    SELECT id, max_array_position FROM scrobbles 
                    WHERE track_name = ? AND artist_name = ? AND album_name = ?
                ''', (song['title'], song['artist'], song['album'])).fetchone()
                
                if existing_song:
                    # Update existing song
                    song_id, current_max = existing_song
                    new_max = max(current_max or position, position)
                    
                    cursor.execute('''
                        UPDATE scrobbles 
                        SET array_position = ?, max_array_position = ?, scrobbled_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (position, new_max, song_id))
                else:
                    # Insert new song
                    cursor.execute('''
                        INSERT INTO scrobbles 
                        (track_name, artist_name, album_name, array_position, max_array_position, is_first_time_scrobble)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (song['title'], song['artist'], song['album'], position, position, is_first_time))
                
                if not should_scrobble:
                    db_only_tracks.append(f"{song['title']} by {song['artist']} ({reason})")
                
                self.conn.commit()
                
            except Exception as error:
                # Use the helper method to handle auth errors consistently
                should_continue = self._handle_processing_auth_error(error)
                if not should_continue:
                    failed_songs.append(f"{song['title']} by {song['artist']}")
                    failure_type = self.scrobbler.categorize_error(error)
                    if failure_type == FailureType.AUTH:
                        print("🔒 Authentication error detected. Stopping execution.")
                        break

        # Check for potential duplicates in the database
        cursor.execute('''
            SELECT track_name, artist_name, COUNT(*) as count
            FROM scrobbles
            WHERE scrobbled_at >= datetime('now', '-1 hour')
            GROUP BY track_name, artist_name
            HAVING count > 1
        ''')
        
        duplicates = cursor.fetchall()
        cursor.close()
        
        # Final summary
        # Final summary with better structure
        print(f"\n{'='*60}")
        print(f"🎵 SCROBBLING COMPLETED!")
        print(f"{'='*60}")
        
        # Log unknown date values for future expansion (now in final summary)
        unknown_values = get_unknown_date_values(history)
        
        print(f"📊 FINAL SUMMARY:")
        print(f"   Total songs processed: {len(songs_to_process):>4}")
        print(f"   Successfully scrobbled: {songs_scrobbled:>3}")
        print(f"   Failed scrobbles: {len(failed_songs):>9}")
        if failed_songs:
            print(f"   Failed tracks: {', '.join(failed_songs[:3])}" + ("..." if len(failed_songs) > 3 else ""))
        print(f"   Duplicate checks: {'✅ No duplicates' if not duplicates else f'⚠️ Found {len(duplicates)} duplicates'}")
        
        print(f"\n📈 PROCESS BREAKDOWN:")
        print(f"   New songs: {scrobble_stats['new_songs']:>16}")
        print(f"   Re-productions: {scrobble_stats['reproductions']:>11}")
        print(f"   Position updates: {scrobble_stats['position_updates']:>9}")
        
        # Include the specific tracks information
        if scrobbled_tracks:
            print(f"\n✅ SCROBBLED TRACKS ({len(scrobbled_tracks)}):")
            for i, track in enumerate(scrobbled_tracks, 1):  # Show ALL scrobbled tracks
                print(f"   {i}. {track}")
        
        if db_only_tracks:
            print(f"\n💾 DATABASE ONLY ({len(db_only_tracks)}):")
            for i, track in enumerate(db_only_tracks[:5], 1):  # Show first 5
                print(f"   {i}. {track}")
            if len(db_only_tracks) > 5:
                print(f"   ... and {len(db_only_tracks) - 5} more")
        
        if failed_songs:
            print(f"\n❌ FAILED TRACKS ({len(failed_songs)}):")
            for i, track in enumerate(failed_songs[:5], 1):  # Show first 5
                print(f"   {i}. {track}")
            if len(failed_songs) > 5:
                print(f"   ... and {len(failed_songs) - 5} more")
        
        # Include unknown date formats in the summary
        if unknown_values:
            print(f"\n🔍 DATE SUPPORT INFO:")
            print(f"   Unrecognized date formats: {', '.join(unknown_values)}")
            print(f"   (These will be added to support more languages)")
        
        print(f"\n{'='*60}")
        if songs_scrobbled > 0:
            print(f"✅ SUCCESS: {songs_scrobbled} songs sent to Last.fm")
        elif len(failed_songs) > 0:
            print(f"⚠️  PARTIAL: {len(failed_songs)} songs failed to scrobble")
        else:
            print(f"✅ COMPLETED: All songs processed (no new scrobbles needed)")
        print(f"{'='*60}")
        
        return True

        # Filter songs played today using multilingual detection
        print("Filtering songs played today...")
        today_songs = [song for song in history if is_today_song(song.get('playedAt'))]
        
        # Log unknown date values for future expansion
        unknown_values = get_unknown_date_values(history)
        if unknown_values:
            print(f"Unknown date formats detected: {', '.join(unknown_values)}")
            print("Please report these to the developer for future support")
        
        # Log detected languages
        detected_languages = get_detected_languages(history)
        if detected_languages:
            print(f"Detected languages in today's songs: {', '.join(detected_languages)}")

        print(f"Found {len(today_songs)} songs played today")

        if len(today_songs) == 0:
            print("No songs played today. Nothing to scrobble.")
            return True

        # Get existing songs from database
        cursor = self.conn.cursor()
        db_songs = cursor.execute('''
            SELECT track_name, artist_name, album_name, array_position,
                   max_array_position, is_first_time_scrobble
            FROM scrobbles
        ''').fetchall()
        
        print(f"📊 Database Analysis:")
        print(f"  - Total existing songs in database: {len(db_songs)}")
        
        # Convert to dict format for easier processing
        database_songs = []
        for row in db_songs:
            database_songs.append({
                'title': row[0],
                'artist': row[1],
                'album': row[2],
                'array_position': row[3],
                'max_array_position': row[4] or row[3],  # Use array_position if max is NULL
                'is_first_time': bool(row[5])
            })
        
        # Show recent database entries for debugging
        if database_songs:
            print(f"  - Recent database entries:")
            for song in database_songs[:5]:
                print(f"    - {song['title']} by {song['artist']} (pos: {song.get('array_position', 'N/A')}, max: {song.get('max_array_position', 'N/A')})")

        # Determine if this is first time scrobbling
        is_first_time = len(database_songs) == 0
        
        # Clean up database: remove songs not in today's history
        if database_songs:
            songs_to_delete = []
            for db_song in database_songs:
                found = False
                for today_song in today_songs:
                    if (today_song['title'] == db_song['title'] and 
                        today_song['artist'] == db_song['artist'] and 
                        today_song['album'] == db_song['album']):
                        found = True
                        break
                
                if not found:
                    songs_to_delete.append(db_song)
            
            if songs_to_delete:
                print(f"Removing {len(songs_to_delete)} songs no longer in today's history")
                for song in songs_to_delete:
                    cursor.execute('''
                        DELETE FROM scrobbles 
                        WHERE track_name = ? AND artist_name = ? AND album_name = ?
                    ''', (song['title'], song['artist'], song['album']))
                self.conn.commit()

        # Determine which songs to scrobble using smart position tracking
        max_first_time_songs = 10  # Can be made configurable
        songs_to_process = self.position_tracker.detect_songs_to_scrobble(
            today_songs, database_songs, is_first_time, max_first_time_songs
        )

        # Count how many will actually be scrobbled
        songs_to_scrobble = [s for s in songs_to_process if s['should_scrobble']]
        total_to_scrobble = len(songs_to_scrobble)

        print(f"🎵 Processing Analysis:")
        print(f"  - Total songs to process: {len(songs_to_process)}")
        print(f"  - Songs to scrobble: {total_to_scrobble}")
        print(f"  - Songs for database only: {len(songs_to_process) - total_to_scrobble}")
        
        # Log processing decisions for debugging
        for item in songs_to_process[:10]:  # Show first 10 for brevity
            song = item['song']
            should_scrobble = item['should_scrobble']
            reason = item['reason']
            action = "SCROBBLE" if should_scrobble else "DB-ONLY"
            print(f"    - {action}: {song['title']} by {song['artist']} ({reason})")
        
        if len(songs_to_process) > 10:
            print(f"    ... and {len(songs_to_process) - 10} more songs")
        
        if is_first_time and total_to_scrobble > 0:
            print(f"First-time user: Limiting scrobbles to {min(total_to_scrobble, max_first_time_songs)} most recent songs")

        songs_scrobbled = 0
        scrobble_position = 0

        for item in songs_to_process:
            song = item['song']
            position = item['position']
            should_scrobble = item['should_scrobble']
            reason = item['reason']
            
            try:
                if should_scrobble:
                    # Calculate smart timestamp
                    timestamp = self.scrobbler.calculate_timestamp(
                        scrobble_position,
                        total_to_scrobble,
                        is_pro_user=False,  # Can be made configurable
                        is_first_time=is_first_time
                    )
                    
                    # Scrobble the song
                    success = self.scrobbler.scrobble_song(song, self.session, timestamp)
                    
                    if success:
                        songs_scrobbled += 1
                        action = "NEW" if reason == "new_song" else f"RE-SCROBBLE ({reason})" if reason == "reproduction" else "FIRST-TIME"
                        print(f"{action}: {song['title']} by {song['artist']}")
                        scrobble_position += 1
                    else:
                        print(f"FAILED: {song['title']} by {song['artist']} (Last.fm rejected)")
                
                # Update/insert in database
                existing_song = cursor.execute('''
                    SELECT id, max_array_position FROM scrobbles 
                    WHERE track_name = ? AND artist_name = ? AND album_name = ?
                ''', (song['title'], song['artist'], song['album'])).fetchone()
                
                if existing_song:
                    # Update existing song
                    song_id, current_max = existing_song
                    new_max = max(current_max or position, position)
                    
                    cursor.execute('''
                        UPDATE scrobbles 
                        SET array_position = ?, max_array_position = ?, scrobbled_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (position, new_max, song_id))
                else:
                    # Insert new song
                    cursor.execute('''
                        INSERT INTO scrobbles 
                        (track_name, artist_name, album_name, array_position, max_array_position, is_first_time_scrobble)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (song['title'], song['artist'], song['album'], position, position, is_first_time))
                
                self.conn.commit()
                
            except Exception as error:
                failure_type = self.scrobbler.categorize_error(error)
                print(f"ERROR processing '{song['title']}' by {song['artist']}: {error}")
                print(f"Error type: {failure_type.value}")
                
                # Continue processing other songs unless it's an auth error
                if failure_type == FailureType.AUTH:
                    print("Authentication error detected. Stopping execution.")
                    break

        # Check for potential duplicates in the database
        print(f"\\n🔍 Duplicate Detection:")
        cursor.execute('''
            SELECT track_name, artist_name, COUNT(*) as count
            FROM scrobbles
            WHERE scrobbled_at >= datetime('now', '-1 hour')
            GROUP BY track_name, artist_name
            HAVING count > 1
        ''')
        
        duplicates = cursor.fetchall()
        if duplicates:
            print(f"  ⚠️  Potential duplicates found in last hour:")
            for song, count in duplicates:
                print(f"    - {song} (appears {count} times)")
        else:
            print(f"  ✅ No duplicates found in last hour")
        
        cursor.close()
        
        print(f"\\n✅ Scrobbling completed!")
        print(f"📊 Summary:")
        print(f"  - Total songs in today's history: {len(today_songs)}")
        print(f"  - Songs successfully scrobbled: {songs_scrobbled}")
        print(f"  - Songs processed (DB updated): {len(songs_to_process)}")
        
        if is_first_time:
            print(f"  - First-time user: Limited to {max_first_time_songs} scrobbles")
        
        return True

    def _handle_auth_error(self, error: Exception, operation: str) -> bool:
        """Helper method to handle authentication errors consistently"""
        failure_type = self.scrobbler.categorize_error(error)
        
        if failure_type == FailureType.AUTH:
            self.handle_authentication_error(error)
            # Re-raise the exception to ensure the execution fails as requested
            raise error
        else:
            print(f"Error {operation}: {error}")
            print(f"Error type: {failure_type.value}")
            raise error

    def _handle_processing_auth_error(self, error: Exception) -> bool:
        """Helper method to handle authentication errors during processing"""
        failure_type = self.scrobbler.categorize_error(error)
        if failure_type == FailureType.AUTH:
            self.handle_authentication_error(error)
            # Re-raise the exception to ensure the execution fails as requested
            raise error
        else:
            return False  # Continue processing for non-auth errors


def main():
    """Main entry point"""
    print("🎵 Standalone YouTube Music Last.fm Scrobbler")
    print("=" * 50)
    
    try:
        process = ImprovedProcess()
        success = process.execute()
        
        if success:
            print("\n🎉 Process completed successfully!")
        else:
            print("\n❌ Process failed. Please check the errors above.")
            return 1
            
    except KeyboardInterrupt:
        print("\n⏹️  Process interrupted by user")
        return 1
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        # Exit with error code to ensure failure is detected by the GitHub workflow
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())