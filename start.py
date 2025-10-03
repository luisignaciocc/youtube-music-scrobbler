import os
import time
import lastpy
import sqlite3
import webbrowser
import threading
import http.server
import socketserver
from ytmusicapi import YTMusic
import xml.etree.ElementTree as ET
from dotenv import load_dotenv, set_key
from datetime import datetime

load_dotenv()


class TokenHandler(http.server.SimpleHTTPRequestHandler):
    def do_get_token(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b'<html><head><title>Token Received</title></head>')
        self.wfile.write(b'<body><p>Authentication successful! You can now close this window.</p></body></html>')
        self.server.token = self.path.split('?token=')[1]

    def do_GET(self):
        if self.path.startswith('/?token='):
            self.do_get_token()
        else:
            http.server.SimpleHTTPRequestHandler.do_GET(self)


class TokenServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    token = None


class Process:
    def __init__(self):
        self.api_key = os.environ['LAST_FM_API']
        self.session = os.environ.get('LASTFM_SESSION', None)
        self.formatted_date = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        self.conn = sqlite3.connect('./data.db')
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scrobbles (
                id INTEGER PRIMARY KEY,
                track_id TEXT,
                scrobbled_at TEXT DEFAULT CURRENT_TIMESTAMP,
                array_position INTEGER
            )
        ''')
        self.conn.commit()
        cursor.close()

    def get_token(self):
        print("Waiting for authentication...")
        auth_url = f"https://www.last.fm/api/auth/?api_key={self.api_key}&cb=http://localhost:5588"
        with TokenServer(('localhost', 5588), TokenHandler) as httpd:
            webbrowser.open(auth_url)
            thread = threading.Thread(target=httpd.serve_forever)
            thread.start()
            while not httpd.token:
                time.sleep(0.1)
            httpd.shutdown()
        return httpd.token

    def get_session(self, token):
        print("Getting session...")
        xml_response = lastpy.authorize(token)
        try:
            root = ET.fromstring(xml_response)
            token = root.find('session/key').text
            set_key('.env', 'LASTFM_SESSION', token)
            return token
        except Exception as e:
            print(xml_response)
            raise Exception(e)

    def execute(self):
        ytmusic = YTMusic("browser.json")
        if not self.session:
            token = self.get_token()
            self.session = self.get_session(token)
        print("Getting history...")
        history = ytmusic.get_history()
        cursor = self.conn.cursor()

        # Performing scrobbling of songs, cleaning up local DB if needed first, then adding/updating records to local DB and Last.FM
        # Step 1: Collect all today's scrobbles
        today_records = [song["videoId"] for song in history
                         if song["played"] == "Today"
                         and not song["artists"][0]["name"].endswith(" - Topic")]

        # Step 2: Delete all records in the database that are not in today's scrobbles
        if today_records:
            placeholders = ', '.join(['?'] * len(today_records))
            cursor.execute(f'DELETE FROM scrobbles WHERE track_id NOT IN ({placeholders})', today_records)
            self.conn.commit()

        # Step 3: Insert or update today's scrobbles
        i = 0  # Initialize i for scrobble timing
        for index, item in enumerate(history):
            # If it was played before today, or the artist is a topic, skip the song.
            if item["played"] != "Today" or item["artists"][0]["name"].endswith(" - Topic"):
                continue
            record = {
                "artistName": item["artists"][0]["name"],
                "trackName": item["title"],
                "trackID": item["videoId"],
                "ts": self.formatted_date,
                "albumName": (item.get("album") or {}).get("name", item["title"]),
                "arrayPosition": index,
            }

            scroble = cursor.execute('SELECT * FROM scrobbles WHERE track_id = :trackID',
                                     {"trackID": record["trackID"]}).fetchone()

            if scroble is None:
                # No existing record, insert a new one
                cursor.execute('''
                    INSERT INTO scrobbles (track_id, scrobbled_at, array_position)
                    VALUES (:trackID, :ts, :arrayPosition)
                ''', record)
                self.conn.commit()
                print(f"NEW: Scrobble for {record['trackName']} by {record['artistName']}.")

            elif scroble[3] > record["arrayPosition"]:

                # Existing record found and needs to be updated
                cursor.execute('''
                    UPDATE scrobbles
                    SET scrobbled_at = :ts, array_position = :arrayPosition
                    WHERE track_id = :trackID
                ''', record)
                self.conn.commit()
                print(f"UPDATE: Update scrobble for {record['trackName']} by {record['artistName']} with new array position (new listen).")
            else:
                # Existing record found that won't be sent to Last.FM, but local records needs updating
                cursor.execute('''
                    UPDATE scrobbles
                    SET scrobbled_at = :ts, array_position = :arrayPosition
                    WHERE track_id = :trackID
                ''', record)
                self.conn.commit()
                continue

            xml_response = lastpy.scrobble(
                record["trackName"],
                record["artistName"],
                record["albumName"],
                self.session,
                str(int(time.time() - 30 - (i * 90)))
            )
            root = ET.fromstring(xml_response)
            scrobbles = root.find('scrobbles')
            accepted = scrobbles.get('accepted')
            ignored = scrobbles.get('ignored')
            if accepted == '0' and ignored == '1':
                print(f"Error scrobbling {record['trackName']} by {record['artistName']}.")
                print(xml_response)
            else:
                i += 1

        print(f"Scrobbled {i} songs")
        cursor.close()
        self.conn.close()


if __name__ == '__main__':
    Process().execute()