"""
Multilingual date detection for YouTube Music playedAt values
Supports 50+ languages including Latin, Cyrillic, Arabic, CJK, and Indic scripts
"""
from typing import Dict, Set, List, Optional, NamedTuple


class DateDetectionResult(NamedTuple):
    is_today: bool
    is_yesterday: bool
    detected_language: Optional[str]
    original_value: str


# Comprehensive list of "Today" translations
TODAY_TRANSLATIONS = {
    # Latin script
    'Today': 'en',           # English
    'Hoy': 'es',            # Spanish
    'Hoje': 'pt',           # Portuguese
    'Oggi': 'it',           # Italian
    'Aujourd\'hui': 'fr',   # French
    'Heute': 'de',          # German
    'Vandaag': 'nl',        # Dutch
    'Idag': 'sv',           # Swedish
    'I dag': 'no',          # Norwegian
    'Tänään': 'fi',         # Finnish
    'Ma': 'et',             # Estonian
    'Šodien': 'lv',         # Latvian
    'Šiandien': 'lt',       # Lithuanian
    'Dzisiaj': 'pl',        # Polish
    'Dnes': 'cs',           # Czech
    'Danes': 'sl',          # Slovenian
    'Astăzi': 'ro',         # Romanian
    'Täna': 'et',           # Estonian (alternative)
    'Bugün': 'tr',          # Turkish
    'Σήμερα': 'el',         # Greek
    'Днес': 'bg',           # Bulgarian
    'Данас': 'sr',          # Serbian
    'Danas': 'hr',          # Croatian
    'Данеска': 'mk',        # Macedonian
    
    # Cyrillic script
    'Сегодня': 'ru',        # Russian
    'Сьогодні': 'uk',       # Ukrainian
    'Сёння': 'be',          # Belarusian
    
    # Arabic script
    'اليوم': 'ar',           # Arabic
    'امروز': 'fa',          # Persian/Farsi
    'آج': 'ur',             # Urdu
    
    # CJK scripts
    '今天': 'zh',            # Chinese Simplified
    '今日': 'ja',            # Japanese
    '오늘': 'ko',            # Korean
    
    # Indic scripts
    'आज': 'hi',             # Hindi
    'আজ': 'bn',             # Bengali
    'આજે': 'gu',            # Gujarati
    'இன்று': 'ta',         # Tamil
    'ఈ రోజు': 'te',         # Telugu
    'ಇಂದು': 'kn',           # Kannada
    'ഇന്ന്': 'ml',          # Malayalam
    'ਅੱਜ': 'pa',            # Punjabi
    
    # Southeast Asian
    'วันนี้': 'th',          # Thai
    'Hôm nay': 'vi',        # Vietnamese
    'Hari ini': 'id',       # Indonesian
    'Ngayong araw': 'tl',   # Filipino/Tagalog
    'ယနေ့': 'my',           # Burmese/Myanmar
    
    # African languages
    'Leo': 'sw',            # Swahili
    'Vandag': 'af',         # Afrikaans
    
    # Other scripts
    'היום': 'he',           # Hebrew
    'დღეს': 'ka',           # Georgian
    'այսօր': 'hy',          # Armenian
}


# Comprehensive list of "Yesterday" translations
YESTERDAY_TRANSLATIONS = {
    # Latin script
    'Yesterday': 'en',       # English
    'Ayer': 'es',           # Spanish
    'Ontem': 'pt',          # Portuguese
    'Ieri': 'it',           # Italian
    'Hier': 'fr',           # French
    'Gestern': 'de',        # German
    'Gisteren': 'nl',       # Dutch
    'Igår': 'sv',           # Swedish
    'I går': 'no',          # Norwegian
    'Eilen': 'fi',          # Finnish
    'Wczoraj': 'pl',        # Polish
    'Včera': 'cs',          # Czech
    'Včeraj': 'sl',         # Slovenian
    'Tegnap': 'hu',         # Hungarian
    'Dün': 'tr',            # Turkish
    'Χθες': 'el',           # Greek
    'Вчера': 'bg',          # Bulgarian
    'Јуче': 'sr',           # Serbian
    'Jučer': 'hr',          # Croatian
    
    # Cyrillic script
    'Вчера': 'ru',          # Russian
    'Вчора': 'uk',          # Ukrainian
    'Учора': 'be',          # Belarusian
    
    # Arabic script
    'أمس': 'ar',            # Arabic
    'دیروز': 'fa',          # Persian/Farsi
    'کل': 'ur',             # Urdu
    
    # CJK scripts
    '昨天': 'zh',            # Chinese Simplified
    '昨日': 'ja',            # Japanese
    '어제': 'ko',            # Korean
    
    # Indic scripts
    'कल': 'hi',             # Hindi (can mean yesterday or tomorrow)
    'গতকাল': 'bn',          # Bengali
    'ગઈકાલે': 'gu',         # Gujarati
    'நேற்று': 'ta',        # Tamil
    'నిన్న': 'te',          # Telugu
    'ನಿನ್ನೆ': 'kn',         # Kannada
    'ഇന്നലെ': 'ml',         # Malayalam
    'ਕੱਲ੍ਹ': 'pa',          # Punjabi
    
    # Southeast Asian
    'เมื่อวาน': 'th',        # Thai
    'Hôm qua': 'vi',        # Vietnamese
    'Kemarin': 'id',        # Indonesian
    'Semalam': 'ms',        # Malay
    'Kahapon': 'tl',        # Filipino/Tagalog
    'မနေ့က': 'my',          # Burmese/Myanmar
    
    # African languages
    'Jana': 'sw',           # Swahili
    'Gister': 'af',         # Afrikaans
    
    # Other scripts
    'אתמול': 'he',          # Hebrew
    'გუშინ': 'ka',          # Georgian
    'երեկ': 'hy',           # Armenian
}


def detect_date_value(played_at: Optional[str]) -> DateDetectionResult:
    """
    Detect if a playedAt value represents today or yesterday in any supported language
    
    Args:
        played_at: The playedAt string from YouTube Music
        
    Returns:
        DateDetectionResult with detection info
    """
    if not played_at:
        return DateDetectionResult(
            is_today=False,
            is_yesterday=False,
            detected_language=None,
            original_value=played_at or ''
        )
    
    trimmed = played_at.strip()
    
    # Check for today
    if trimmed in TODAY_TRANSLATIONS:
        return DateDetectionResult(
            is_today=True,
            is_yesterday=False,
            detected_language=TODAY_TRANSLATIONS[trimmed],
            original_value=trimmed
        )
    
    # Check for yesterday
    if trimmed in YESTERDAY_TRANSLATIONS:
        return DateDetectionResult(
            is_today=False,
            is_yesterday=True,
            detected_language=YESTERDAY_TRANSLATIONS[trimmed],
            original_value=trimmed
        )
    
    # No match found
    return DateDetectionResult(
        is_today=False,
        is_yesterday=False,
        detected_language=None,
        original_value=trimmed
    )


def is_today_song(played_at: Optional[str]) -> bool:
    """Check if a song was played today"""
    return detect_date_value(played_at).is_today


def is_yesterday_song(played_at: Optional[str]) -> bool:
    """Check if a song was played yesterday"""
    return detect_date_value(played_at).is_yesterday


def get_all_today_variants() -> List[str]:
    """Get all supported 'today' variants for debugging"""
    return list(TODAY_TRANSLATIONS.keys())


def get_all_yesterday_variants() -> List[str]:
    """Get all supported 'yesterday' variants for debugging"""
    return list(YESTERDAY_TRANSLATIONS.keys())


def get_unknown_date_values(songs: List[Dict[str, str]]) -> List[str]:
    """
    Get unknown playedAt values that should be logged for future expansion
    
    Args:
        songs: List of songs with playedAt field
        
    Returns:
        List of unknown date values
    """
    unknown_values: Set[str] = set()
    
    for song in songs:
        played_at = song.get('playedAt')
        if played_at:
            result = detect_date_value(played_at)
            if not result.is_today and not result.is_yesterday and played_at.strip():
                unknown_values.add(played_at.strip())
    
    return list(unknown_values)


def get_detected_languages(songs: List[Dict[str, str]]) -> Set[str]:
    """
    Get all detected languages from songs played today
    
    Args:
        songs: List of songs with playedAt field
        
    Returns:
        Set of detected language codes
    """
    detected_languages: Set[str] = set()
    
    for song in songs:
        played_at = song.get('playedAt')
        result = detect_date_value(played_at)
        if result.detected_language and result.is_today:
            detected_languages.add(result.detected_language)
    
    return detected_languages