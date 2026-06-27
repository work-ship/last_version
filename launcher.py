from __future__ import annotations

try:
    from Launcher.app import main

    if __name__ == "__main__":
        main()
except Exception as e:
    import sys
    import traceback
    from tkinter import Tk, messagebox

    root = Tk()
    root.withdraw()
    messagebox.showerror(
        "SchoolERP Launcher Error",
        f"Failed to start launcher:\n\n{type(e).__name__}: {str(e)}\n\nCheck the logs folder for details.",
    )
    root.destroy()
    traceback.print_exc()
    sys.exit(1)
