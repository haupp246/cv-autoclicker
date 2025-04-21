# system/process_utils.py

import psutil
import sys
import platform
from typing import Optional, Tuple, List # Added List

# Import Windows-specific modules conditionally
if platform.system() == "Windows":
    try:
        import win32process
        import win32gui
        import win32api
        import win32con
        # import pythoncom
    except ImportError:
        print("Warning: pywin32 library not found. Windows-specific features will be disabled.")
        win32process = None; win32gui = None; win32api = None; win32con = None
else:
    win32process = None; win32gui = None; win32api = None; win32con = None

# --- get_running_processes, get_process_name_from_hwnd ---
# --- get_foreground_window_info, is_target_active ---
# --- get_window_under_cursor ---
# (Keep previous implementations of these functions)
def get_running_processes():
    processes = []; # ... (implementation is same) ...
    try:
        for proc in psutil.process_iter(['pid', 'name', 'exe']):
            try:
                pinfo = proc.info; name = pinfo.get('exe') or pinfo.get('name')
                if name and pinfo.get('pid'):
                    if '\\' in name or '/' in name: name = name.split('\\')[-1].split('/')[-1]
                    processes.append((name, pinfo['pid']))
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess): continue
    except Exception as e: print(f"Error getting process list: {e}"); return []
    processes.sort(key=lambda x: x[0].lower()); return processes

def get_process_name_from_hwnd(hwnd):
    if platform.system() != "Windows" or not win32process or not win32gui or not win32api: return None
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd);
        if pid == 0: return None
        handle = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ, False, pid)
        if not handle: return None
        try: proc_name = win32process.QueryFullProcessImageName(handle, 0); return proc_name.split('\\')[-1]
        finally: win32api.CloseHandle(handle)
    except Exception:
        try: return psutil.Process(pid).name() # Fallback
        except (psutil.NoSuchProcess, psutil.AccessDenied): return None
    return None

def get_foreground_window_info():
    if platform.system() != "Windows" or not win32gui: return {"hwnd": None, "pid": None, "process_name": None}
    try:
        hwnd = win32gui.GetForegroundWindow();
        if not hwnd: return {"hwnd": None, "pid": None, "process_name": None}
        _, pid = win32process.GetWindowThreadProcessId(hwnd); process_name = get_process_name_from_hwnd(hwnd)
        return {"hwnd": hwnd, "pid": pid, "process_name": process_name}
    except Exception as e: print(f"Error getting foreground window info: {e}"); return {"hwnd": None, "pid": None, "process_name": None}

def is_target_active(target_process_name):
    if not target_process_name or platform.system() != "Windows" or not win32gui: return not bool(target_process_name)
    info = get_foreground_window_info()
    return info["process_name"] is not None and info["process_name"].lower() == target_process_name.lower()

def get_window_under_cursor():
    if platform.system() != "Windows" or not win32gui: return None
    try: return win32gui.WindowFromPoint(win32gui.GetCursorPos())
    except Exception as e: print(f"Error getting window under cursor: {e}"); return None


# --- REVISED Function ---
def find_window_for_process(target_process_name: str) -> Optional[Tuple[int, Tuple[int, int, int, int]]]:
    """
    Finds the most likely interactable window for the target process name.
    Prioritizes the foreground window if it matches the process.

    Args:
        target_process_name: The executable name (e.g., "notepad.exe"). Case-insensitive.

    Returns:
        A tuple (hwnd, rect) where rect is (left, top, right, bottom) screen coordinates,
        or (None, None) if not found or on error/non-Windows.
    """
    if platform.system() != "Windows" or not win32gui or not win32process or not target_process_name:
        return None, None

    target_process_name_lower = target_process_name.lower()
    found_hwnd = None
    found_rect = None

    # 1. Check if the *current* foreground window belongs to the target process
    try:
        fg_info = get_foreground_window_info()
        if fg_info["process_name"] and fg_info["process_name"].lower() == target_process_name_lower:
            hwnd = fg_info["hwnd"]
            rect = win32gui.GetWindowRect(hwnd)
            # Basic sanity check on rect size
            if rect[2] > rect[0] and rect[3] > rect[1]:
                print(f"Target process '{target_process_name}' is the foreground window. Using HWND: {hwnd}, Rect: {rect}")
                return hwnd, rect
            else:
                 print(f"Foreground window matched process, but rect {rect} seems invalid. Continuing search.")
        else:
            print(f"Foreground window ({fg_info.get('process_name', 'N/A')}) does not match target '{target_process_name}'. Searching all windows.")

    except Exception as e:
        print(f"Error checking foreground window: {e}. Searching all windows.")


    # 2. If foreground doesn't match, find all PIDs for the process name
    target_pids: List[int] = []
    try:
        for proc in psutil.process_iter(['pid', 'name', 'exe']):
            try:
                pinfo = proc.info
                name = pinfo.get('exe') or pinfo.get('name')
                if name:
                    base_name = name.split('\\')[-1].split('/')[-1].lower()
                    if base_name == target_process_name_lower:
                        target_pids.append(pinfo['pid'])
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
    except Exception as e:
         print(f"Error finding PIDs for {target_process_name}: {e}")
         # Continue without PIDs? Might lead to incorrect matches if EnumWindows callback doesn't check process name.
         # Let's return None if we can't even find PIDs.
         return None, None


    if not target_pids:
        print(f"Could not find any running process with name '{target_process_name}'")
        return None, None

    print(f"Found PIDs for '{target_process_name}': {target_pids}. Enumerating windows...")

    # 3. Enumerate windows and find the best match for the PIDs
    windows_found = [] # Store potential matches (hwnd, rect, area)

    def enum_windows_callback(hwnd, lParam):
        # Check if window is visible
        if not win32gui.IsWindowVisible(hwnd):
            return True

        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if pid in target_pids:
                # Check if it has a title (often filters out helper windows)
                # title = win32gui.GetWindowText(hwnd)
                # if not title:
                #     return True # Skip windows without titles? Risky.

                rect = win32gui.GetWindowRect(hwnd)
                # Basic check for valid rect (non-zero size)
                if rect[2] > rect[0] and rect[3] > rect[1]:
                    area = (rect[2] - rect[0]) * (rect[3] - rect[1])
                    print(f"  Found potential window HWND: {hwnd}, PID: {pid}, Rect: {rect}, Area: {area}")
                    windows_found.append((hwnd, rect, area))
                # else:
                #     print(f"  Skipping HWND {hwnd} (PID {pid}) due to invalid rect: {rect}")

        except Exception:
            pass # Ignore errors for specific windows during enumeration
        return True # Continue enumeration

    try:
        win32gui.EnumWindows(enum_windows_callback, None)
    except Exception as e:
        print(f"Error during EnumWindows: {e}")
        # Continue with any windows found before the error

    # 4. Select the best match from the enumerated windows
    if not windows_found:
        print(f"Could not find any suitable visible window for PIDs {target_pids}")
        return None, None

    # Strategy: Choose the largest window among the matches
    windows_found.sort(key=lambda x: x[2], reverse=True) # Sort by area descending
    best_hwnd, best_rect, best_area = windows_found[0]

    print(f"Selected best match: HWND {best_hwnd}, Rect {best_rect}, Area {best_area}")
    return best_hwnd, best_rect