import os
import pytesseract
from PIL import Image, ImageFilter, ImageEnhance

os.environ['TESSDATA_PREFIX'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tessdata')


def extract_text(image):
    """Extract Japanese text from an image using Tesseract OCR.

    Args:
        image: PIL.Image to process.

    Returns:
        str: Extracted Japanese text.
    """
    processed = preprocess(image)
    text = pytesseract.image_to_string(processed, lang='jpn', config='--psm 6')
    return cleanup(text.strip())


# Circled numbers ① - ⑳ → 1 - 20
_CIRCLED_NUMS = {chr(0x2460 + i): str(i + 1) for i in range(20)}


def cleanup(text):
    """Clean up common OCR artifacts."""
    for circled, num in _CIRCLED_NUMS.items():
        text = text.replace(circled, num)
    return text


def preprocess(image):
    """Preprocess image for better OCR accuracy."""
    # Scale up first if small
    width, height = image.size
    if width < 1000:
        scale = 1000 / width
        new_size = (int(width * scale), int(height * scale))
        image = image.resize(new_size, Image.LANCZOS)

    # Convert to grayscale
    gray = image.convert('L')

    # Increase contrast
    enhancer = ImageEnhance.Contrast(gray)
    enhanced = enhancer.enhance(2.0)

    # Sharpen
    sharpened = enhanced.filter(ImageFilter.SHARPEN)

    # Binarize with Otsu-like threshold for clean black/white
    threshold = 128
    binarized = sharpened.point(lambda p: 255 if p > threshold else 0)

    return binarized
