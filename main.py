import ctypes
# Make the app DPI-aware so multi-monitor coordinates are correct
ctypes.windll.shcore.SetProcessDpiAwareness(2)

import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox
import threading
import keyboard
import time
from datetime import datetime

import capture
import ocr_engine
import furigana
from region_selector import RegionSelector, MonitorChooser, load_region, save_region, load_hotkey, save_hotkey


class FuriHelper:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('FuriHelper')
        self.root.geometry('600x700')
        self.root.configure(bg='#1e1e2e')

        # Keep window on top so it stays visible on Monitor B
        self.root.attributes('-topmost', True)

        self.region = load_region()
        self.processing = False
        self.font_size = 14
        self.hotkey = load_hotkey()

        self._build_ui()
        self._start_hotkey_listener()

        if self.region is None:
            self.root.after(500, self._prompt_region_select)

    def _build_ui(self):
        # Title bar
        title_frame = tk.Frame(self.root, bg='#1e1e2e')
        title_frame.pack(fill=tk.X, padx=10, pady=(10, 0))

        title = tk.Label(title_frame, text='FuriHelper',
                         font=('Arial', 18, 'bold'), fg='#cdd6f4', bg='#1e1e2e')
        title.pack(side=tk.LEFT)

        # Buttons
        btn_frame = tk.Frame(self.root, bg='#1e1e2e')
        btn_frame.pack(fill=tk.X, padx=10, pady=5)

        select_btn = tk.Button(btn_frame, text='Select Region',
                               command=self._select_region,
                               bg='#45475a', fg='#cdd6f4',
                               activebackground='#585b70',
                               font=('Arial', 10), relief=tk.FLAT, padx=10, pady=3)
        select_btn.pack(side=tk.LEFT)

        clear_btn = tk.Button(btn_frame, text='Clear Log',
                              command=self._clear_log,
                              bg='#45475a', fg='#cdd6f4',
                              activebackground='#585b70',
                              font=('Arial', 10), relief=tk.FLAT, padx=10, pady=3)
        clear_btn.pack(side=tk.LEFT, padx=(5, 0))

        self.hotkey_btn = tk.Button(btn_frame, text='Set Hotkey',
                                    command=self._set_hotkey,
                                    bg='#45475a', fg='#cdd6f4',
                                    activebackground='#585b70',
                                    font=('Arial', 10), relief=tk.FLAT, padx=10, pady=3)
        self.hotkey_btn.pack(side=tk.LEFT, padx=(5, 0))

        # Hotkey hint
        self.hint = tk.Label(btn_frame, text=f'Press {self.hotkey} to capture',
                             font=('Arial', 9), fg='#6c7086', bg='#1e1e2e')
        self.hint.pack(side=tk.RIGHT)

        # Font size +/- buttons
        minus_btn = tk.Button(btn_frame, text='-',
                              command=self._decrease_font,
                              bg='#45475a', fg='#cdd6f4',
                              activebackground='#585b70',
                              font=('Arial', 10, 'bold'), relief=tk.FLAT,
                              width=2, pady=3)
        minus_btn.pack(side=tk.LEFT, padx=(10, 0))

        self.font_size_label = tk.Label(btn_frame, text=str(self.font_size),
                                        font=('Arial', 9), fg='#6c7086', bg='#1e1e2e',
                                        width=3)
        self.font_size_label.pack(side=tk.LEFT)

        plus_btn = tk.Button(btn_frame, text='+',
                             command=self._increase_font,
                             bg='#45475a', fg='#cdd6f4',
                             activebackground='#585b70',
                             font=('Arial', 10, 'bold'), relief=tk.FLAT,
                             width=2, pady=3)
        plus_btn.pack(side=tk.LEFT)

        # Separator
        sep = tk.Frame(self.root, height=1, bg='#45475a')
        sep.pack(fill=tk.X, padx=10, pady=5)

        # Log area - scrollable canvas for ruby text
        log_frame = tk.Frame(self.root, bg='#313244')
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 5))

        self.log_canvas = tk.Canvas(log_frame, bg='#313244', highlightthickness=0)
        log_scrollbar = tk.Scrollbar(log_frame, orient=tk.VERTICAL,
                                     command=self.log_canvas.yview)
        self.log_canvas.configure(yscrollcommand=log_scrollbar.set)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.log_canvas.bind('<MouseWheel>', lambda e: self.log_canvas.yview_scroll(
            int(-1 * (e.delta / 120)), 'units'))

        self.log_entries = []
        self.canvas_y = 10
        self._resize_timer = None
        self._update_fonts()
        self.log_canvas.bind('<Configure>', self._on_canvas_resize)

        # Status bar (Entry widget so text is selectable/copiable)
        self.status_var = tk.StringVar(value='Standby')
        status_frame = tk.Frame(self.root, bg='#181825')
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        self.status_bar = tk.Entry(status_frame, textvariable=self.status_var,
                                   font=('Arial', 9), fg='#a6adc8', bg='#181825',
                                   readonlybackground='#181825', bd=0,
                                   relief=tk.FLAT, state='readonly')
        self.status_bar.pack(fill=tk.X, padx=10, ipady=3)

        region_status = 'Region set' if self.region else 'No region selected'
        self.status_var.set(f'Standby | {region_status}')

    def _update_fonts(self):
        ruby_size = max(self.font_size // 2, 6)
        self.main_font = tkfont.Font(family='Yu Gothic UI', size=self.font_size)
        self.ruby_font = tkfont.Font(family='Yu Gothic UI', size=ruby_size)
        self.timestamp_font = tkfont.Font(family='Arial', size=9)

    def _increase_font(self):
        self.font_size = min(self.font_size + 2, 40)
        self._update_font_size()

    def _decrease_font(self):
        self.font_size = max(self.font_size - 2, 8)
        self._update_font_size()

    def _update_font_size(self):
        self.font_size_label.configure(text=str(self.font_size))
        self._update_fonts()
        self._redraw_all()

    def _on_canvas_resize(self, event):
        if self._resize_timer:
            self.root.after_cancel(self._resize_timer)
        self._resize_timer = self.root.after(150, self._redraw_all)

    def _redraw_all(self):
        self.log_canvas.delete('all')
        self.canvas_y = 10
        for entry in self.log_entries:
            self._draw_entry(entry['timestamp'], entry['segments'])
        self.log_canvas.configure(
            scrollregion=self.log_canvas.bbox('all') or (0, 0, 0, 0))

    def _draw_entry(self, timestamp, segments):
        canvas = self.log_canvas
        margin = 10

        # Timestamp
        canvas.create_text(margin, self.canvas_y, text=f'[{timestamp}]',
                           anchor='nw', font=self.timestamp_font, fill='#6c7086')
        ts_h = self.timestamp_font.metrics('linespace')
        self.canvas_y += ts_h + 4

        # Ruby text
        self._draw_ruby_text(segments)

        # Separator
        canvas.create_text(margin, self.canvas_y, text='─' * 50,
                           anchor='nw', font=self.timestamp_font, fill='#45475a')
        sep_h = self.timestamp_font.metrics('linespace')
        self.canvas_y += sep_h + 10

    def _draw_ruby_text(self, segments):
        canvas = self.log_canvas
        canvas_width = canvas.winfo_width()
        if canvas_width < 100:
            canvas_width = 560
        margin = 10
        max_x = canvas_width - margin

        main_h = self.main_font.metrics('linespace')
        ruby_h = self.ruby_font.metrics('linespace')
        line_height = ruby_h + 2 + main_h

        x = margin
        line_top = self.canvas_y

        for text, reading in segments:
            text_w = self.main_font.measure(text)
            if reading:
                ruby_w = self.ruby_font.measure(reading)
                seg_w = max(text_w, ruby_w)
            else:
                seg_w = text_w

            # Wrap to next line if needed
            if x + seg_w > max_x and x > margin:
                x = margin
                line_top += line_height + 4

            if reading:
                # Ruby text centered above kanji
                ruby_x = x + (seg_w - ruby_w) // 2
                canvas.create_text(ruby_x, line_top, text=reading, anchor='nw',
                                   font=self.ruby_font, fill='#a6e3a1')
                # Main text centered below ruby
                main_x = x + (seg_w - text_w) // 2
                canvas.create_text(main_x, line_top + ruby_h + 2, text=text,
                                   anchor='nw', font=self.main_font, fill='#cdd6f4')
            else:
                # No ruby, align with main text baseline
                canvas.create_text(x, line_top + ruby_h + 2, text=text,
                                   anchor='nw', font=self.main_font, fill='#cdd6f4')

            x += seg_w

        self.canvas_y = line_top + line_height + 4

    def _start_hotkey_listener(self):
        """Start listening for the configured hotkey in a background thread."""
        keyboard.unhook_all()
        keyboard.add_hotkey(self.hotkey, self._on_hotkey)

    def _set_hotkey(self):
        """Let the user press a key to set as the capture hotkey."""
        self.hotkey_btn.configure(text='Press a key...', bg='#f38ba8')
        self.hint.configure(text='Waiting for key...')

        def on_key(event):
            keyboard.unhook_all()
            self.hotkey = event.name
            save_hotkey(self.hotkey)
            self._start_hotkey_listener()
            self.root.after(0, lambda: self.hotkey_btn.configure(
                text='Set Hotkey', bg='#45475a'))
            self.root.after(0, lambda: self.hint.configure(
                text=f'Press {self.hotkey} to capture'))

        keyboard.on_press(on_key, suppress=False)

    def _on_hotkey(self):
        """Called when the capture hotkey is pressed."""
        if self.processing:
            return
        if self.region is None:
            self.root.after(0, lambda: messagebox.showwarning(
                'No Region', 'Please select a capture region first.'))
            return

        self.processing = True
        self.root.after(0, lambda: self.status_var.set('Capturing...'))

        thread = threading.Thread(target=self._process_capture, daemon=True)
        thread.start()

    def _process_capture(self):
        """Full capture pipeline: screenshot → OCR → furigana → display."""
        try:
            # Small delay to let user release F4 and keep game window focused
            time.sleep(0.1)

            # Step 1: Get foreground window
            self.root.after(0, lambda: self.status_var.set('Detecting window...'))
            window_rect = capture.get_foreground_window_rect()
            if window_rect is None:
                self.root.after(0, lambda: self.status_var.set(
                    'Error: Could not detect foreground window'))
                return

            # Step 2: Capture region
            self.root.after(0, lambda: self.status_var.set('Capturing screenshot...'))
            image = capture.capture_region(window_rect, self.region)

            # Step 3: OCR
            self.root.after(0, lambda: self.status_var.set('Extracting text (OCR)...'))
            text = ocr_engine.extract_text(image)

            if not text:
                self.root.after(0, lambda: self.status_var.set(
                    'No text detected. Try adjusting the region.'))
                return

            # Step 4: Furigana
            self.root.after(0, lambda: self.status_var.set('Adding furigana...'))
            annotated = furigana.annotate(text)

            # Step 5: Display
            self.root.after(0, lambda: self._append_to_log(annotated))
            self.root.after(0, lambda: self.status_var.set('Standby | Region set'))

        except Exception as e:
            err_msg = str(e)
            self.root.after(0, lambda: self.status_var.set(f'Error: {err_msg}'))
        finally:
            self.processing = False

    def _append_to_log(self, segments):
        """Append a new entry to the scrolling log."""
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log_entries.append({'timestamp': timestamp, 'segments': segments})
        self._draw_entry(timestamp, segments)
        self.log_canvas.configure(
            scrollregion=self.log_canvas.bbox('all') or (0, 0, 0, 0))
        self.log_canvas.yview_moveto(1.0)

    def _clear_log(self):
        """Clear all entries from the log."""
        self.log_entries.clear()
        self.log_canvas.delete('all')
        self.canvas_y = 10
        self.log_canvas.configure(scrollregion=(0, 0, 0, 0))

    def _prompt_region_select(self):
        """Prompt user to select a region on first launch."""
        result = messagebox.askyesno(
            'Setup Required',
            'No capture region is saved.\n\n'
            'Would you like to select the text region now?\n\n'
            'Position your game window first, then click Yes.')
        if result:
            self._select_region()

    def _select_region(self):
        """Open the monitor chooser, then the region selector overlay."""
        capture.reset_target_window()

        def on_monitor_chosen(monitor):
            if monitor is None:
                # User cancelled monitor selection
                self.root.attributes('-topmost', True)
                self.status_var.set('Standby | Region selection cancelled')
                return

            self.root.attributes('-topmost', False)
            self.status_var.set('Selecting region... Drag to select, Escape to cancel.')

            def on_selected(x, y, w, h):
                # Convert absolute screen coords to window-relative coords
                window_rect = capture.get_foreground_window_rect()
                if window_rect:
                    win_left, win_top, _, _ = window_rect
                    region = {
                        'x': x - win_left,
                        'y': y - win_top,
                        'width': w,
                        'height': h
                    }
                else:
                    region = {'x': x, 'y': y, 'width': w, 'height': h}

                self.region = region
                save_region(region)
                self.status_var.set('Standby | Region set')
                self.root.attributes('-topmost', True)

            RegionSelector(on_selected, monitor=monitor)

        MonitorChooser(self.root, on_monitor_chosen)

    def run(self):
        self.root.mainloop()


if __name__ == '__main__':
    app = FuriHelper()
    app.run()
