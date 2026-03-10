"""COP2273 Autograder v2 — entry point.

Run this file directly:
    python autograder.py

The old monolithic implementation is preserved as autograder_v1.py.
"""

import sys
import tkinter as tk


def main():
    # macOS: set app name in menu bar / Dock
    if sys.platform == "darwin":
        try:
            from Foundation import NSBundle
            bundle = NSBundle.mainBundle()
            info = bundle.localizedInfoDictionary() or bundle.infoDictionary()
            info["CFBundleName"] = "COP2273 Autograder"
        except Exception:
            pass

    root = tk.Tk()

    if sys.platform == "darwin":
        root.tk.call("ttk::style", "theme", "use", "clam")
        try:
            root.tk.call("wm", "attributes", root._w, "-modified", False)
            import tkinter as _tk
            menubar = _tk.Menu(root, name="apple")
            root.configure(menu=menubar)
            root.createcommand("tk::mac::ReopenApplication", root.deiconify)
        except Exception:
            pass

    from ui.app import App
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
