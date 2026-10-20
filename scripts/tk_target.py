"""Test target window: a Tk Text box that mirrors its content to a file. Usage: tk_target.py <out> <title>"""
import sys, tkinter as tk
out, title = sys.argv[1], sys.argv[2]
root = tk.Tk(); root.title(title); root.geometry("500x300+200+200")
t = tk.Text(root, wrap="word"); t.pack(fill="both", expand=True); t.focus_set()
last = [None]
def dump():
    s = t.get("1.0", "end-1c")
    if s != last[0]:
        open(out, "w", encoding="utf-8", newline="").write(s); last[0] = s
    root.after(80, dump)
open(out, "w").close(); dump(); root.mainloop()
