# YOUTUBE MUSIC LAST.FM SCROBBLER

The YouTube Music Last.fm Scrobbler is a Python application that fetches your YouTube Music listening history from the last 24 hours and scrobbles it to Last.fm. This project offers two versions with different approaches and capabilities.

## 📋 Available Versions

| Version | File | Approach | Best For |
|---------|------|----------|----------|
| **🌟 Standalone** | `start_standalone.py` | Direct HTML scraping | **Recommended** - More reliable, multilingual, smarter |
| **Legacy** | `start.py` | YTMusic API | Simple setup, backward compatibility |

---

## 🚀 Quick Start (Standalone Version - Recommended)

### Prerequisites

1. Install Python 3.8+ and dependencies:
   ```bash
   # Using conda (recommended)
   conda env create -f environment.yml
   conda activate ytmusic-scrobbler
   
   # OR using pip
   pip install -r requirements.txt
   ```

2. Get your Last.fm API credentials from [Last.fm API](https://www.last.fm/api/account/create)

3. Create a `.env` file:
   ```bash
   LAST_FM_API=your_lastfm_api_key
   LAST_FM_API_SECRET=your_lastfm_api_secret
   ```

### Run Standalone Version

```bash
python start_standalone.py
```

On first run, you'll be prompted to:
1. **Authenticate with Last.fm** (browser will open automatically)  
2. **Provide your YouTube Music cookie** (detailed instructions provided)

**To get your YouTube Music cookie:**
1. Go to [https://music.youtube.com](https://music.youtube.com) in your browser
2. Open Developer Tools (F12) → Network tab  
3. Refresh the page and find any `music.youtube.com` request
4. Copy the complete `Cookie` header value
5. Paste when prompted (or save to `.env` as `YTMUSIC_COOKIE`)

---

## 🔧 Legacy Version Setup

If you prefer the original YTMusic API approach:

### Additional Setup for Legacy Version

1. Install ytmusicapi and authenticate:
   ```bash
   pip install ytmusicapi==1.10.3
   ytmusicapi browser
   ```
   
2. Follow the [ytmusicapi browser authentication](https://ytmusicapi.readthedocs.io/en/stable/setup/browser.html) instructions to create `browser.json`

3. Run the legacy version:
   ```bash
   python start.py
   ```

---

## 📊 Version Comparison

### 🌟 Standalone Version (`start_standalone.py`)

**✅ Advantages:**
- **No API dependencies** - Direct HTML scraping eliminates API rate limits
- **Multilingual support** - Detects "Today" in 50+ languages (English, Spanish, Chinese, Russian, Arabic, etc.)
- **Smart timestamp distribution**:
  - First-time users: Logarithmic over 24 hours
  - Regular users: Logarithmic over 1 hour
  - Pro users: Linear over 5 minutes
- **Better duplicate detection** - Tracks re-reproductions and position changes
- **Robust error handling** - Categorizes and handles different error types
- **Enhanced logging** - Better visibility into processing and language detection
- **No browser.json needed** - Just requires your browser cookie

**⚠️ Considerations:**
- Requires copying cookie from browser (but provides detailed instructions)
- Cookie needs periodic refresh (browser will notify when needed)

### 📜 Legacy Version (`start.py`)

**✅ Advantages:**
- **Simple setup** - Uses YTMusic API with `browser.json`
- **Established approach** - Original working implementation
- **No cookie handling** - API-based authentication

**⚠️ Limitations:**
- **API dependency** - Subject to rate limits and API changes
- **English-only date detection** - Only recognizes "Today" in English
- **Fixed timestamp intervals** - Simple 90-second spacing
- **Basic error handling** - Limited error categorization
- **Requires ytmusicapi** - Additional dependency for API access

---

## 🗄️ Database Schema

Both versions use SQLite to track scrobbled songs and prevent duplicates:

### Standalone Version Schema
```sql
CREATE TABLE scrobbles (
    id INTEGER PRIMARY KEY,
    track_name TEXT,
    artist_name TEXT,
    album_name TEXT,
    scrobbled_at TEXT DEFAULT CURRENT_TIMESTAMP,
    array_position INTEGER,
    max_array_position INTEGER,          -- NEW: Tracks highest position
    is_first_time_scrobble BOOLEAN       -- NEW: First-time user flag
)
```

### Legacy Version Schema
```sql
CREATE TABLE scrobbles (
    id INTEGER PRIMARY KEY,
    track_name TEXT,
    artist_name TEXT,  
    album_name TEXT,
    scrobbled_at TEXT DEFAULT CURRENT_TIMESTAMP,
    array_position INTEGER
)
```

---

## 📝 How It Works

### Standalone Version Process
1. **Fetches YouTube Music history page** directly via HTTP
2. **Extracts embedded JSON data** from HTML using regex parsing
3. **Detects today's songs** using multilingual date detection (50+ languages)
4. **Smart position tracking** - Identifies new songs and re-reproductions
5. **Calculates intelligent timestamps** - Different strategies for different user types
6. **Scrobbles to Last.fm** with proper error handling and retry logic
7. **Updates database** with enhanced tracking information

### Legacy Version Process  
1. **Uses YTMusic API** to fetch history data
2. **Filters "Today" songs** (English only)
3. **Simple duplicate prevention** based on position
4. **Fixed timestamp intervals** (90 seconds apart)
5. **Basic scrobbling** to Last.fm
6. **Database updates** with basic tracking

---

## 🌍 Multilingual Support (Standalone Only)

The standalone version automatically detects "Today" in these language families:

- **Latin**: English, Spanish, Portuguese, Italian, French, German, Dutch, etc.
- **Cyrillic**: Russian, Ukrainian, Bulgarian, Serbian, etc.
- **Arabic**: Arabic, Persian, Urdu
- **CJK**: Chinese (Simplified/Traditional), Japanese, Korean
- **Indic**: Hindi, Bengali, Tamil, Telugu, etc.
- **Southeast Asian**: Thai, Vietnamese, Indonesian, etc.
- **Others**: Hebrew, Georgian, Armenian, etc.

---

## 🚀 Migration from Legacy to Standalone

1. **Stop using browser.json** - No longer needed
2. **Get YouTube Music cookie** - Follow the instructions above  
3. **Add to .env file**: `YTMUSIC_COOKIE=your_cookie_here`
4. **Run standalone version**: `python start_standalone.py`
5. **Database migration** - Automatic (new columns added seamlessly)

---

## 🔧 Configuration

### Environment Variables (.env)
```bash
# Required for both versions
LAST_FM_API=your_lastfm_api_key
LAST_FM_API_SECRET=your_lastfm_api_secret

# Added automatically after first run
LASTFM_SESSION=your_session_token

# Required for standalone version only  
YTMUSIC_COOKIE=your_complete_browser_cookie
```

### Files Used
| File | Standalone | Legacy | Description |
|------|------------|--------|-------------|
| `.env` | ✅ Required | ✅ Required | API keys and tokens |
| `browser.json` | ❌ Not needed | ✅ Required | YTMusic API auth |
| `data.db` | ✅ Enhanced | ✅ Basic | SQLite tracking database |

---

## 🐛 Troubleshooting

### Common Issues - Standalone Version

**❌ "Cookie is missing __Secure-3PAPISID"**
- Ensure you copied the complete cookie from Developer Tools
- Make sure you're logged into YouTube Music in the browser

**❌ "Authentication failed"**  
- Your cookie may have expired - get a fresh one from browser
- Cookies typically last several hours to days

**❌ "No songs played today"**
- Check your YouTube Music language - multilingual detection should work
- Report unknown date formats to help improve detection

### Common Issues - Legacy Version

**❌ "browser.json not found"**
- Run `ytmusicapi browser` first to generate authentication

**❌ "No results found"**  
- YTMusic API response format may have changed
- Check if ytmusicapi needs updating

---

## 📋 Deployment

Both versions can be deployed to servers, but have different requirements:

### Standalone Version Deployment
1. Run locally first to complete Last.fm OAuth
2. Copy `.env` file to server (includes `LASTFM_SESSION`)
3. Set up cron job or scheduler:
   ```bash
   # Run daily at 23:59
   59 23 * * * /path/to/python /path/to/start_standalone.py
   ```

### Legacy Version Deployment  
1. Run locally first for Last.fm OAuth and YTMusic setup
2. Copy `.env` and `browser.json` to server
3. Set up cron job with both files

---

## 🤝 Contributing

Contributions are welcome! Please focus improvements on the standalone version as it's the recommended approach.

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more information.

---

## 🎵 Enjoy Your Scrobbles!

Whether you choose the standalone or legacy version, you'll be able to seamlessly sync your YouTube Music listening history with Last.fm. The standalone version is recommended for its reliability, multilingual support, and smart features, but both versions will get your music scrobbled! 🎶