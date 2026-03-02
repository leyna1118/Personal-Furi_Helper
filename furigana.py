import re
import fugashi

_tagger = fugashi.Tagger()

# Pattern to match whitespace between CJK characters
_CJK_SPACE_RE = re.compile(
    r'(?<=[\u3000-\u9FFF\uF900-\uFAFF])[\s　]+(?=[\u3000-\u9FFF\uF900-\uFAFF])'
)


def annotate(text):
    """Return structured segments for ruby-style furigana rendering.

    Uses MeCab morphological analysis for accurate compound word readings.

    Returns:
        list of (text, reading_or_None) tuples.
    """
    # Remove spaces between CJK characters (common OCR artifact)
    text = _CJK_SPACE_RE.sub('', text)

    segments = []
    words = _tagger(text)
    for word in words:
        surface = word.surface
        reading = _get_reading(word)

        if _contains_kanji(surface):
            if reading:
                hiragana = _kata_to_hira(reading)
                if hiragana != surface:
                    segments.append((surface, hiragana))
                else:
                    segments.append((surface, None))
            else:
                # Fallback: re-analyze the surface alone to get a reading
                fallback = _get_fallback_reading(surface)
                if fallback:
                    segments.append((surface, fallback))
                else:
                    segments.append((surface, None))
        else:
            segments.append((surface, None))

    return segments


def _get_reading(word):
    """Extract katakana reading from MeCab word."""
    for attr in ('kana', 'pron', 'pronBase'):
        try:
            val = getattr(word.feature, attr)
            if val and val != '*':
                return val
        except (AttributeError, IndexError):
            continue

    # Fallback: check raw feature string for katakana field
    try:
        features = str(word.feature).split(',')
        for f in reversed(features):
            f = f.strip()
            if f and f != '*' and all(0x30A0 <= ord(c) <= 0x30FF for c in f):
                return f
    except Exception:
        pass

    return None


def _get_fallback_reading(text):
    """Try to get a reading for text that MeCab couldn't read."""
    parts = []
    for char in text:
        if _contains_kanji(char):
            words = _tagger(char)
            for w in words:
                r = _get_reading(w)
                if r:
                    parts.append(_kata_to_hira(r))
                else:
                    return None
        else:
            parts.append(char)
    return ''.join(parts) if parts else None


def _kata_to_hira(text):
    """Convert katakana to hiragana."""
    return ''.join(
        chr(ord(c) - 0x60) if 0x30A1 <= ord(c) <= 0x30F6 else c
        for c in text
    )


def _contains_kanji(text):
    """Check if text contains any kanji characters."""
    for char in text:
        cp = ord(char)
        if 0x4E00 <= cp <= 0x9FFF:
            return True
        if 0x3400 <= cp <= 0x4DBF:
            return True
    return False
