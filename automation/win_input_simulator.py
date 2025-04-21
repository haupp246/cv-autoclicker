# automation/win_input_simulator.py

import platform
import time
from typing import Optional, Tuple

# Import Windows-specific modules conditionally
if platform.system() == "Windows":
    try:
        import win32gui
        import win32api
        import win32con
    except ImportError:
        print("Warning: pywin32 library not found. Background simulation will be disabled.")
        win32gui = None; win32api = None; win32con = None
else:
    win32gui = None; win32api = None; win32con = None

def is_simulation_available() -> bool:
    """Checks if necessary modules for background simulation are available."""
    return win32gui is not None and win32api is not None and win32con is not None

def simulate_click(hwnd: int, x: int, y: int, button: str = 'left', clicks: int = 1, delay_ms: int = 50):
    """
    Simulates mouse clicks by sending messages directly to a window handle.

    Args:
        hwnd: The target window handle (HWND).
        x: The x-coordinate relative to the window's client area.
        y: The y-coordinate relative to the window's client area.
        button: 'left', 'right', or 'middle'.
        clicks: Number of clicks (1 or 2).
        delay_ms: Delay between down and up messages in milliseconds.
    """
    if not is_simulation_available():
        raise RuntimeError("Cannot simulate click: pywin32 library not installed or not on Windows.")
    if not hwnd or not win32gui.IsWindow(hwnd): # Check if HWND is valid
         raise ValueError(f"Invalid window handle (HWND: {hwnd}) provided for simulation.")

    # Convert relative coordinates to lParam format
    # MAKELONG packs the x (low-order word) and y (high-order word)
    lParam = win32api.MAKELONG(x, y)
    print(f"Simulating {button} {clicks}x click at client coords ({x},{y}) on HWND {hwnd}, lParam={lParam}")

    # Map button string to Windows message constants
    if button == 'left':
        down_message = win32con.WM_LBUTTONDOWN
        up_message = win32con.WM_LBUTTONUP
        # wParam for mouse messages often indicates key states (Shift, Ctrl)
        # MK_LBUTTON indicates the left button is down during the event
        wparam_down = win32con.MK_LBUTTON
        wparam_up = 0 # No button state for UP message usually needed
    elif button == 'right':
        down_message = win32con.WM_RBUTTONDOWN
        up_message = win32con.WM_RBUTTONUP
        wparam_down = win32con.MK_RBUTTON
        wparam_up = 0
    elif button == 'middle':
        down_message = win32con.WM_MBUTTONDOWN
        up_message = win32con.WM_MBUTTONUP
        wparam_down = win32con.MK_MBUTTON
        wparam_up = 0
    else:
        raise ValueError(f"Unsupported button type: {button}")

    try:
        for _ in range(clicks):
            # PostMessage is generally preferred for automation
            win32api.PostMessage(hwnd, down_message, wparam_down, lParam)
            time.sleep(delay_ms / 1000.0) # Wait between down and up
            win32api.PostMessage(hwnd, up_message, wparam_up, lParam)
            if clicks > 1:
                 time.sleep(delay_ms / 1000.0) # Wait between multiple clicks if needed

        print(f"Posted {button} click messages to HWND {hwnd}")

    except Exception as e:
        # This might catch errors if the HWND becomes invalid between checks and posting
        print(f"Error posting click messages to HWND {hwnd}: {e}")
        raise RuntimeError(f"Failed to simulate click on HWND {hwnd}: {e}")


# --- Helper to convert screen coords to client coords ---
def screen_to_client(hwnd: int, screen_x: int, screen_y: int) -> Optional[Tuple[int, int]]:
    """Converts absolute screen coordinates to client coordinates for a given window."""
    if not is_simulation_available(): return None
    if not hwnd or not win32gui.IsWindow(hwnd): return None

    try:
        # ScreenToClient expects a point tuple or list
        client_x, client_y = win32gui.ScreenToClient(hwnd, (screen_x, screen_y))
        return client_x, client_y
    except Exception as e:
        print(f"Error converting screen coords ({screen_x},{screen_y}) to client for HWND {hwnd}: {e}")
        return None

# Example Usage (for testing - hard to test directly without a target HWND)
if __name__ == '__main__':
    if is_simulation_available():
        print("Simulation available (pywin32 found).")
        # Find Notepad window (example)
        hwnd = win32gui.FindWindow(None, "Untitled - Notepad") # Or the actual title
        if hwnd:
            print(f"Found Notepad HWND: {hwnd}")
            print("Attempting to simulate click at (50, 50) client coords in 3 seconds...")
            time.sleep(3)
            try:
                # Get client coords for screen coords (100, 100) relative to Notepad
                client_coords = screen_to_client(hwnd, 100, 100)
                if client_coords:
                     print(f"Screen (100,100) maps to Client {client_coords}")

                # Simulate click inside client area
                simulate_click(hwnd, 50, 50, button='left', clicks=1)
                print("Simulated click sent.")
                time.sleep(1)
                print("Attempting double click...")
                simulate_click(hwnd, 50, 50, button='left', clicks=2)
                print("Simulated double click sent.")

            except Exception as e:
                print(f"Error during simulation test: {e}")
        else:
            print("Could not find Notepad window for testing.")
    else:
        print("Simulation not available.")