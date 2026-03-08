import ctypes
# Per-Monitor DPI Awareness for multi-monitor setups
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    ctypes.windll.user32.SetProcessDPIAware()

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
        self.root.geometry('600x800')
        self.root.configure(bg='#1e1e2e')

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
        title_frame = tk.Frame(self.root, bg='#1e1e2e')
        title_frame.pack(fill=tk.X, padx=10, pady=(10, 0))
        tk.Label(title_frame, text='FuriHelper', font=('Arial', 18, 'bold'), 
                 fg='#cdd6f4', bg='#1e1e2e').pack(side=tk.LEFT)

        btn_frame = tk.Frame(self.root, bg='#1e1e2e')
        btn_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Button(btn_frame, text='Select Region', command=self._select_region, bg='#45475a', fg='#cdd6f4',
                  activebackground='#585b70', relief=tk.FLAT, padx=10, pady=3).pack(side=tk.LEFT, padx=2)
        
        tk.Button(btn_frame, text='Clear Log', command=self._clear_log, bg='#45475a', fg='#cdd6f4',
                  activebackground='#585b70', relief=tk.FLAT, padx=10, pady=3).pack(side=tk.LEFT, padx=2)

        self.hotkey_btn = tk.Button(btn_frame, text='Set Hotkey', command=self._set_hotkey,
                                    bg='#45475a', fg='#cdd6f4', relief=tk.FLAT, padx=10, pady=3)
        self.hotkey_btn.pack(side=tk.LEFT, padx=2)

        tk.Button(btn_frame, text='-', command=self._decrease_font, bg='#45475a', fg='#cdd6f4', 
                  width=2, relief=tk.FLAT).pack(side=tk.LEFT, padx=(10, 0))
        self.font_size_label = tk.Label(btn_frame, text=str(self.font_size), fg='#6c7086', bg='#1e1e2e', width=3)
        self.font_size_label.pack(side=tk.LEFT)
        tk.Button(btn_frame, text='+', command=self._increase_font, bg='#45475a', fg='#cdd6f4', 
                  width=2, relief=tk.FLAT).pack(side=tk.LEFT)

        self.hint = tk.Label(btn_frame, text=f'Press {self.hotkey} to capture', 
                             font=('Arial', 9), fg='#6c7086', bg='#1e1e2e')
        self.hint.pack(side=tk.RIGHT)

        log_frame = tk.Frame(self.root, bg='#313244')
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 5))

        self.log_canvas = tk.Canvas(log_frame, bg='#313244', highlightthickness=0)
        log_scrollbar = tk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_canvas.yview)
        self.log_canvas.configure(yscrollcommand=log_scrollbar.set)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.log_canvas.bind('<MouseWheel>', lambda e: self.log_canvas.yview_scroll(int(-1 * (e.delta / 120)), 'units'))

        self.log_entries = []
        self.canvas_y = 10
        self._update_fonts()
        self.log_canvas.bind('<Configure>', lambda e: self._redraw_all())

        self.status_var = tk.StringVar(value='Standby')
        status_bar = tk.Entry(self.root, textvariable=self.status_var, font=('Arial', 9), 
                              fg='#a6adc8', bg='#181825', bd=0, state='readonly')
        status_bar.pack(fill=tk.X, side=tk.BOTTOM, ipady=3)

    def _update_fonts(self):
        ruby_size = max(self.font_size // 2, 7)
        self.main_font = tkfont.Font(family='Yu Gothic UI', size=self.font_size)
        self.trans_font = tkfont.Font(family='Microsoft JhengHei', size=self.font_size - 1)
        self.ruby_font = tkfont.Font(family='Yu Gothic UI', size=ruby_size)
        self.timestamp_font = tkfont.Font(family='Arial', size=9)

    def _redraw_all(self):
        self.log_canvas.delete('all')
        self.canvas_y = 10
        for entry in self.log_entries:
            self._draw_entry(entry['timestamp'], entry['data'])
        self.log_canvas.configure(scrollregion=self.log_canvas.bbox('all') or (0, 0, 0, 0))

    def _draw_entry(self, timestamp, data):
        canvas = self.log_canvas
        margin = 10
        segments = data['segments']
        translation = data['translation']

        canvas.create_text(margin, self.canvas_y, text=f'[{timestamp}]', anchor='nw', font=self.timestamp_font, fill='#6c7086')
        self.canvas_y += self.timestamp_font.metrics('linespace') + 4

        self._draw_ruby_text(segments)

        fill_color = '#89b4fa' if translation != "正在翻譯..." else '#fab387'
        canvas_width = canvas.winfo_width() - (margin * 2)
        if canvas_width < 100: canvas_width = 560
        
        t_id = canvas.create_text(margin, self.canvas_y, text=translation, anchor='nw', 
                                  font=self.trans_font, fill=fill_color, width=canvas_width)
        
        bbox = canvas.bbox(t_id)
        self.canvas_y += (bbox[3] - bbox[1]) + 10
        canvas.create_line(margin, self.canvas_y, canvas.winfo_width()-margin, self.canvas_y, fill='#45475a')
        self.canvas_y += 15

    def _draw_ruby_text(self, segments):
        canvas = self.log_canvas
        canvas_width = canvas.winfo_width()
        if canvas_width < 100: canvas_width = 560
        margin = 10
        max_x = canvas_width - margin

        main_h = self.main_font.metrics('linespace')
        ruby_h = self.ruby_font.metrics('linespace')
        line_height = ruby_h + 2 + main_h

        x, line_top = margin, self.canvas_y

        for text, reading in segments:
            text_w = self.main_font.measure(text)
            seg_w = max(text_w, self.ruby_font.measure(reading)) if reading else text_w

            if x + seg_w > max_x and x > margin:
                x = margin
                line_top += line_height + 4

            if reading:
                ruby_w = self.ruby_font.measure(reading)
                canvas.create_text(x + (seg_w-ruby_w)//2, line_top, text=reading, 
                                   anchor='nw', font=self.ruby_font, fill='#a6e3a1')
                canvas.create_text(x + (seg_w-text_w)//2, line_top + ruby_h + 2, text=text,
                                   anchor='nw', font=self.main_font, fill='#cdd6f4')
            else:
                canvas.create_text(x, line_top + ruby_h + 2, text=text, anchor='nw', font=self.main_font, fill='#cdd6f4')
            x += seg_w

        self.canvas_y = line_top + line_height + 4

    def _process_capture(self):
        try:
            time.sleep(0.1)
            window_rect = capture.get_foreground_window_rect()
            if not window_rect: return

            image = capture.capture_region(window_rect, self.region)
            text = ocr_engine.extract_text(image)

            if text:
                clean_text, segments = furigana.get_annotate_only(text)
                data = {'segments': segments, 'translation': "正在翻譯..."}
                self.root.after(0, lambda: self._append_and_translate(data, clean_text))
                self.root.after(0, lambda: self.status_var.set('Standby'))
            else:
                self.root.after(0, lambda: self.status_var.set('No text detected'))
        except Exception as e:
            self.root.after(0, lambda: self.status_var.set(f'Error: {e}'))
        finally:
            self.processing = False

    def _append_and_translate(self, data, clean_text):
        timestamp = datetime.now().strftime('%H:%M:%S')
        entry = {'timestamp': timestamp, 'data': data}
        self.log_entries.append(entry)
        self._redraw_all()
        self.log_canvas.yview_moveto(1.0)

        def fetch():
            real_trans = furigana.get_translation_only(clean_text)
            entry['data']['translation'] = real_trans
            self.root.after(0, self._redraw_all)
            self.root.after(100, lambda: self.log_canvas.yview_moveto(1.0))

        threading.Thread(target=fetch, daemon=True).start()

    def _clear_log(self):
        self.log_entries.clear()
        self._redraw_all()

    def _start_hotkey_listener(self):
        keyboard.unhook_all()
        keyboard.add_hotkey(self.hotkey, self._on_hotkey)

    def _on_hotkey(self):
        if self.processing: return
        if not self.region:
            self.root.after(0, lambda: messagebox.showwarning('No Region', 'Select region first.'))
            return
        self.processing = True
        self.status_var.set('Processing...')
        threading.Thread(target=self._process_capture, daemon=True).start()

    def _set_hotkey(self):
        self.hotkey_btn.configure(text='Press key...', bg='#f38ba8')
        def on_key(event):
            keyboard.unhook_all()
            self.hotkey = event.name
            save_hotkey(self.hotkey)
            self._start_hotkey_listener()
            self.root.after(0, lambda: self.hotkey_btn.configure(text='Set Hotkey', bg='#45475a'))
            self.root.after(0, lambda: self.hint.configure(text=f'Press {self.hotkey} to capture'))
        keyboard.on_press(on_key)

    def _increase_font(self):
        self.font_size = min(self.font_size+2, 40)
        self._update_font_size()

    def _decrease_font(self):
        self.font_size = max(self.font_size-2, 8)
        self._update_font_size()

    def _update_font_size(self):
        self.font_size_label.configure(text=str(self.font_size))
        self._update_fonts()
        self._redraw_all()

    def _prompt_region_select(self):
        if messagebox.askyesno('Setup', 'Select capture region now?'): self._select_region()

    def _select_region(self):
        capture.reset_target_window()
        def chosen(m):
            if not m: return
            self.root.attributes('-topmost', False)
            def selected(x,y,w,h):
                wr = capture.get_foreground_window_rect()
                self.region = {'x':x-wr[0], 'y':y-wr[1], 'width':w, 'height':h} if wr else {'x':x,'y':y,'width':w,'height':h}
                save_region(self.region); self.status_var.set('Region set'); self.root.attributes('-topmost', True)
            RegionSelector(selected, monitor=m)
        MonitorChooser(self.root, chosen)

    def run(self): 
        self.root.mainloop()

if __name__ == '__main__':
    FuriHelper().run()