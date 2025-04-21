# vision/object_detector.py

import cv2
import numpy as np
from typing import Optional, Tuple, List
import imutils # Ensure installed: pip install imutils
import os

# Import screen capture function relative to this file's location
from . import screen_capture

def find_template(
    template_path: str,
    region: Optional[Tuple[int, int, int, int]] = None,
    threshold: float = 0.8,
    method=cv2.TM_CCOEFF_NORMED,
    use_grayscale: bool = True, # Default to grayscale
    use_multiscale: bool = True, # Default to multi-scale
    scale_range: Tuple[float, float] = (0.7, 1.3), # Scale range (e.g., 70% to 130%)
    scale_steps: int = 7 # Number of scales to check (odd number recommended)
) -> Optional[Tuple[int, int, int, int, float]]:
    """
    Finds a template image using template matching.
    Optionally uses grayscale and multi-scale searching.

    Args:
        template_path: Path to the template image file.
        region: Optional screen region (left, top, width, height) to search within.
                If None, searches the primary monitor.
        threshold: Minimum matching confidence required.
        method: OpenCV template matching method.
        use_grayscale: Convert images to grayscale before matching.
        use_multiscale: Perform matching at different template scales.
        scale_range: Tuple (min_scale, max_scale) for multi-scale search.
        scale_steps: Number of scales to check within the range.

    Returns:
        A tuple (x, y, w, h, confidence) of the best match found above the
        threshold across all scales, or None if no match found.
        Coordinates are absolute screen coordinates.
    """
    if not os.path.exists(template_path):
        print(f"Error: Template file not found at '{template_path}'")
        return None

    try:
        # --- Load Template ---
        img_mode = cv2.IMREAD_GRAYSCALE if use_grayscale else cv2.IMREAD_COLOR
        template_orig = cv2.imread(template_path, img_mode)
        if template_orig is None:
            print(f"Error: Could not load template image at '{template_path}' (invalid format or permissions?).")
            return None
        (orig_h, orig_w) = template_orig.shape[:2]
        if orig_h == 0 or orig_w == 0:
             print(f"Error: Template image '{template_path}' has zero dimensions.")
             return None

        # --- Capture Screen/Region ---
        haystack_bgr = screen_capture.capture(region)
        if haystack_bgr is None:
            print("Error: Failed to capture screen/region.")
            return None

        # --- Convert Haystack if needed ---
        haystack = cv2.cvtColor(haystack_bgr, cv2.COLOR_BGR2GRAY) if use_grayscale else haystack_bgr
        (haystack_h, haystack_w) = haystack.shape[:2]
        if haystack_h == 0 or haystack_w == 0:
             print("Error: Captured screen/region has zero dimensions.")
             return None


        # --- Multi-Scale Loop (or single pass if disabled) ---
        best_match: Optional[Tuple[int, int, int, int, float]] = None

        if use_multiscale and scale_steps > 1 and scale_range[0] < scale_range[1]:
            scales_to_check = np.linspace(scale_range[0], scale_range[1], scale_steps)
        else:
            scales_to_check = [1.0] # Only check original scale

        for scale in scales_to_check:
            # Resize template (ensure dimensions are valid)
            new_w = int(orig_w * scale)
            new_h = int(orig_h * scale)

            if new_w <= 0 or new_h <= 0: continue
            if new_w > haystack_w or new_h > haystack_h:
                if len(scales_to_check) == 1: print(f"Warning: Template ({new_w}x{new_h}) is larger than search area ({haystack_w}x{haystack_h}).")
                continue

            interpolation = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
            template = cv2.resize(template_orig, (new_w, new_h), interpolation=interpolation)
            (h, w) = template.shape[:2]

            # --- Perform Template Matching ---
            try:
                result = cv2.matchTemplate(haystack, template, method)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            except cv2.error as e:
                 print(f"OpenCV error during matchTemplate at scale {scale:.2f}: {e}")
                 continue

            if method in [cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED]:
                confidence = 1.0 - min_val; top_left = min_loc
            else:
                confidence = max_val; top_left = max_loc

            # --- Update Best Match ---
            if confidence >= threshold:
                if best_match is None or confidence > best_match[4]:
                    match_x_rel = top_left[0]; match_y_rel = top_left[1]
                    match_x_abs = match_x_rel + (region[0] if region else 0)
                    match_y_abs = match_y_rel + (region[1] if region else 0)
                    best_match = (match_x_abs, match_y_abs, w, h, confidence)

        # --- Return Best Match ---
        if best_match:
            print(f"Object found: Conf={best_match[4]:.4f}, Screen Coords=({best_match[0]},{best_match[1]}), Size=({best_match[2]}x{best_match[3]})")
            return best_match
        else:
            return None

    except cv2.error as e:
        print(f"OpenCV Error during template processing: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error during template matching: {e}")
        import traceback
        traceback.print_exc()
        return None

# --- Example Usage ---
if __name__ == '__main__':
    import time
    template_file = "template_test.png" # MAKE SURE THIS FILE EXISTS

    if not os.path.exists(template_file):
        print(f"ERROR: Please create '{template_file}' containing something visible on your screen for testing.")
    else:
        print(f"\nSearching for '{template_file}' on full screen (threshold 0.7)...")
        time.sleep(2)
        match_result = find_template(template_file, threshold=0.7)
        if match_result: print(f"-> SUCCESS: Found.")
        else: print("-> FAILURE: Not Found.")

        print(f"\nSearching for '{template_file}' in region (0, 0, 500, 500) (threshold 0.8)...")
        time.sleep(2)
        match_result_region = find_template(template_file, region=(0, 0, 500, 500), threshold=0.8)
        if match_result_region: print(f"-> SUCCESS: Found.")
        else: print("-> FAILURE: Not Found.")

        print(f"\nSearching (NO MULTISCALE) for '{template_file}' on full screen (threshold 0.7)...")
        time.sleep(2)
        match_result_no_multi = find_template(template_file, threshold=0.7, use_multiscale=False)
        if match_result_no_multi: print(f"-> SUCCESS: Found.")
        else: print("-> FAILURE: Not Found.")