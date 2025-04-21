# ui/main_window.py

import sys
import platform
import os
import time
from typing import List, Optional, Tuple

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QStatusBar, QMenuBar, QGroupBox, QLineEdit, QPushButton, QCheckBox,
    QListWidget, QToolBar, QSplitter, QMessageBox, QInputDialog, QDialog,
    QFormLayout, QComboBox, QSpinBox, QDialogButtonBox, QFileDialog,
    QDoubleSpinBox
)
from PyQt6.QtGui import QAction, QIcon, QCursor, QColor, QPalette
from PyQt6.QtCore import Qt, QSize, QTimer, pyqtSlot

# --- Import Panels ---
from ui.widgets.left_panel import LeftPanelWidget
from ui.widgets.right_panel import RightPanelWidget
# --- Import AddActionDialog ---
from ui.dialogs.add_action_dialog import AddActionDialog
# --- Import Overlay ---
from overlay.overlay_window import OverlayWindow

# Import Core/System stuff
from system.process_utils import find_window_for_process
# --- Import Scenario and specific Action Types needed here ---
from core.scenario import (
    Scenario, Position, Action, ACTION_TYPES, ACTION_CLICK, ACTION_WAIT,
    ACTION_WAIT_FOR_OBJECT, ACTION_IF_OBJECT_FOUND, ACTION_CHECK_OBJECT_BREAK_LOOP # Import needed types
)
from core.scenario_runner import ScenarioRunner

# Import pynput/pyautogui conditionally
try: from pynput import keyboard
except ImportError: keyboard = None
try: import pyautogui
except ImportError: pyautogui = None

# --- Constants ---
ICON_FOLDER = "icons/"
ICON_START = None; ICON_STOP = None; ICON_RECORD = None
RECORD_HOTKEY = keyboard.Key.f7 if keyboard else None
STOP_HOTKEY = keyboard.Key.f6 if keyboard else None


class MainWindow(QMainWindow):
    """Main application window - Orchestrator."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Advanced Auto-Clicker")
        self.setGeometry(100, 100, 900, 700)

        self.current_scenario = Scenario()
        self._scenario_runner: Optional[ScenarioRunner] = None
        self._stop_hotkey_listener = None

        self._overlay_window = OverlayWindow()
        self.left_panel = LeftPanelWidget(self)
        self.right_panel = RightPanelWidget(self)

        self._setup_ui() # Call UI setup method

        self._create_menu_bar()
        self._create_tool_bar()
        self.status_bar = QStatusBar(); self.setStatusBar(self.status_bar)

        self.left_panel.target_process_changed.connect(self._update_target_process)
        self.left_panel.require_focus_changed.connect(self._update_require_focus)
        self.left_panel.position_added.connect(self._add_position)
        self.left_panel.status_update_requested.connect(self.update_status)
        self.right_panel.add_action_requested.connect(self._add_action)
        self.right_panel.remove_action_requested.connect(self._remove_action)
        self.right_panel.edit_action_requested.connect(self._edit_action) # Connect Edit
        self.right_panel.move_action_up_requested.connect(self._move_action_up) # Connect Move Up
        self.right_panel.move_action_down_requested.connect(self._move_action_down) # Connect Move Down

        self.update_status("Ready"); self._update_window_title(); self._start_global_listeners()
        print("MainWindow initialized.")

    def _setup_ui(self):
        """Creates the UI panels and widgets."""
        # --- Run Settings Panel (NEW) ---
        self.run_settings_widget = QWidget()
        run_settings_layout = QHBoxLayout(self.run_settings_widget)
        run_settings_layout.setContentsMargins(10, 2, 10, 2)

        run_settings_layout.addWidget(QLabel("Scenario Repetitions:"))
        self.repetitions_spinbox = QSpinBox()
        self.repetitions_spinbox.setRange(0, 99999)
        self.repetitions_spinbox.setValue(self.current_scenario.global_repetitions) # Use value from scenario
        self.repetitions_spinbox.setToolTip("Number of times to run the entire scenario (0 = Infinite)")
        self.repetitions_spinbox.setSpecialValueText("Infinite")
        self.repetitions_spinbox.valueChanged.connect(self._update_global_repetitions)
        run_settings_layout.addWidget(self.repetitions_spinbox)
        run_settings_layout.addStretch()

        # --- Main Layout (Splitter + Run Settings below) ---
        main_layout_widget = QWidget()
        main_v_layout = QVBoxLayout(main_layout_widget)
        main_v_layout.setContentsMargins(0,0,0,0)
        main_v_layout.setSpacing(0)

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.addWidget(self.left_panel) # Add left panel instance
        self.main_splitter.addWidget(self.right_panel) # Add right panel instance
        self.main_splitter.setStretchFactor(0, 1); self.main_splitter.setStretchFactor(1, 2)
        self.main_splitter.setSizes([350, 550])

        main_v_layout.addWidget(self.main_splitter)
        main_v_layout.addWidget(self.run_settings_widget) # Add run settings below splitter

        self.setCentralWidget(main_layout_widget)

    def _update_window_title(self):
        title = f"Advanced Auto-Clicker - {self.current_scenario.scenario_name or 'Untitled Scenario'}"
        if self.current_scenario.is_modified: title += " *"
        self.setWindowTitle(title)

    def _create_menu_bar(self):
        menu_bar = self.menuBar(); menu_bar.clear()
        file_menu = menu_bar.addMenu("&File"); new_action = QAction("&New Scenario", self); new_action.triggered.connect(self._new_scenario); load_action = QAction("&Load Scenario...", self); load_action.triggered.connect(self._load_scenario); save_action = QAction("&Save Scenario", self); save_action.triggered.connect(self._save_scenario); save_as_action = QAction("Save Scenario &As...", self); save_as_action.triggered.connect(self._save_scenario_as); exit_action = QAction("&Exit", self); exit_action.triggered.connect(self.close); file_menu.addAction(new_action); file_menu.addAction(load_action); file_menu.addAction(save_action); file_menu.addAction(save_as_action); file_menu.addSeparator(); file_menu.addAction(exit_action)
        view_menu = menu_bar.addMenu("&View"); self.toggle_overlay_action = QAction("Show &Overlay", self, checkable=True); self.toggle_overlay_action.setStatusTip("Show/hide the debugging overlay"); self.toggle_overlay_action.toggled.connect(self._toggle_overlay); view_menu.addAction(self.toggle_overlay_action)
        run_menu = menu_bar.addMenu("&Run"); self.start_action = QAction("&Start Scenario", self); self.stop_action = QAction("S&top Scenario", self); self.stop_action.setEnabled(False); self.start_action.triggered.connect(self._start_scenario); self.stop_action.triggered.connect(self._stop_scenario); run_menu.addAction(self.start_action); run_menu.addAction(self.stop_action)
        help_menu = menu_bar.addMenu("&Help"); about_action = QAction("&About", self); help_menu.addAction(about_action)

    def _create_tool_bar(self):
        toolbar = QToolBar("Main Toolbar"); toolbar.setIconSize(QSize(24, 24)); self.addToolBar(toolbar)
        start_icon = QIcon(ICON_START) if ICON_START else QIcon(); stop_icon = QIcon(ICON_STOP) if ICON_STOP else QIcon(); record_icon = QIcon(ICON_RECORD) if ICON_RECORD else QIcon()
        self.start_action = QAction(start_icon, "&Start Scenario", self); self.start_action.setStatusTip("Start running the current scenario"); self.start_action.triggered.connect(self._start_scenario); toolbar.addAction(self.start_action)
        
        self.stop_action = QAction(stop_icon, "S&top Scenario", self)
        stop_hotkey_name = STOP_HOTKEY._name_ if STOP_HOTKEY and hasattr(STOP_HOTKEY, '_name_') else 'N/A'
        # --- Add (F6) hint ---
        self.stop_action.setText(f"S&top Scenario ({stop_hotkey_name})")
        self.stop_action.setStatusTip(f"Stop the currently running scenario (Hotkey: {stop_hotkey_name})")
        self.stop_action.setEnabled(False)
        self.stop_action.triggered.connect(self._stop_scenario)
        toolbar.addAction(self.stop_action)

        toolbar.addSeparator()
        hotkey_name = RECORD_HOTKEY._name_ if RECORD_HOTKEY and hasattr(RECORD_HOTKEY, '_name_') else 'N/A'
        self.record_toolbar_action = QAction(record_icon, f"Enable Record Hotkey ({hotkey_name})", self); self.record_toolbar_action.setStatusTip(f"Enable listening for {hotkey_name} to record mouse position relative to target."); self.record_toolbar_action.setCheckable(True); self.record_toolbar_action.toggled.connect(self.left_panel.set_record_button_checked); self.left_panel.record_pos_button.toggled.connect(self.record_toolbar_action.setChecked); toolbar.addAction(self.record_toolbar_action);
        if keyboard is None or pyautogui is None or RECORD_HOTKEY is None or platform.system() != "Windows": self.record_toolbar_action.setEnabled(False); self.record_toolbar_action.setText("Recording Disabled")
        view_toolbar = self.addToolBar("View Toolbar"); overlay_icon = QIcon(); overlay_toolbar_action = QAction(overlay_icon, "Toggle Overlay", self); overlay_toolbar_action.setStatusTip("Show/hide the debugging overlay"); overlay_toolbar_action.setCheckable(True); overlay_toolbar_action.toggled.connect(self._toggle_overlay); self.toggle_overlay_action.toggled.connect(overlay_toolbar_action.setChecked); overlay_toolbar_action.toggled.connect(self.toggle_overlay_action.setChecked); view_toolbar.addAction(overlay_toolbar_action)

    def _prompt_save_if_needed(self) -> bool:
        if not self.current_scenario.is_modified: return True
        reply = QMessageBox.question(self, 'Unsaved Changes', f"Scenario '{self.current_scenario.scenario_name}' has unsaved changes.\nDo you want to save them?", QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Save)
        if reply == QMessageBox.StandardButton.Save: return self._save_scenario()
        elif reply == QMessageBox.StandardButton.Cancel: return False
        else: return True

    def closeEvent(self, event):
        if self._scenario_runner and self._scenario_runner.isRunning(): self._stop_scenario()
        if self._prompt_save_if_needed():
            self.left_panel.stop_listeners(); self._stop_global_listeners(); self._overlay_window.close(); event.accept()
        else: event.ignore()

    @pyqtSlot(str)
    def update_status(self, message):
        self.status_bar.showMessage(message); print(f"Status: {message}")

    @pyqtSlot(str)
    def _update_target_process(self, text):
        new_value = text if text else None
        if self.current_scenario.target_process_name != new_value: self.current_scenario.set_target_process(new_value); self._mark_scenario_modified()

    @pyqtSlot(bool)
    def _update_require_focus(self, required):
        if self.current_scenario.require_focus != required: self.current_scenario.set_require_focus(required); self._mark_scenario_modified()

    @pyqtSlot(int)
    def _update_global_repetitions(self, value):
        """Updates the global repetitions in the current scenario."""
        if self.current_scenario.global_repetitions != value:
            self.current_scenario.set_global_repetitions(value)
            self._mark_scenario_modified()

    @pyqtSlot(str, int, int)
    def _add_position(self, name, rel_x, rel_y):
        try:
            self.current_scenario.add_position(name, rel_x, rel_y); self.left_panel.update_position_list(self.current_scenario.positions); self._mark_scenario_modified()
        except ValueError as e: QMessageBox.warning(self.left_panel, "Record Position", str(e))

    def _mark_scenario_modified(self):
        self.current_scenario._mark_modified(); self._update_window_title()

    def _new_scenario(self):
        if not self._prompt_save_if_needed(): return
        print("Creating new scenario..."); self.left_panel.stop_listeners()
        self.current_scenario = Scenario(); self._update_ui_from_scenario()
        self.update_status("New scenario created.")

    def _load_scenario(self):
        if not self._prompt_save_if_needed(): return
        default_dir = os.path.dirname(self.current_scenario.filepath) if self.current_scenario.filepath else ""
        filepath, _ = QFileDialog.getOpenFileName(self, "Load Scenario", default_dir, "Scenario Files (*.json);;All Files (*)")
        if filepath:
            print(f"Attempting to load scenario from: {filepath}")
            try:
                self.left_panel.stop_listeners(); self.current_scenario = Scenario.load_from_file(filepath); self._update_ui_from_scenario()
                self.update_status(f"Scenario '{self.current_scenario.scenario_name}' loaded successfully."); print("Scenario loaded.")
            except Exception as e: error_msg = f"Failed to load scenario from {filepath}:\n{e}"; print(error_msg); QMessageBox.critical(self, "Load Error", error_msg); self.update_status("Scenario load failed.")

    def _save_scenario(self) -> bool:
        if not self.current_scenario.filepath: return self._save_scenario_as()
        else:
            print(f"Attempting to save scenario to: {self.current_scenario.filepath}")
            try:
                if self.current_scenario.scenario_name == "Untitled Scenario": base_name = os.path.splitext(os.path.basename(self.current_scenario.filepath))[0]; self.current_scenario.set_name(base_name)
                self.current_scenario.save_to_file(self.current_scenario.filepath); self._update_window_title(); self.update_status(f"Scenario saved to {self.current_scenario.filepath}"); print("Scenario saved."); return True
            except Exception as e: error_msg = f"Failed to save scenario to {self.current_scenario.filepath}:\n{e}"; print(error_msg); QMessageBox.critical(self, "Save Error", error_msg); self.update_status("Scenario save failed."); return False

    def _save_scenario_as(self) -> bool:
        suggested_name = f"{self.current_scenario.scenario_name or 'Untitled Scenario'}.json"; default_dir = os.path.dirname(self.current_scenario.filepath) if self.current_scenario.filepath else ""
        filepath, _ = QFileDialog.getSaveFileName(self, "Save Scenario As", os.path.join(default_dir, suggested_name), "Scenario Files (*.json);;All Files (*)")
        if filepath:
            print(f"Attempting to save scenario to new path: {filepath}"); self.current_scenario.filepath = filepath
            base_name = os.path.splitext(os.path.basename(filepath))[0]
            if self.current_scenario.scenario_name == "Untitled Scenario" or not self.current_scenario.scenario_name: self.current_scenario.set_name(base_name)
            return self._save_scenario()
        else: self.update_status("Save As cancelled."); return False

    @pyqtSlot()
    def _add_action(self):
        print("Add Action requested.")
        available_positions = self.current_scenario.get_position_names()
        dialog = AddActionDialog(available_positions, self) # Pass None for edit_action
        if dialog.exec():
            new_action = dialog.get_action()
            if new_action:
                # Add to end or at current selection + 1? Let's add to end.
                self.current_scenario.add_action(new_action)
                self.right_panel.update_action_list(self.current_scenario.actions)
                new_row_index = len(self.current_scenario.actions) - 1
                self.right_panel.set_current_row(new_row_index) # Select new item
                self.update_status(f"Action '{new_action.type}' added."); print(f"Added action: {new_action.to_dict()}"); self._mark_scenario_modified()
        else: print("Add action cancelled."); self.update_status("Add action cancelled.")

    @pyqtSlot(int)
    def _edit_action(self, index):
        """Opens the dialog to edit an existing action."""
        if not (0 <= index < len(self.current_scenario.actions)): return

        action_to_edit = self.current_scenario.actions[index]
        print(f"Edit Action requested for index {index}: {action_to_edit.to_dict()}")
        available_positions = self.current_scenario.get_position_names()

        # Pass the existing action to the dialog
        dialog = AddActionDialog(available_positions, self, edit_action=action_to_edit)

        if dialog.exec():
            edited_action = dialog.get_action()
            if edited_action:
                # Replace the action in the scenario list
                self.current_scenario.actions[index] = edited_action
                self.right_panel.update_action_list(self.current_scenario.actions) # Refresh list
                self.right_panel.set_current_row(index) # Reselect edited item
                self.update_status(f"Action {index+1} ('{edited_action.type}') updated.")
                print(f"Edited action {index}: {edited_action.to_dict()}")
                self._mark_scenario_modified()
        else:
             print("Edit action cancelled.")
             self.update_status("Edit action cancelled.")

    @pyqtSlot(int)
    def _remove_action(self, index): # ... (implementation is same) ...
        if not (0 <= index < len(self.current_scenario.actions)): return
        action_to_remove = self.current_scenario.actions[index]; print(f"Removing action at index {index}: {action_to_remove.to_dict()}"); reply = QMessageBox.question(self, "Remove Action", f"Are you sure you want to remove the selected '{action_to_remove.type}' action?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.current_scenario.remove_action(index); self.right_panel.update_action_list(self.current_scenario.actions); self.update_status(f"Action removed."); print("Action removed."); self._mark_scenario_modified()
            if len(self.current_scenario.actions) > 0: new_selection = max(0, index - 1); self.right_panel.set_current_row(new_selection)

    @pyqtSlot(int)
    def _move_action_up(self, index):
        """Moves the selected action one position up in the list."""
        if 0 < index < len(self.current_scenario.actions):
            actions = self.current_scenario.actions
            actions[index], actions[index - 1] = actions[index - 1], actions[index] # Swap
            self.current_scenario._mark_modified() # Mark scenario modified
            self.right_panel.update_action_list(actions) # Update UI
            self.right_panel.set_current_row(index - 1) # Keep new position selected
            self.update_status(f"Moved action {index+1} up.")
            print(f"Moved action from {index} to {index-1}")

    @pyqtSlot(int)
    def _move_action_down(self, index):
        """Moves the selected action one position down in the list."""
        if 0 <= index < len(self.current_scenario.actions) - 1:
            actions = self.current_scenario.actions
            actions[index], actions[index + 1] = actions[index + 1], actions[index] # Swap
            self.current_scenario._mark_modified() # Mark scenario modified
            self.right_panel.update_action_list(actions) # Update UI
            self.right_panel.set_current_row(index + 1) # Keep new position selected
            self.update_status(f"Moved action {index+1} down.")
            print(f"Moved action from {index} to {index+1}")

    def _update_ui_from_scenario(self):
        print("Updating UI from scenario...")
        self.left_panel.set_target_process(self.current_scenario.target_process_name); self.left_panel.set_require_focus(self.current_scenario.require_focus); self.left_panel.update_position_list(self.current_scenario.positions); self.left_panel.stop_listeners()
        self.right_panel.update_action_list(self.current_scenario.actions)
        self.repetitions_spinbox.blockSignals(True); self.repetitions_spinbox.setValue(self.current_scenario.global_repetitions); self.repetitions_spinbox.blockSignals(False)
        self._update_window_title(); print("UI updated.")

    def _start_scenario(self):
        # ... (checks) ...
        print("Starting scenario execution..."); self._set_ui_running_state(True)
        repetitions = self.repetitions_spinbox.value()
        self._overlay_window.update_status(f"Running: {self.current_scenario.scenario_name} (Rep: 1/{'Infinite' if repetitions == 0 else repetitions})")

        self._scenario_runner = ScenarioRunner(self.current_scenario, repetitions, self)
        # --- Connect ALL signals ---
        self._scenario_runner.status_update.connect(self._on_runner_status_update)
        self._scenario_runner.finished.connect(self._on_scenario_finished)
        self._scenario_runner.error_occurred.connect(self._on_scenario_error)
        self._scenario_runner.action_started.connect(self._highlight_action)
        # --- Ensure Overlay Signals ARE Connected ---
        self._scenario_runner.object_detected_at.connect(self._overlay_show_found_object)
        self._scenario_runner.click_target_calculated.connect(self._overlay_show_click_target)
        # --- Connect Overlay Control Signals ---
        self._scenario_runner.request_hide_overlay.connect(self._hide_overlay_temporarily)
        self._scenario_runner.request_show_overlay.connect(self._show_overlay_after_action)
        # --- Connect Repetition Signal ---
        self._scenario_runner.repetition_update.connect(self._on_repetition_update)
        self._scenario_runner.start()

    def _stop_scenario(self):
        if self._scenario_runner and self._scenario_runner.isRunning():
            print("Requesting scenario stop...")
            self.update_status("Stopping scenario...")
            self._overlay_window.update_status("Stopping...")
            self._scenario_runner.stop() # Signal the thread to stop
            # --- Re-enable UI immediately ---
            print("Re-enabling UI after stop request.")
            self._set_ui_running_state(False)
            # Optional: Clear highlights immediately? Or wait for thread exit? Let's clear now.
            self._clear_action_highlights()
        else:
            # If called when not running, ensure UI is enabled
            self.update_status("Scenario is not running.")
            if not self.start_action.isEnabled(): # Check if UI might be wrongly disabled
                 self._set_ui_running_state(False)

    def _set_ui_running_state(self, is_running):
        """Enable/disable UI elements based on running state."""
        print(f"Setting UI Running State: {is_running}") # Debug print
        self.start_action.setEnabled(not is_running)
        self.stop_action.setEnabled(is_running)
        self.left_panel.set_running_state(is_running)
        self.right_panel.set_running_state(is_running)
        self.run_settings_widget.setEnabled(not is_running)
        # Enable/disable relevant menu actions
        for action in self.menuBar().findChildren(QAction):
             action_text = action.text().split(" (")[0] # Ignore hotkey hints for comparison
             if action_text in ["&New Scenario", "&Load Scenario...", "Save Scenario &As...", "&Save Scenario"]:
                 action.setEnabled(not is_running)
             # Ensure Start/Stop menu items match toolbar state
             elif action_text == "&Start Scenario":
                 action.setEnabled(not is_running)
             elif action_text == "S&top Scenario":
                 action.setEnabled(is_running)     

    @pyqtSlot(str)
    def _on_runner_status_update(self, message):
        # Avoid overwriting repetition count if it's currently displayed
        if not message.startswith("Running Repetition:"):
            self.update_status(message)
            self._overlay_window.update_status(message)

    @pyqtSlot(int, int)
    def _on_repetition_update(self, current_rep, total_reps):
        total_str = "Infinite" if total_reps == 0 else str(total_reps)
        status_msg = f"Running Repetition: {current_rep}/{total_str}"
        self.update_status(status_msg)
        self._overlay_window.update_status(status_msg)

    @pyqtSlot()
    def _on_scenario_finished(self):
        """Called when the scenario runner finishes normally."""
        print("Scenario finished signal received by main window.")
        # Ensure UI is enabled, even if stop was already clicked
        if not self.start_action.isEnabled():
             self._set_ui_running_state(False)
        self._clear_action_highlights()
        # Don't override final "Finished" status from runner if stop wasn't clicked
        # self._overlay_window.update_status("Finished")

    @pyqtSlot(str)
    def _on_scenario_error(self, error_message):
        """Called when the scenario runner encounters an error."""
        print(f"Scenario error signal received: {error_message}")
        # Ensure UI is enabled
        if not self.start_action.isEnabled():
            self._set_ui_running_state(False)
        self._clear_action_highlights()
        QMessageBox.critical(self, "Scenario Error", error_message)
        # Status already updated by runner signal connection
        # self.update_status(f"Error: {error_message}")
        # self._overlay_window.update_status(f"Error: {error_message}")
        
    @pyqtSlot(int)
    def _highlight_action(self, index):
        self._clear_action_highlights(); color = QColor(Qt.GlobalColor.yellow)
        self.right_panel.highlight_action(index, color)
    def _clear_action_highlights(self):
        color = self.right_panel.get_default_background_color()
        self.right_panel.clear_highlights(color)

    # --- Overlay Methods ---
    @pyqtSlot(bool)
    def _toggle_overlay(self, checked):
        """Shows or hides the overlay window based on user toggle."""
        if checked:
            print("Showing overlay (User Toggle)...")
            self._overlay_window.show()
        else:
            print("Hiding overlay (User Toggle)...")
            self._overlay_window.hide()

    # --- Slots for Runner Overlay Control ---
    @pyqtSlot()
    def _hide_overlay_temporarily(self):
        """Hides overlay only if it's currently supposed to be visible."""
        if self.toggle_overlay_action.isChecked(): # Check the user's desired state
             # print("Temporarily hiding overlay for action...")
             self._overlay_window.hide()

    @pyqtSlot()
    def _show_overlay_after_action(self):
        """Shows overlay only if it's supposed to be visible."""
        if self.toggle_overlay_action.isChecked(): # Check the user's desired state
             # print("Restoring overlay after action...")
             self._overlay_window.show()

    @pyqtSlot(int, int, int, int, float, str)
    def _overlay_show_found_object(self, x, y, w, h, confidence, template_name):
        if self._overlay_window.isVisible():
            print(f"Overlay: Drawing rect for '{template_name}' at ({x},{y}) size ({w},{h}), Conf: {confidence:.2f}")
            item = {"type": "rect", "rect": [x,y,w,h], "color": QColor("lime"), "duration_ms": 1500, "label": template_name, "confidence": confidence}
            self._overlay_window.add_item(item)

    @pyqtSlot(int, int)
    def _overlay_show_click_target(self, x, y):
         if self._overlay_window.isVisible():
             print(f"Overlay: Drawing point at ({x},{y})")
             item = {"type": "point", "pos": [x,y], "color": QColor("yellow"), "radius": 5, "duration_ms": 750, "label": "Click"}
             self._overlay_window.add_item(item)

    def _start_global_listeners(self):
        if not keyboard or not STOP_HOTKEY: return
        if self._stop_hotkey_listener and self._stop_hotkey_listener.is_alive(): return
        stop_hotkey_name = STOP_HOTKEY._name_ if hasattr(STOP_HOTKEY, '_name_') else 'N/A'
        print(f"Starting global stop hotkey ({stop_hotkey_name}) listener...")
        try:
            def on_press(key):
                if key == STOP_HOTKEY: print(f"Stop hotkey ({stop_hotkey_name}) pressed."); QTimer.singleShot(0, self._stop_scenario)
            self._stop_hotkey_listener = keyboard.Listener(on_press=on_press, suppress=False); self._stop_hotkey_listener.start()
        except Exception as e: print(f"Error starting global stop listener: {e}"); QMessageBox.warning(self, "Hotkey Error", f"Could not start global stop hotkey listener ({stop_hotkey_name}):\n{e}")

    def _stop_global_listeners(self):
        if self._stop_hotkey_listener:
            print("Stopping global stop hotkey listener...")
            try: self._stop_hotkey_listener.stop()
            except Exception as e: print(f"Error stopping global listener: {e}")
            self._stop_hotkey_listener = None

    # --- Placeholders ---
    # def show_about_dialog(self): pass

# --- Main execution block ---
if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())