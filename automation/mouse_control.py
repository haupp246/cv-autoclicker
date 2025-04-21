# automation/mouse_control.py

import pyautogui
import time

# Configure PyAutoGUI failsafe (optional but recommended)
pyautogui.FAILSAFE = True # Move mouse to top-left corner to abort
pyautogui.PAUSE = 0.05 # Small pause after each action (helps stability)

def click(x: int, y: int, button: str = 'left', clicks: int = 1, interval: float = 0.1):
    """
    Performs a mouse click at the specified coordinates.

    Args:
        x: The x-coordinate on the screen.
        y: The y-coordinate on the screen.
        button: 'left', 'right', or 'middle'.
        clicks: Number of clicks (1 for single, 2 for double).
        interval: Time interval between clicks for double-clicks (in seconds).
    """
    try:
        print(f"Attempting to click {button} button {clicks} times at ({x}, {y})")
        pyautogui.click(x=x, y=y, clicks=clicks, interval=interval, button=button)
        print(f"Click successful at ({x}, {y})")
    except pyautogui.FailSafeException:
        print("FAILSAFE triggered! Mouse moved to top-left corner.")
        raise # Re-raise so the runner knows execution stopped
    except Exception as e:
        print(f"Error during click at ({x}, {y}): {e}")
        raise # Re-raise for the runner to handle

def move_to(x: int, y: int, duration: float = 0.1):
    """Moves the mouse cursor to the specified coordinates."""
    try:
        pyautogui.moveTo(x, y, duration=duration)
    except pyautogui.FailSafeException:
        print("FAILSAFE triggered during move!")
        raise
    except Exception as e:
        print(f"Error during mouse move to ({x}, {y}): {e}")
        raise

# Add other functions later if needed (drag, scroll, etc.)