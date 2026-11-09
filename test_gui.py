import time
import tkinter as tk
import unittest
from unittest.mock import patch
import gui


class AsyncErrors(unittest.TestCase):
    def test_failed_operation_releases_controls(self):
        window = tk.Tk(); window.withdraw()
        try:
            with patch.object(gui.service, "load_game", return_value=""):
                app = gui.Application(window)
            app.game.set("fixture")
            with patch.object(gui.service, "perform", side_effect=ValueError("operation failed")):
                app.start("install"); self.assertTrue(app.busy)
                deadline = time.monotonic() + 3
                while app.busy and time.monotonic() < deadline:
                    window.update(); time.sleep(.02)
            self.assertFalse(app.busy)
            self.assertIn("operation failed", app.message.get())
            self.assertTrue(all(str(widget["state"]) == "normal" for widget in app.inputs))
        finally:
            window.destroy()


if __name__ == "__main__":
    unittest.main()
