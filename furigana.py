import re
import fugashi
from deep_translator import GoogleTranslator

_tagger = fugashi.Tagger()
_translator = GoogleTranslator(source='ja', target='zh-TW')

# Regex to remove whitespace between CJK characters (common OCR noise)
_CJK_SPACE_RE = re.compile(
    r'(?<=[\u3000-\u9FFF\uF900-\uFAFF])[\s　]+(?=[\u3000-\u9FFF\uF900-\uFAFF])'
)

def get_annotate_only(text):
    """Tokenize and get readings only (offline, fast)."""
    clean_text = _CJK_SPACE_RE.sub('', text)
    segments = _build_segments(_tagger(clean_text))
    return clean_text, segments

def get_translation_only(clean_text):
    """Translate text via Google Translate (requires network)."""
    try:
        return _translator.translate(clean_text)
    except Exception as e:
        return f"(翻譯失敗: {e})"
        
def annotate_with_translation(text):
    """Annotate Japanese text with readings and translate to Traditional Chinese."""
    if not text.strip():
        return {'segments': [], 'translation': ""}

    clean_text = _CJK_SPACE_RE.sub('', text)
    segments = _build_segments(_tagger(clean_text))
    translation = get_translation_only(clean_text)

    return {'segments': segments, 'translation': translation}

# --- Helper functions ---

def _build_segments(words):
    """Build (surface, reading) segment list from tokenized words."""
    segments = []
    for word in words:
        surface = word.surface
        reading = _get_reading(word)
        if _contains_kanji(surface):
            if reading:
                hiragana = _kata_to_hira(reading)
                segments.append((surface, hiragana) if hiragana != surface else (surface, None))
            else:
                fallback = _get_fallback_reading(surface)
                segments.append((surface, fallback) if fallback else (surface, None))
        else:
            segments.append((surface, None))
    return segments

def _get_reading(word):
    """Extract katakana reading from MeCab feature fields."""
    for attr in ('kana', 'pron', 'pronBase'):
        try:
            val = getattr(word.feature, attr)
            if val and val != '*': return val
        except (AttributeError, IndexError): continue

    # Fallback: parse from raw feature string
    try:
        features = str(word.feature).split(',')
        for f in reversed(features):
            f = f.strip()
            if f and f != '*' and all(0x30A0 <= ord(c) <= 0x30FF for c in f): return f
    except: pass
    return None

def _get_fallback_reading(text):
    """Attempt per-character reading when whole-word reading is unavailable."""
    parts = []
    for char in text:
        if _contains_kanji(char):
            words = _tagger(char)
            for w in words:
                r = _get_reading(w)
                if r: parts.append(_kata_to_hira(r))
                else: return None
        else: parts.append(char)
    return ''.join(parts) if parts else None

def _kata_to_hira(text):
    """Convert katakana to hiragana."""
    return ''.join(chr(ord(c) - 0x60) if 0x30A1 <= ord(c) <= 0x30F6 else c for c in text)

def _contains_kanji(text):
    """Check if text contains any kanji characters."""
    for char in text:
        cp = ord(char)
        if 0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF: return True
    return False
