# FuriHelper

A hotkey-triggered OCR tool for reading Japanese game text. Press a hotkey while playing a game to capture dialogue, extract the text, and display it with ruby-style furigana above the kanji in a scrolling log.

## How It Works

1. Run `main.py` on your secondary monitor
2. Play your game on any monitor
3. Press the capture hotkey (default **F4**) when you see text you want to read
4. The program captures the dialogue region, runs OCR, adds furigana, and displays the result

## Setup

### 1. Install Tesseract OCR

Download from https://github.com/UB-Mannheim/tesseract/wiki

During installation, make sure Tesseract is added to your PATH.

Japanese language data (`jpn.traineddata`) is already included in the `tessdata/` folder — no extra setup needed.

### 2. Install Python dependencies

```
pip install -r requirements.txt
```

### 3. Run

```
python main.py
```

On first launch, you'll be prompted to drag-select the text region of your game window. This is saved to `config.json` and reused across sessions.

The region selector handles mixed-DPI multi-monitor setups (e.g. a HiDPI laptop at 200% scaling + an external monitor at 100%). Coordinates are automatically converted between display scaling and physical pixels.

## Controls

| Action | How |
|---|---|
| Capture text | Press the configured hotkey (default **F4**, works globally) |
| Change hotkey | Click **Set Hotkey**, then press your desired key |
| Re-select region | Click **Select Region** button (works across all monitors) |
| Adjust font size | Click **+** / **-** buttons |
| Clear log | Click **Clear Log** button |

## Files

| File | Purpose |
|---|---|
| `main.py` | Entry point, GUI, and hotkey listener |
| `capture.py` | Foreground window detection and screenshot |
| `ocr_engine.py` | Tesseract OCR with image preprocessing |
| `furigana.py` | Kanji to hiragana annotation via MeCab (fugashi) |
| `region_selector.py` | Multi-monitor drag-to-select overlay for defining capture area |
| `config.json` | Auto-generated file storing your selected region and hotkey |

## Requirements

- Python 3.8+
- Tesseract OCR
- Windows 10/11
