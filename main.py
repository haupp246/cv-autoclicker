# main.py

import sys
import os
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow # Import the window class

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        # Adjust based on whether bundling as onefile or onedir if needed
        base_path = sys._MEIPASS
    except Exception:
        # sys._MEIPASS not defined, so running in development mode
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

def main():
    """Main function to start the application."""
    print("Starting Advanced Auto-Clicker...")
    app = QApplication(sys.argv)

    # You could add setup here (e.g., loading config, setting styles)

    window = MainWindow()
    window.show()

    print("Application event loop starting.")
    exit_code = app.exec()
    print(f"Application exited with code: {exit_code}")
    sys.exit(exit_code)

if __name__ == "__main__":
    main()