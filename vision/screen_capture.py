# vision/screen_capture.py

import numpy as np
import mss
import cv2 # For converting color format
from typing import Optional, Tuple

# REMOVE the global sct instance:
# sct = mss.mss() # <--- REMOVE THIS LINE

def capture(region: Optional[Tuple[int, int, int, int]] = None) -> Optional[np.ndarray]:
    """
    Captures the screen or a specific region.

    Args:
        region: Optional tuple (left, top, width, height) defining the
                capture area. If None, captures the primary monitor.

    Returns:
        A NumPy array representing the captured image in BGR format (compatible with OpenCV),
        or None if capture fails.
    """
    try:
        # --- Create mss instance INSIDE the function ---
        with mss.mss() as sct: # Use context manager for cleanup
            if region:
                # Ensure region values are integers
                monitor = {
                    "top": int(region[1]),
                    "left": int(region[0]),
                    "width": int(region[2]),
                    "height": int(region[3])
                }
                if monitor["width"] <= 0 or monitor["height"] <= 0:
                     print(f"Error: Invalid capture region dimensions: {monitor}")
                     return None
            else:
                # Capture primary monitor by default if no region specified
                # mss.monitors[0] is the virtual screen bounding all monitors
                # mss.monitors[1] is the primary monitor
                if len(sct.monitors) > 1:
                    monitor = sct.monitors[1]
                elif len(sct.monitors) == 1: # Only the virtual screen exists? Use it.
                     monitor = sct.monitors[0]
                else:
                     print("Error: No monitors found by mss.")
                     return None


            # Grab the data
            sct_img = sct.grab(monitor)

            # Convert to NumPy array
            img = np.array(sct_img)

            # Convert BGRA to BGR for OpenCV processing
            img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

            return img_bgr

    except Exception as e:
        # Provide more context if possible
        print(f"Error during screen capture (Region: {region}): {e}")
        # import traceback
        # traceback.print_exc() # Uncomment for detailed stack trace if needed
        return None

# Example Usage (Keep as is for testing)
if __name__ == '__main__':
    import time
    import os # Make sure os is imported for path check
    print("Capturing full screen in 3 seconds...")
    time.sleep(3)
    full_screen = capture()
    if full_screen is not None:
        print(f"Full screen captured, shape: {full_screen.shape}")
        cv2.imwrite("fullscreen_capture_test.png", full_screen)
        print("Saved as fullscreen_capture_test.png")
    else:
        print("Full screen capture failed.")

    print("\nCapturing region (100, 100, 300, 200) in 3 seconds...")
    time.sleep(3)
    region_capture = capture(region=(100, 100, 300, 200))
    if region_capture is not None:
        print(f"Region captured, shape: {region_capture.shape}")
        cv2.imwrite("region_capture_test.png", region_capture)
        print("Saved as region_capture_test.png")
    else:
        print("Region capture failed.")