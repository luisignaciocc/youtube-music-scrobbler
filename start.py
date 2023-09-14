import os
import time
import lastpy
import webbrowser
import threading
import http.server
import socketserver
from ytmusicapi import YTMusic
import xml.etree.ElementTree as ET
from dotenv import load_dotenv, set_key
from datetime import datetime, timedelta

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


class Process:
    def __init__(self):
        self.api_key = os.environ['LAST_FM_API']
        try:
            self.session = os.environ['LASTFM_SESSION']
        except:
            self.session = None

        current_datetime = datetime.now()
        yesterday_datetime = current_datetime - timedelta(days=1)
        self.formatted_date = yesterday_datetime.strftime(
            "%Y-%m-%dT%H:%M:%S.%fZ")

    def get_token(self):
        print("Waiting for authentication...")
        auth_url = "https://www.last.fm/api/auth/?api_key=" + \
            self.api_key + "&cb=http://localhost:5588"
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
        ytmusic = YTMusic("oauth.json")

        if not self.session:
            token = self.get_token()
            self.session = self.get_session(token)
        print("Getting history...")
        history = ytmusic.get_history()
        total = len(history)
        i = 0
        for item in history:
            i += 1
            print("Scrobbling " + str(i) + " songs of " + str(total))
            record = {
                "artistName": item["artists"][0]["name"],
                "trackName": item["title"],
                "ts": self.formatted_date,
                "albumName": item["album"]["name"] if "album" in item and item["album"] is not None else None,
            }
            resp = lastpy.scrobble(
                record["trackName"],
                record["artistName"],
                record["albumName"],
                self.session
            )
            print(resp)


if __name__ == '__main__':
    Process().execute()
