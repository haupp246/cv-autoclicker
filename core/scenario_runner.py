# core/scenario_runner.py

import time
import os
import platform
from PyQt6.QtCore import QThread, pyqtSignal
from typing import Optional, Tuple, List

from core.scenario import (
    Scenario, Action, ACTION_CLICK, ACTION_WAIT, ACTION_WAIT_FOR_OBJECT,
    ACTION_IF_OBJECT_FOUND, ACTION_END_IF, CLICK_TARGET_FOUND_OBJECT,
    ACTION_LOOP_START, ACTION_LOOP_END, ACTION_CHECK_OBJECT_BREAK_LOOP
)
from system.process_utils import find_window_for_process, is_target_active
from automation import mouse_control
from vision import object_detector, screen_capture


class InterruptedError(Exception):
    pass


class LoopError(Exception):
    pass


class ScenarioRunner(QThread):
    """Executes a scenario in a separate thread."""
    status_update = pyqtSignal(str)
    finished = pyqtSignal()
    error_occurred = pyqtSignal(str)
    action_started = pyqtSignal(int)
    action_finished = pyqtSignal(int)
    # x, y, w, h, confidence, template_name
    object_detected_at = pyqtSignal(int, int, int, int, float, str)
    click_target_calculated = pyqtSignal(int, int)
    # current_rep, total_reps (0 for infinite)
    repetition_update = pyqtSignal(int, int)
    request_hide_overlay = pyqtSignal()
    request_show_overlay = pyqtSignal()

    # --- Corrected __init__ signature ---
    def __init__(self, scenario: Scenario, repetitions: int, parent=None):
        super().__init__(parent)
        self.scenario = scenario
        # Ensure repetitions is non-negative
        # Store global repetitions (0 for infinite)
        self.repetitions = max(0, repetitions)
        self._is_running = False
        self._current_action_index = 0
        self._skip_until_endif_level = 0
        self._last_found_object_coords: Optional[Tuple[int,
                                                       int, int, int]] = None
        self._last_condition_met = False
        self._loop_stack: List[Tuple[int, int]] = []
        self._break_loop_requested = False

    def run(self):
        """The main execution loop for the scenario, including global repetitions."""
        self._is_running = True
        action_count = len(self.scenario.actions)
        print(
            f"Starting scenario '{self.scenario.scenario_name}' with {action_count} actions, Repetitions: {'Infinite' if self.repetitions == 0 else self.repetitions}.")

        current_repetition = 0
        # --- Outer loop for global repetitions ---
        while self._is_running:
            current_repetition += 1
            if self.repetitions > 0 and current_repetition > self.repetitions:
                print(f"Finished {self.repetitions} repetitions.")
                break  # Finished all requested repetitions

            print(
                f"\n--- Starting Repetition {current_repetition}/{'Infinite' if self.repetitions == 0 else self.repetitions} ---")
            self.repetition_update.emit(current_repetition, self.repetitions)

            # --- Reset state for this repetition ---
            self._current_action_index = 0
            self._skip_until_endif_level = 0
            self._last_found_object_coords = None
            self._loop_stack = []
            self._last_condition_met = False
            self._break_loop_requested = False

            # --- Inner loop for actions ---
            while 0 <= self._current_action_index < action_count and self._is_running:
                action = self.scenario.actions[self._current_action_index]
                action_display_num = self._current_action_index + 1
                jump_to_index = -1

                # --- Handle Block Endings ---
                if action.type == ACTION_END_IF:
                    self.action_started.emit(self._current_action_index)
                    if self._skip_until_endif_level > 0:
                        self._skip_until_endif_level -= 1
                        print(
                            f"END_IF reached, decreasing skip level to {self._skip_until_endif_level}")
                    else:
                        print("END_IF reached (not skipping)")
                    self.action_finished.emit(self._current_action_index)
                    self._current_action_index += 1
                    continue
                elif action.type == ACTION_LOOP_END:
                    self.action_started.emit(self._current_action_index)
                    try:
                        if self._break_loop_requested:
                            print("LOOP END: Breaking loop due to previous request.")
                            if not self._loop_stack:
                                raise LoopError(
                                    "Attempted to break loop, but loop stack is empty.")
                            self._loop_stack.pop()
                            self._break_loop_requested = False
                            jump_to_index = -1
                        else:
                            jump_to_index = self._handle_loop_end(action)
                    except Exception as e:
                        error_msg = f"Error on action {action_display_num} ({action.type}): {e}"
                        print(error_msg)
                        self.error_occurred.emit(error_msg)
                        self._is_running = False
                        break
                    self.action_finished.emit(self._current_action_index)
                    if jump_to_index >= 0:
                        self._current_action_index = jump_to_index
                        continue
                    else:
                        self._current_action_index += 1
                        continue

                # --- Check Skipping ---
                if self._skip_until_endif_level > 0:
                    print(
                        f"Skipping action {action_display_num} ({action.type}) due to unmet IF condition.")
                    if action.type in [ACTION_IF_OBJECT_FOUND, ACTION_LOOP_START]:
                        self._skip_until_endif_level += 1
                        print(
                            f"Nested {action.type} found while skipping, increasing skip level to {self._skip_until_endif_level}")
                    self.action_started.emit(self._current_action_index)
                    self.action_finished.emit(self._current_action_index)
                    self._current_action_index += 1
                    continue

                # --- Execute Action ---
                # self.status_update.emit(f"Rep {current_repetition}, Action {action_display_num}/{action_count}: {action.type}") # Can be too noisy
                self.action_started.emit(self._current_action_index)
                print(
                    f"Rep {current_repetition}, Executing action {action_display_num}: {action.type} - Details: {action.details}")

                try:
                    # --- Target Focus Check ---
                    interactive_actions = [ACTION_CLICK, ACTION_WAIT_FOR_OBJECT,
                                           ACTION_IF_OBJECT_FOUND, ACTION_CHECK_OBJECT_BREAK_LOOP]
                    if action.type in interactive_actions:
                        if self.scenario.require_focus and self.scenario.target_process_name:
                            if not is_target_active(self.scenario.target_process_name):
                                status_msg = f"Rep {current_repetition}: Waiting for target app '{self.scenario.target_process_name}'..."
                                print(status_msg)
                                self.status_update.emit(status_msg)
                                while not is_target_active(self.scenario.target_process_name) and self._is_running:
                                    time.sleep(0.5)
                                if not self._is_running:
                                    print(
                                        "Scenario stopped while waiting for target app.")
                                    break
                                print("Target app is active. Resuming...")

                    # --- Reset condition flag before IF checks ---
                    if action.type in [ACTION_IF_OBJECT_FOUND]:
                        self._last_condition_met = False

                    # --- Execute Specific Action Handler ---
                    if action.type == ACTION_CLICK:
                        abs_x, abs_y = self._calculate_click_coords(
                            action)  # Calculate first
                        if abs_x is not None and abs_y is not None:
                            print(
                                f"--- CLICK DEBUG: Final Absolute Coords: ({abs_x}, {abs_y}) ---")

                            # --- Emit signal for overlay FIRST ---
                            self.click_target_calculated.emit(abs_x, abs_y)

                            # --- Hide/Show Overlay Workaround ---
                            self.request_hide_overlay.emit()
                            self.msleep(30)  # Delay for hide + target readiness

                            if self._is_running:
                                try:
                                    mouse_control.click(x=abs_x, y=abs_y, button=action.details.get(
                                        "button", "left"), clicks=2 if action.details.get("click_type") == "double" else 1)
                                finally:
                                    self.msleep(10)
                                    self.request_show_overlay.emit()  # Ensure shown
                            else:
                                self.request_show_overlay.emit()  # Ensure shown if stopped
                                raise InterruptedError(
                                    "Stopped during pre-click delay.")
                        else:
                            raise RuntimeError(
                                "Failed to determine click coordinates before clicking.")
                    elif action.type == ACTION_WAIT:
                        self._handle_wait(action)
                    elif action.type == ACTION_WAIT_FOR_OBJECT:
                        self._handle_wait_for_object(action)
                    elif action.type == ACTION_IF_OBJECT_FOUND:
                        self._handle_if_object_found(action)
                    elif action.type == ACTION_LOOP_START:
                        self._handle_loop_start(action)
                    elif action.type == ACTION_CHECK_OBJECT_BREAK_LOOP:
                        self._handle_check_object_break_loop(action)
                    else:
                        print(
                            f"Warning: Action type '{action.type}' not implemented yet. Skipping.")

                    self.action_finished.emit(self._current_action_index)

                    # --- Check if break was requested ---
                    if self._break_loop_requested:
                        if not self._loop_stack:
                            print(
                                "Warning: Break requested but loop stack is empty.")
                            self._break_loop_requested = False
                            self._current_action_index += 1
                        else:
                            found_loop_end_index = -1
                            temp_index = self._current_action_index + 1
                            nesting_level = 0
                            while temp_index < action_count:
                                a_type = self.scenario.actions[temp_index].type
                                if a_type == ACTION_LOOP_START:
                                    nesting_level += 1
                                elif a_type == ACTION_LOOP_END:
                                    if nesting_level == 0:
                                        found_loop_end_index = temp_index
                                        break
                                    else:
                                        nesting_level -= 1
                                temp_index += 1
                            if found_loop_end_index != -1:
                                print(
                                    f"Break requested, jumping to LOOP_END at index {found_loop_end_index}")
                                self._current_action_index = found_loop_end_index
                            else:
                                print(
                                    "Warning: Break requested but matching LOOP_END not found.")
                                self._break_loop_requested = False
                                self._current_action_index += 1
                    else:
                        self._current_action_index += 1  # Normal progression

                except InterruptedError:
                    print("Scenario stopped during action.")
                    self.status_update.emit("Scenario stopped.")
                    self._is_running = False
                    break
                except Exception as e:
                    error_msg = f"Error on action {action_display_num} ({action.type}): {e}"
                    print(error_msg)
                    self.error_occurred.emit(error_msg)
                    self._is_running = False
                    break

                if not self._is_running:
                    print("Stop requested between actions.")
                    break
            # --- End of inner action loop ---

            if not self._is_running:
                break  # Break outer loop if inner loop was stopped

        # --- Outer loop finished ---
        if self._is_running:  # If not stopped by error or request
            if self._loop_stack:
                print("Warning: Scenario finished with unterminated loops on stack.")
                self.error_occurred.emit(
                    "Scenario finished with unterminated LOOP block(s).")
            elif self._skip_until_endif_level > 0:
                print("Warning: Scenario finished with unterminated IF blocks.")
                self.error_occurred.emit(
                    "Scenario finished with unterminated IF block(s).")
            else:
                print(
                    f"Scenario '{self.scenario.scenario_name}' finished all repetitions.")
                self.status_update.emit("Scenario finished.")
                self.finished.emit()
        self._is_running = False

    def stop(self):
        print("Stop signal received by ScenarioRunner.")
        self._is_running = False

    def _get_search_region(self, action_region: Optional[Tuple[int, int, int, int]]) -> Optional[Tuple[int, int, int, int]]:
        if action_region:
            print(f"Using specified search region: {action_region}")
            return action_region
        if self.scenario.target_process_name and platform.system() == "Windows":
            print(
                f"No region specified, attempting to use target window '{self.scenario.target_process_name}'...")
            hwnd, rect = find_window_for_process(
                self.scenario.target_process_name)
            if rect:
                region = (rect[0], rect[1], rect[2] -
                          rect[0], rect[3] - rect[1])
                if region[2] > 0 and region[3] > 0:
                    print(
                        f"Using target window rect as search region: {region}")
                    return region
                else:
                    print(
                        f"Warning: Target window rect has invalid size: {region}. Searching full screen.")
                    return None
            else:
                print(
                    f"Warning: Could not find target window '{self.scenario.target_process_name}'. Searching full screen.")
                return None
        else:
            print(
                "No region specified and no target window usable. Searching full screen.")
            return None

    def _handle_wait(self, action: Action):
        duration_ms = action.details.get("duration_ms", 1000)
        duration_s = duration_ms / 1000.0
        print(f"Waiting for {duration_s:.2f} seconds...")
        end_time = time.time() + duration_s
        while time.time() < end_time and self._is_running:
            sleep_interval = min(0.1, end_time - time.time())
            time.sleep(sleep_interval) if sleep_interval > 0 else None
        if not self._is_running:
            print("Wait interrupted.")
            raise InterruptedError("Stopped during wait.")
        print("Wait finished.")

    def _calculate_click_coords(self, action: Action) -> Tuple[Optional[int], Optional[int]]:
        pos_name = action.details.get("position_name")
        offset_x = action.details.get("offset_x", 0)
        offset_y = action.details.get("offset_y", 0)
        absolute_x: Optional[int] = None
        absolute_y: Optional[int] = None
        print(f"--- CLICK COORD DEBUG: Action Details: {action.details} ---")

        if pos_name == CLICK_TARGET_FOUND_OBJECT:
            print("--- CLICK COORD DEBUG: Target is Found Object ---")
            if self._last_found_object_coords is None:
                raise ValueError(
                    "CLICK targets found object, but no object found previously.")
            fx, fy, fw, fh = self._last_found_object_coords
            center_x = fx + fw // 2
            center_y = fy + fh // 2
            absolute_x = center_x + offset_x
            absolute_y = center_y + offset_y
            print(
                f"--- CLICK COORD DEBUG: Found Object Rect (Screen): ({fx},{fy},{fw},{fh}) ---")
            print(
                f"--- CLICK COORD DEBUG: Found Object Center (Screen): ({center_x},{center_y}) ---")
            print(
                f"--- CLICK COORD DEBUG: Offset: ({offset_x},{offset_y}) ---")
        elif pos_name:
            print(
                f"--- CLICK COORD DEBUG: Target is Position '{pos_name}' ---")
            if not self.scenario.target_process_name:
                raise ValueError(
                    "Cannot perform relative CLICK without target app.")
            position = self.scenario.get_position_by_name(pos_name)
            if not position:
                raise ValueError(f"Position '{pos_name}' not found.")
            print(
                f"--- CLICK COORD DEBUG: Finding window for '{self.scenario.target_process_name}'... ---")
            hwnd, rect = find_window_for_process(
                self.scenario.target_process_name)
            if not hwnd or not rect:
                raise RuntimeError(
                    f"Target window for '{self.scenario.target_process_name}' not found.")
            window_x, window_y = rect[0], rect[1]
            print(
                f"--- CLICK COORD DEBUG: Target window Rect (Screen): {rect} ---")
            print(
                f"--- CLICK COORD DEBUG: Target window TopLeft (Screen): ({window_x}, {window_y}) ---")
            print(
                f"--- CLICK COORD DEBUG: Position Relative Coords: ({position.relative_x},{position.relative_y}) ---")
            absolute_x = window_x + position.relative_x
            absolute_y = window_y + position.relative_y
        else:
            raise ValueError("CLICK action has invalid target.")

        print(
            f"--- CLICK COORD DEBUG: Calculated Absolute Coords: ({absolute_x}, {absolute_y}) ---")
        return absolute_x, absolute_y

    def _handle_click(self, action: Action):
        pass  # Calculation and click moved to run loop

    def _handle_wait_for_object(self, action: Action):
        template_path = action.details.get("template_path")
        confidence = action.details.get("confidence", 0.8)
        action_region = action.details.get("region")
        timeout_ms = action.details.get("timeout_ms")
        if not template_path or not os.path.exists(template_path):
            raise FileNotFoundError(
                f"Template image path invalid or not found: '{template_path}'")
        search_region = self._get_search_region(action_region)
        template_filename = os.path.basename(template_path)
        print(
            f"Waiting for object '{template_filename}' (Conf: {confidence:.2f})... Region: {search_region}")
        self.status_update.emit(f"Waiting for object: {template_filename}...")
        start_time = time.time()
        timeout_s = (timeout_ms / 1000.0) if timeout_ms else None
        check_interval = 0.3
        self._last_found_object_coords = None
        while self._is_running:
            if timeout_s is not None and (time.time() - start_time) > timeout_s:
                print(
                    f"Timeout reached while waiting for object '{template_filename}'. Proceeding.")
                self.status_update.emit(
                    f"Timeout waiting for '{template_filename}'.")
                self._last_found_object_coords = None
                return
            match_result = object_detector.find_template(
                template_path=template_path, region=search_region, threshold=confidence)
            if match_result:
                x, y, w, h, conf = match_result
                print(
                    f"Object '{template_filename}' found at screen coords ({x},{y}) with confidence {conf:.4f}.")
                self.status_update.emit(f"Object '{template_filename}' found.")
                self._last_found_object_coords = (x, y, w, h)
                self.object_detected_at.emit(
                    x, y, w, h, conf, template_filename)
                return
            wait_end_time = time.time() + check_interval
            while time.time() < wait_end_time and self._is_running:
                sleep_chunk = min(0.1, wait_end_time - time.time())
                time.sleep(sleep_chunk) if sleep_chunk > 0 else None
        if not self._is_running:
            print("Wait for object interrupted.")
            raise InterruptedError("Stopped while waiting for object.")

    def _handle_if_object_found(self, action: Action):
        template_path = action.details.get("template_path")
        confidence = action.details.get("confidence", 0.8)
        action_region = action.details.get("region")
        if not template_path or not os.path.exists(template_path):
            raise FileNotFoundError(
                f"Template image path invalid or not found: '{template_path}'")
        search_region = self._get_search_region(action_region)
        template_filename = os.path.basename(template_path)
        print(
            f"Checking IF object '{template_filename}' found (Conf: {confidence:.2f})... Region: {search_region}")
        self._last_found_object_coords = None
        self._last_condition_met = False
        match_result = object_detector.find_template(
            template_path=template_path, region=search_region, threshold=confidence)
        if match_result:
            x, y, w, h, conf = match_result
            print(
                f"IF condition MET: Object found at screen coords ({x},{y}), confidence {conf:.4f}.")
            self._last_found_object_coords = (x, y, w, h)
            self._last_condition_met = True
            self.object_detected_at.emit(x, y, w, h, conf, template_filename)
        else:
            print("IF condition NOT MET: Object not found.")
            self._last_condition_met = False
            self._skip_until_endif_level += 1
            print(
                f"Skipping until END_IF level {self._skip_until_endif_level} reached.")

    def _handle_loop_start(self, action: Action):
        iterations = action.details.get("iterations", 1)
        if iterations < 0:
            raise ValueError("LOOP iterations cannot be negative.")
        iterations_remaining = -1 if iterations == 0 else iterations
        loop_start_index = self._current_action_index
        self._loop_stack.append((loop_start_index, iterations_remaining))
        print(
            f"LOOP START: {iterations if iterations > 0 else 'Infinite'} iterations. Stack: {self._loop_stack}")

    def _handle_loop_end(self, action: Action) -> int:
        if not self._loop_stack:
            raise LoopError(
                "Encountered LOOP_END without matching LOOP_START.")
        start_index, iterations_remaining = self._loop_stack[-1]
        break_condition = action.details.get("break_condition", "none")

        if break_condition == "last_if_success" and self._last_condition_met:
            print("LOOP END: Breaking loop because 'last_if_success' condition met.")
            self._loop_stack.pop()
            self._last_condition_met = False
            return -1

        self._last_condition_met = False

        if iterations_remaining == -1:
            print("LOOP END: Infinite loop, jumping back.")
            return start_index + 1
        iterations_remaining -= 1
        print(
            f"LOOP END: Decrementing count. Remaining: {iterations_remaining}")
        if iterations_remaining > 0:
            self._loop_stack[-1] = (start_index, iterations_remaining)
            print("Loop continues, jumping back.")
            return start_index + 1
        else:
            self._loop_stack.pop()
            print(f"Loop finished. Popping stack. Stack: {self._loop_stack}")
            return -1

    def _handle_check_object_break_loop(self, action: Action):
        template_path = action.details.get("template_path")
        confidence = action.details.get("confidence", 0.8)
        action_region = action.details.get("region")
        if not template_path or not os.path.exists(template_path):
            raise FileNotFoundError(
                f"Template image path invalid or not found: '{template_path}'")
        search_region = self._get_search_region(action_region)
        template_filename = os.path.basename(template_path)
        print(
            f"Checking if object '{template_filename}' found to break loop (Conf: {confidence:.2f})... Region: {search_region}")
        self._last_found_object_coords = None
        match_result = object_detector.find_template(
            template_path=template_path, region=search_region, threshold=confidence)
        if match_result:
            x, y, w, h, conf = match_result
            print(
                f"Object found at ({x},{y}), confidence {conf:.4f}. Requesting loop break.")
            self.status_update.emit(
                f"Object '{template_filename}' found, breaking loop.")
            self._last_found_object_coords = (x, y, w, h)
            self.object_detected_at.emit(x, y, w, h, conf, template_filename)
            self._break_loop_requested = True
        else:
            print("Object not found, loop continues.")
            self._break_loop_requested = False
