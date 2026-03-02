import tkinter as tk
import json
import os
import win32api
import win32con

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')


def get_monitors():
    """Enumerate all monitors and return their position/size info.

    Returns:
        list of dicts with keys: 'name', 'x', 'y', 'width', 'height'
    """
    monitors = []
    for i, (hmon, hdc, (left, top, right, bottom)) in enumerate(
            win32api.EnumDisplayMonitors(None, None)):
        monitors.append({
            'name': f'Monitor {i + 1}: {right - left}x{bottom - top}',
            'x': left,
            'y': top,
            'width': right - left,
            'height': bottom - top,
        })
    return monitors


class MonitorChooser:
    """Dialog that lets the user pick which monitor to use for region selection."""

    def __init__(self, parent, on_chosen):
        """
        Args:
            parent: Parent tk window (can be None).
            on_chosen: Callback receiving the chosen monitor dict, or None if cancelled.
        """
        self.on_chosen = on_chosen
        self.monitors = get_monitors()

        if len(self.monitors) == 1:
            # Only one monitor, skip the dialog
            on_chosen(self.monitors[0])
            return

        self.dialog = tk.Toplevel(parent)
        self.dialog.title('Select Monitor')
        self.dialog.attributes('-topmost', True)
        self.dialog.resizable(False, False)
        self.dialog.configure(bg='#1e1e2e')
        self.dialog.grab_set()

        label = tk.Label(self.dialog, text='Which monitor to select region on?',
                         font=('Arial', 12), fg='#cdd6f4', bg='#1e1e2e')
        label.pack(padx=20, pady=(15, 10))

        for monitor in self.monitors:
            btn = tk.Button(
                self.dialog,
                text=monitor['name'],
                command=lambda m=monitor: self._choose(m),
                bg='#45475a', fg='#cdd6f4',
                activebackground='#585b70',
                font=('Arial', 11), relief=tk.FLAT,
                padx=20, pady=8, width=30,
            )
            btn.pack(padx=20, pady=3)

        cancel_btn = tk.Button(
            self.dialog, text='Cancel',
            command=self._cancel,
            bg='#313244', fg='#a6adc8',
            activebackground='#45475a',
            font=('Arial', 10), relief=tk.FLAT,
            padx=10, pady=4,
        )
        cancel_btn.pack(padx=20, pady=(5, 15))

        self.dialog.bind('<Escape>', lambda e: self._cancel())

        # Center the dialog on screen
        self.dialog.update_idletasks()
        w = self.dialog.winfo_width()
        h = self.dialog.winfo_height()
        sx = self.dialog.winfo_screenwidth()
        sy = self.dialog.winfo_screenheight()
        self.dialog.geometry(f'+{(sx - w) // 2}+{(sy - h) // 2}')

    def _choose(self, monitor):
        self.dialog.destroy()
        self.on_chosen(monitor)

    def _cancel(self):
        self.dialog.destroy()
        self.on_chosen(None)


def _load_config():
    if not os.path.exists(CONFIG_PATH):
        return {}
    try:
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _save_config(config):
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)


def load_region():
    config = _load_config()
    region = config.get('region')
    if region and all(k in region for k in ('x', 'y', 'width', 'height')):
        return region
    return None


def save_region(region):
    config = _load_config()
    config['region'] = region
    _save_config(config)


def load_hotkey():
    return _load_config().get('hotkey', 'F4')


def save_hotkey(hotkey):
    config = _load_config()
    config['hotkey'] = hotkey
    _save_config(config)


def _get_dpi_scale():
    """Get the ratio of physical pixels to tkinter coordinates.

    Compares Win32 primary monitor size (physical pixels, DPI-aware) with
    tkinter's reported screen size (logical pixels) to derive the scaling
    factor that tkinter applies internally.

    Returns 1.0 when both coordinate systems match (e.g. 100% scaling).
    Returns 2.0 on a 200% scaled primary monitor, etc.
    """
    phys_w = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
    # Need a temporary Tk to query; use existing one if available
    try:
        temp = tk._default_root
        tk_w = temp.winfo_screenwidth()
    except Exception:
        tk_w = phys_w
    return phys_w / tk_w if tk_w else 1.0


class RegionSelector:
    """Semi-transparent overlay on a single monitor for drag-selecting a capture region."""

    def __init__(self, on_selected, monitor=None):
        """
        Args:
            on_selected: Callback function receiving (x, y, width, height) in physical
                         screen pixel coords (matching Win32 API / ImageGrab).
            monitor: dict with 'x', 'y', 'width', 'height' for the target monitor
                     (in physical pixels from EnumDisplayMonitors).
                     If None, spans the entire virtual screen (legacy behavior).
        """
        self.on_selected = on_selected
        self.start_x = 0
        self.start_y = 0
        self._draw_start_x = 0
        self._draw_start_y = 0
        self.rect_id = None

        # Detect DPI scaling between physical pixels and tkinter coordinates
        self.dpi_scale = _get_dpi_scale()

        if monitor:
            mx, my, mw, mh = monitor['x'], monitor['y'], monitor['width'], monitor['height']
        else:
            mx = win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
            my = win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)
            mw = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
            mh = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)

        self.monitor_x = mx
        self.monitor_y = my

        # Convert physical pixel coords to tkinter logical coords for geometry
        tk_mx = int(mx / self.dpi_scale)
        tk_my = int(my / self.dpi_scale)
        tk_mw = int(mw / self.dpi_scale)
        tk_mh = int(mh / self.dpi_scale)

        self.root = tk.Toplevel()
        self.root.overrideredirect(True)
        self.root.geometry(f'{tk_mw}x{tk_mh}+{tk_mx}+{tk_my}')
        self.root.attributes('-alpha', 0.3)
        self.root.attributes('-topmost', True)
        self.root.configure(bg='black')
        self.root.title('Select Text Region')

        self.canvas = tk.Canvas(self.root, cursor='crosshair', bg='black',
                                highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Instructions label
        self.canvas.create_text(
            tk_mw // 2,
            50,
            text='Drag to select the text region, then release. Press Escape to cancel.',
            fill='white',
            font=('Arial', 16)
        )

        self.canvas.bind('<ButtonPress-1>', self._on_press)
        self.canvas.bind('<B1-Motion>', self._on_drag)
        self.canvas.bind('<ButtonRelease-1>', self._on_release)
        self.root.bind('<Escape>', lambda e: self.root.destroy())

    def _on_press(self, event):
        # Store physical pixel coords for region output
        self.start_x = int(event.x_root * self.dpi_scale)
        self.start_y = int(event.y_root * self.dpi_scale)
        # Store canvas coords for rectangle drawing
        self._draw_start_x = event.x
        self._draw_start_y = event.y
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y,
            outline='red', width=2
        )

    def _on_drag(self, event):
        if self.rect_id:
            self.canvas.coords(self.rect_id,
                               self._draw_start_x, self._draw_start_y,
                               event.x, event.y)

    def _on_release(self, event):
        # Convert tkinter coords to physical pixels
        end_x = int(event.x_root * self.dpi_scale)
        end_y = int(event.y_root * self.dpi_scale)

        x = min(self.start_x, end_x)
        y = min(self.start_y, end_y)
        w = abs(end_x - self.start_x)
        h = abs(end_y - self.start_y)

        self.root.destroy()

        if w > 10 and h > 10:
            self.on_selected(x, y, w, h)
