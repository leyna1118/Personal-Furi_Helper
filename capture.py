import win32gui
from PIL import ImageGrab


_target_hwnd = None


def get_foreground_window_rect():
    """Get the position and size of the target window.

    On the first call, captures the current foreground window as the target.
    On subsequent calls, reuses that same window so it doesn't matter
    which window is focused.

    Returns:
        tuple: (left, top, right, bottom) of the window, or None if failed.
    """
    global _target_hwnd
    if _target_hwnd is None or not win32gui.IsWindow(_target_hwnd):
        _target_hwnd = win32gui.GetForegroundWindow()
    if _target_hwnd == 0:
        return None
    rect = win32gui.GetWindowRect(_target_hwnd)
    return rect


def reset_target_window():
    """Reset the target window so the next capture picks a new foreground window."""
    global _target_hwnd
    _target_hwnd = None


def capture_region(window_rect, region):
    """Capture a sub-region of a window.

    Args:
        window_rect: (left, top, right, bottom) of the window.
        region: dict with keys 'x', 'y', 'width', 'height' relative to window.

    Returns:
        PIL.Image of the captured region.
    """
    win_left, win_top, win_right, win_bottom = window_rect

    abs_left = win_left + region['x']
    abs_top = win_top + region['y']
    abs_right = abs_left + region['width']
    abs_bottom = abs_top + region['height']

    screenshot = ImageGrab.grab(bbox=(abs_left, abs_top, abs_right, abs_bottom), all_screens=True)
    return screenshot
