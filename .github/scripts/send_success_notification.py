#!/usr/bin/env python
import os
import json
import requests

log = os.environ.get("SCROBBLE_LOG", "")
webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")

if not webhook_url:
    print("DISCORD_WEBHOOK_URL not set. Skipping notification.")
    exit(0)

# Discord has a 2000 character limit for embed descriptions.
if len(log) > 1980:
    log = log[:1980] + "\n... (log truncated)"

payload = {
    "content": "YouTube Music Scrobble Sync succeeded!",
    "embeds": [{
        "title": "Scrobble Log",
        "description": f"```\n{log}\n```"
    }]
}

try:
    response = requests.post(webhook_url, json=payload)
    response.raise_for_status()
    print("Successfully sent Discord notification.")
except requests.exceptions.RequestException as e:
    print(f"Failed to send Discord notification: {e}")
    exit(1)
