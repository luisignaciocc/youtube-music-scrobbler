#!/usr/bin/env python3
"""
Script to send failure notification to Discord with details from the scrobble job
"""
import os
import requests
import sys
from datetime import datetime


def send_discord_notification():
    webhook_url = os.environ.get('DISCORD_WEBHOOK_URL')
    if not webhook_url:
        print("Error: DISCORD_WEBHOOK_URL environment variable not set")
        sys.exit(1)
    
    scrobble_log = os.environ.get('SCROBBLE_LOG', 'No log available')
    
    # In GitHub Actions environment, the most common cause of failure is expired cookie
    # Since logs are often minimal when the script fails, we'll provide direct guidance for the most likely issue
    failure_reason = "❌ YouTube Music cookie likely expired or invalid"
    resolution_steps = (
        "**Resolution (Most Important):**\n"
        "Your YouTube Music cookie has likely expired and needs to be refreshed.\n\n"
        "**Steps to update your cookie:**\n"
        "1. Sign in to YouTube Music: https://music.youtube.com\n"
        "2. Open Developer Tools (F12)\n"
        "3. Go to Network tab\n"
        "4. Refresh the page and find any request to music.youtube.com\n"
        "5. Copy the 'Cookie' header value\n"
        "6. Update the `YTMUSIC_COOKIE` in your GitHub repository secrets\n\n"
        "**Note:** YouTube Music cookies typically expire every few days, so this is expected behavior."
    )
    
    color = 15105570  # Orange color for authentication issues
    
    # Prepare the embed message
    embed = {
        "embeds": [
            {
                "title": "❌ YouTube Music Scrobble Sync Failed!",
                "description": failure_reason,
                "color": color,
                "fields": [
                    {
                        "name": "📋 Update Required",
                        "value": resolution_steps,
                        "inline": False
                    },
                    {
                        "name": "📋 Other Possible Causes",
                        "value": (
                            "• Last.fm API credentials may need refreshing\n"
                            "• Network connectivity issues\n"
                            "• Temporary service unavailability"
                        ),
                        "inline": False
                    },
                    {
                        "name": "🔍 Raw Logs",
                        "value": f"```\n{scrobble_log[-600:] if len(scrobble_log) > 600 else scrobble_log}\n```",
                        "inline": False
                    }
                ],
                "footer": {
                    "text": f"Run ID: {os.environ.get('GITHUB_RUN_ID', 'N/A')} | Attempt: {os.environ.get('GITHUB_RUN_ATTEMPT', 'N/A')} | {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        ]
    }
    
    try:
        response = requests.post(webhook_url, json=embed)
        response.raise_for_status()
        print("Discord notification sent successfully")
    except requests.exceptions.RequestException as e:
        print(f"Error sending Discord notification: {e}")
        sys.exit(1)


if __name__ == "__main__":
    send_discord_notification()