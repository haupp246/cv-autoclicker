# ui/widgets/left_panel.py

import sys
import platform
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLineEdit, QPushButton,
    QCheckBox, QListWidget, QMessageBox, QInputDialog, QApplication
)
from PyQt6.QtGui import QIcon, QCursor
from PyQt6.QtCore import Qt, pyqtSignal, QTimer

from ui.dialogs.process_dialog import ProcessDialog
from system.process_utils import (
    get_window_under_cursor, get_process_name_from_hwnd,
    get_foreground_window_info, find_window_for_process
)
# Import pynput/pyautogui conditionally for listeners/position
try: from pynput import mouse, keyboard
except ImportError: mouse = None; keyboard = None
try: import pyautogui
except ImportError: pyautogui = None
from typing import List, Optional, Tuple

# Import constants (adjust path if needed, or pass them in)
# Assuming constants are defined in main_window or a shared config module
# For simplicity here, let's redefine them or assume they are passed
ICON_ACTIVE_WINDOW = None; ICON_BROWSE = None; ICON_PICKER = None; ICON_RECORD = None
RECORD_HOTKEY = keyboard.Key.f7 if keyboard else None

class LeftPanelWidget(QWidget):
    """Widget containing Target Application and Position Management sections."""
    # Signals to notify MainWindow of changes that affect the scenario
    target_process_changed = pyqtSignal(str)
    require_focus_changed = pyqtSignal(bool)
    position_added = pyqtSignal(str, int, int) # name, rel_x, rel_y
    # Signal to request status updates in MainWindow
    status_update_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._main_window = parent # Store reference to main window if needed for scenario access/status
        self._mouse_listener = None
        self._keyboard_listener = None
        self._is_picking_mode = False
        self._is_recording_hotkey_active = False

        self._setup_ui()

    def _setup_ui(self):
        """Creates the UI elements for this panel."""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(5, 5, 5, 5)

        # --- Target Application GroupBox ---
        target_app_group = QGroupBox("Target Application (Required for Relative Positions)")
        target_app_layout = QVBoxLayout()
        target_app_controls_layout = QHBoxLayout()

        self.target_process_input = QLineEdit()
        self.target_process_input.setPlaceholderText("e.g., notepad.exe")
        self.target_process_input.textChanged.connect(self._emit_target_process_change) # Emit signal
        target_app_controls_layout.addWidget(self.target_process_input, 1)

        self.get_active_button = QPushButton("Get Active")
        if ICON_ACTIVE_WINDOW: self.get_active_button.setIcon(QIcon(ICON_ACTIVE_WINDOW))
        self.get_active_button.setToolTip("Get the process name of the currently active window")
        self.get_active_button.clicked.connect(self._get_active_window_process)
        if platform.system() != "Windows" or 'win32gui' not in sys.modules:
             self.get_active_button.setEnabled(False); self.get_active_button.setToolTip("Requires Windows")
        target_app_controls_layout.addWidget(self.get_active_button)

        self.browse_button = QPushButton("Browse...")
        if ICON_BROWSE: self.browse_button.setIcon(QIcon(ICON_BROWSE))
        self.browse_button.setToolTip("Browse running processes")
        self.browse_button.clicked.connect(self._browse_processes)
        target_app_controls_layout.addWidget(self.browse_button)

        self.picker_button = QPushButton("Pick")
        if ICON_PICKER: self.picker_button.setIcon(QIcon(ICON_PICKER))
        self.picker_button.setToolTip("Click this, then click on the target application window")
        self.picker_button.clicked.connect(self._toggle_pick_mode)
        if mouse is None or platform.system() != "Windows" or 'win32gui' not in sys.modules:
            self.picker_button.setEnabled(False); self.picker_button.setToolTip("Requires pynput and Windows")
        target_app_controls_layout.addWidget(self.picker_button)

        target_app_layout.addLayout(target_app_controls_layout)

        self.require_focus_checkbox = QCheckBox("Only run when target app is active/focused")
        self.require_focus_checkbox.setToolTip("If checked, actions only execute if the target application's window is in the foreground.")
        self.require_focus_checkbox.stateChanged.connect(self._emit_require_focus_change) # Emit signal
        if platform.system() != "Windows" or 'win32gui' not in sys.modules:
             self.require_focus_checkbox.setEnabled(False); self.require_focus_checkbox.setToolTip("Requires Windows")
        target_app_layout.addWidget(self.require_focus_checkbox)

        target_app_group.setLayout(target_app_layout)
        self.main_layout.addWidget(target_app_group)

        # --- Position Management GroupBox ---
        position_group = QGroupBox("Recorded Positions (Relative to Target Window)")
        position_layout = QVBoxLayout()
        self.position_list_widget = QListWidget()
        self.position_list_widget.setToolTip("List of saved coordinates (Relative X, Relative Y)")
        # Add context menu later
        position_layout.addWidget(self.position_list_widget)

        record_pos_layout = QHBoxLayout()
        hotkey_name = RECORD_HOTKEY._name_ if RECORD_HOTKEY and hasattr(RECORD_HOTKEY, '_name_') else 'N/A'
        self.record_pos_button = QPushButton(f"Enable Recording Hotkey ({hotkey_name})")
        if ICON_RECORD: self.record_pos_button.setIcon(QIcon(ICON_RECORD))
        self.record_pos_button.setToolTip(f"Click to enable listening for the {hotkey_name} key to record mouse position relative to the target window.")
        self.record_pos_button.setCheckable(True)
        self.record_pos_button.toggled.connect(self._toggle_record_hotkey_listener)
        if keyboard is None or pyautogui is None or RECORD_HOTKEY is None or platform.system() != "Windows":
            self.record_pos_button.setEnabled(False); self.record_pos_button.setText("Recording Disabled")
            self.record_pos_button.setToolTip("Relative Position Recording requires pynput, pyautogui, and Windows.")
        record_pos_layout.addWidget(self.record_pos_button)
        record_pos_layout.addStretch()
        position_layout.addLayout(record_pos_layout)
        position_group.setLayout(position_layout)
        self.main_layout.addWidget(position_group)

        self.main_layout.addStretch(1) # Push groups to top

    # --- Methods to update UI from MainWindow ---
    def set_target_process(self, process_name: Optional[str]):
        self.target_process_input.blockSignals(True)
        self.target_process_input.setText(process_name or "")
        self.target_process_input.blockSignals(False)

    def set_require_focus(self, required: bool):
        self.require_focus_checkbox.blockSignals(True)
        self.require_focus_checkbox.setChecked(required)
        self.require_focus_checkbox.blockSignals(False)

    def update_position_list(self, positions: List['Position']): # Use forward reference
        self.position_list_widget.clear()
        for pos in positions:
            display_text = f"{pos.name} (Rel: {pos.relative_x}, {pos.relative_y})"
            self.position_list_widget.addItem(display_text)
            self.position_list_widget.item(self.position_list_widget.count() - 1).setData(Qt.ItemDataRole.UserRole, pos.name)

    def get_position_names(self) -> List[str]:
        """Returns the names of positions currently in the list widget."""
        # This might be better retrieved directly from the scenario in MainWindow,
        # but providing it here for consistency if needed by AddActionDialog if it were moved here.
        names = []
        for i in range(self.position_list_widget.count()):
             item = self.position_list_widget.item(i)
             name = item.data(Qt.ItemDataRole.UserRole)
             if name:
                 names.append(name)
        return names

    def set_record_button_checked(self, checked: bool):
        """Allows MainWindow to sync toolbar action state."""
        self.record_pos_button.setChecked(checked)

    def set_running_state(self, is_running: bool):
        """Disable controls when scenario is running."""
        self.setEnabled(not is_running)

    # --- Signal Emitting Wrappers ---
    def _emit_target_process_change(self, text):
        self.target_process_changed.emit(text.strip())

    def _emit_require_focus_change(self, state):
        self.require_focus_changed.emit(state == Qt.CheckState.Checked.value)

    def _emit_status_update(self, message):
        self.status_update_requested.emit(message)

    # --- Action Handlers (Mostly same logic, but emit signals/status) ---
    def _browse_processes(self):
        print("Browse processes button clicked.")
        dialog = ProcessDialog(self)
        if dialog.exec():
            selected_process = dialog.get_selected_process()
            if selected_process:
                self.target_process_input.setText(selected_process) # Triggers textChanged -> signal
                self._emit_status_update(f"Selected target process: {selected_process}")
                print(f"Selected process: {selected_process}")
        else:
            print("Process selection cancelled.")
            self._emit_status_update("Process selection cancelled.")

    def _get_active_window_process(self):
        if platform.system() != "Windows" or 'win32gui' not in sys.modules:
             self._emit_status_update("Requires Windows and pywin32.")
             return
        self._emit_status_update("Getting active window process...")
        QApplication.processEvents() # Allow UI update
        info = get_foreground_window_info()
        process_name = info.get("process_name")
        if process_name:
            self.target_process_input.setText(process_name) # Triggers textChanged -> signal
            self._emit_status_update(f"Set target to active window process: {process_name}")
            print(f"Active window process: {process_name}")
        else:
            self._emit_status_update("Could not get process name for the active window.")
            print("Failed to get active window process name.")
            QMessageBox.warning(self, "Get Active Window", "Could not determine the process name for the currently active window.")

    def _toggle_pick_mode(self):
        if self._is_recording_hotkey_active:
            self._emit_status_update("Cannot pick application while recording hotkey is active.")
            return
        if not mouse or platform.system() != "Windows" or 'win32gui' not in sys.modules:
             QMessageBox.critical(self, "Error", "Picker Tool requires pynput library and Windows.")
             return
        if self._is_picking_mode:
            self._stop_picking_mode()
        else:
            self._start_picking_mode()

    def _start_picking_mode(self):
        if self._is_picking_mode: return
        print("Starting picking mode...")
        self._is_picking_mode = True
        self._emit_status_update("Picking Mode: Click on the target application window...")
        self.picker_button.setText("Cancel Pick")
        QApplication.setOverrideCursor(Qt.CursorShape.CrossCursor) # Set global cursor
        try:
            def on_click(x, y, button, pressed):
                if pressed and self._is_picking_mode:
                    QTimer.singleShot(0, self._process_pick_click)
                    return False
            self._mouse_listener = mouse.Listener(on_click=on_click)
            self._mouse_listener.start()
            print("Mouse listener started for picking.")
        except Exception as e:
            print(f"Error starting mouse listener: {e}")
            QMessageBox.critical(self, "Error", f"Failed to start mouse listener for picking:\n{e}")
            self._stop_picking_mode()

    def _stop_picking_mode(self):
        if not self._is_picking_mode: return
        print("Stopping picking mode...")
        if self._mouse_listener:
            try: self._mouse_listener.stop(); print("Mouse listener stopped.")
            except Exception as e: print(f"Error stopping mouse listener: {e}")
            self._mouse_listener = None
        self._is_picking_mode = False
        QApplication.restoreOverrideCursor() # Restore global cursor
        self.picker_button.setText("Pick")
        # Check main window status instead of assuming
        # if "Picking Mode:" in self.status_bar.currentMessage():
        #      self._emit_status_update("Ready")

    def _process_pick_click(self):
        print("Processing pick click...")
        QApplication.restoreOverrideCursor() # Restore cursor immediately after click
        if not self._is_picking_mode:
            print("Picking mode was cancelled before click processing."); return
        hwnd = get_window_under_cursor()
        process_name = None
        if hwnd: process_name = get_process_name_from_hwnd(hwnd)
        if process_name:
            self.target_process_input.setText(process_name) # Triggers signal
            self._emit_status_update(f"Picked target process: {process_name}")
            print(f"Picked process: {process_name}")
        else:
            self._emit_status_update("Could not get process name for the picked window.")
            print("Failed to get process name for picked window.")
            QMessageBox.warning(self, "Pick Application", "Could not determine the process name for the clicked window.")
        self._stop_picking_mode() # Ensure stopped state

    def _toggle_record_hotkey_listener(self, checked):
        if self._is_picking_mode:
            self._emit_status_update("Cannot enable recording hotkey while picking application.")
            self.record_pos_button.setChecked(False); return

        # Check if target process is set (needs access to scenario or main window)
        # We'll do this check in MainWindow before calling start/stop
        # target_process = self._main_window.current_scenario.target_process_name # Example access
        # if checked and not target_process:
        #      QMessageBox.warning(self, "Target Required", "Please specify a Target Application.")
        #      self.record_pos_button.setChecked(False); return

        if checked: self._start_record_hotkey_listener()
        else: self._stop_record_hotkey_listener()

    def _start_record_hotkey_listener(self):
        # Logic remains mostly the same, but use _emit_status_update
        if self._is_recording_hotkey_active or not keyboard or not pyautogui or not RECORD_HOTKEY or platform.system() != "Windows": return
        print(f"Starting position recording hotkey ({RECORD_HOTKEY._name_}) listener...")
        self._is_recording_hotkey_active = True
        hotkey_name = RECORD_HOTKEY._name_ if hasattr(RECORD_HOTKEY, '_name_') else 'N/A'
        # Get target process name from input field for status message
        target_process = self.target_process_input.text()
        status_msg = f"Recording Hotkey ({hotkey_name}) Active. Press {hotkey_name} to capture mouse position relative to '{target_process}'."
        self._emit_status_update(status_msg)
        self.record_pos_button.setText(f"Disable Recording Hotkey ({hotkey_name})")
        try:
            def on_press(key):
                if key == RECORD_HOTKEY:
                    print(f"Recording hotkey ({hotkey_name}) pressed.")
                    QTimer.singleShot(0, self._process_record_hotkey_press)
            self._keyboard_listener = keyboard.Listener(on_press=on_press); self._keyboard_listener.start()
            print("Keyboard listener started for recording.")
        except Exception as e:
            print(f"Error starting keyboard listener for recording: {e}"); QMessageBox.critical(self, "Error", f"Failed to start keyboard listener for recording:\n{e}")
            self._stop_record_hotkey_listener()

    def _stop_record_hotkey_listener(self):
        # Logic remains mostly the same, but use _emit_status_update
        if not self._is_recording_hotkey_active: return
        print("Stopping position recording hotkey listener...")
        if self._keyboard_listener:
            try: self._keyboard_listener.stop(); print("Keyboard listener stopped.")
            except Exception as e: print(f"Error stopping keyboard listener: {e}")
            self._keyboard_listener = None
        self._is_recording_hotkey_active = False
        hotkey_name = RECORD_HOTKEY._name_ if RECORD_HOTKEY and hasattr(RECORD_HOTKEY, '_name_') else 'N/A'
        self.record_pos_button.setText(f"Enable Recording Hotkey ({hotkey_name})")
        self.record_pos_button.setChecked(False) # Ensure button is unchecked
        # Check main window status before resetting
        # if f"Recording Hotkey ({hotkey_name}) Active" in self._main_window.status_bar.currentMessage():
        #      self._emit_status_update("Ready")

    def _process_record_hotkey_press(self):
        # Logic remains mostly the same, but emit position_added signal
        if not self._is_recording_hotkey_active or not pyautogui or platform.system() != "Windows": return

        target_process = self.target_process_input.text() # Get from UI
        if not target_process:
            QMessageBox.critical(self, "Internal Error", "Recording hotkey active but no target process set."); self._stop_record_hotkey_listener(); return

        try: mouse_x, mouse_y = pyautogui.position(); print(f"Hotkey pressed. Mouse at screen coordinates: ({mouse_x}, {mouse_y})")
        except Exception as e: QMessageBox.warning(self, "Record Position Error", f"Could not get mouse coordinates:\n{e}"); return

        hwnd, rect = find_window_for_process(target_process)
        if not hwnd or not rect:
            QMessageBox.warning(self, "Target Window Not Found", f"Could not find a visible window for '{target_process}'."); self._emit_status_update(f"Target window for '{target_process}' not found. Hotkey still active."); return

        window_x, window_y = rect[0], rect[1]; print(f"Found target window '{target_process}' at ({window_x}, {window_y})")
        relative_x = mouse_x - window_x; relative_y = mouse_y - window_y; print(f"Calculated relative coordinates: ({relative_x}, {relative_y})")

        default_name = f"Pos_{self.position_list_widget.count() + 1}" # Get count from own list
        text, ok = QInputDialog.getText(self, "Record Relative Position", f"Target: '{target_process}' @ ({window_x},{window_y})\nMouse (Abs): ({mouse_x},{mouse_y})\nRelative Coords: ({relative_x},{relative_y})\n\nEnter a name:", QLineEdit.EchoMode.Normal, default_name)

        if ok and text:
            position_name = text.strip()
            if not position_name: QMessageBox.warning(self, "Record Position", "Position name cannot be empty."); return

            # --- Emit signal instead of modifying scenario directly ---
            self.position_added.emit(position_name, relative_x, relative_y)
            # MainWindow will handle adding to scenario and updating list
            hotkey_name = RECORD_HOTKEY._name_ if hasattr(RECORD_HOTKEY, '_name_') else 'N/A'
            self._emit_status_update(f"Relative position '{position_name}' ({relative_x},{relative_y}) recorded. Press {hotkey_name} again...")
            print(f"Emitted position_added: {position_name} at ({relative_x},{relative_y})")
        else:
            self._emit_status_update(f"Position recording cancelled by user. Hotkey still active.")
            print("Position recording name input cancelled.")

    def stop_listeners(self):
        """Stop any active listeners."""
        self._stop_picking_mode()
        self._stop_record_hotkey_listener()