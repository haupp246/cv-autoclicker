# ui/widgets/right_panel.py

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QListWidget, QPushButton,
    QMessageBox
)
from PyQt6.QtGui import QIcon, QColor, QPalette
from PyQt6.QtCore import pyqtSignal, Qt
from typing import List

# Import constants (adjust path if needed, or pass them in)
ICON_ADD = None; ICON_REMOVE = None

class RightPanelWidget(QWidget):
    """Widget containing the Scenario Actions list and controls."""
    add_action_requested = pyqtSignal()
    remove_action_requested = pyqtSignal(int)
    edit_action_requested = pyqtSignal(int) # index to edit
    move_action_up_requested = pyqtSignal(int) # index to move up
    move_action_down_requested = pyqtSignal(int) # index to move down

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        self.main_layout = QVBoxLayout(self); self.main_layout.setContentsMargins(5, 5, 5, 5)
        scenario_group = QGroupBox("Scenario Actions"); scenario_layout = QVBoxLayout()

        self.action_list_widget = QListWidget(); self.action_list_widget.setToolTip("Sequence of actions to perform.")
        # --- Connect selection change to update button states ---
        self.action_list_widget.currentRowChanged.connect(self._update_move_button_state)
        scenario_layout.addWidget(self.action_list_widget)

        action_buttons_layout = QHBoxLayout()
        self.add_action_button = QPushButton("Add"); self.add_action_button.setToolTip("Add a new action to the end"); self.add_action_button.clicked.connect(self.add_action_requested)
        if ICON_ADD: self.add_action_button.setIcon(QIcon(ICON_ADD))

        # --- Edit Button ---
        self.edit_action_button = QPushButton("Edit"); self.edit_action_button.setToolTip("Edit the selected action"); self.edit_action_button.clicked.connect(self._request_edit_action); self.edit_action_button.setEnabled(False) # Disabled initially

        self.remove_action_button = QPushButton("Remove"); self.remove_action_button.setToolTip("Remove the selected action"); self.remove_action_button.clicked.connect(self._request_remove_action); self.remove_action_button.setEnabled(False) # Disabled initially
        if ICON_REMOVE: self.remove_action_button.setIcon(QIcon(ICON_REMOVE))

        # --- Move Buttons ---
        self.move_up_button = QPushButton("Move Up"); self.move_up_button.setToolTip("Move selected action up"); self.move_up_button.clicked.connect(self._request_move_up); self.move_up_button.setEnabled(False)
        self.move_down_button = QPushButton("Move Down"); self.move_down_button.setToolTip("Move selected action down"); self.move_down_button.clicked.connect(self._request_move_down); self.move_down_button.setEnabled(False)

        action_buttons_layout.addWidget(self.add_action_button)
        action_buttons_layout.addWidget(self.edit_action_button) # Add Edit button
        action_buttons_layout.addWidget(self.remove_action_button)
        action_buttons_layout.addStretch() # Add spacer
        action_buttons_layout.addWidget(self.move_up_button) # Add Move buttons
        action_buttons_layout.addWidget(self.move_down_button)
        scenario_layout.addLayout(action_buttons_layout)

        scenario_group.setLayout(scenario_layout); self.main_layout.addWidget(scenario_group)
        self._update_move_button_state(-1) # Initial state update

    def _request_remove_action(self):
        selected_row = self.action_list_widget.currentRow()
        if selected_row >= 0: self.remove_action_requested.emit(selected_row)
        # else: QMessageBox.warning(self, "Remove Action", "Please select an action to remove.") # Warning handled by button state

    def _request_edit_action(self):
        selected_row = self.action_list_widget.currentRow()
        if selected_row >= 0: self.edit_action_requested.emit(selected_row)

    def _request_move_up(self):
        selected_row = self.action_list_widget.currentRow()
        if selected_row > 0: # Can only move up if not the first item
            self.move_action_up_requested.emit(selected_row)

    def _request_move_down(self):
        selected_row = self.action_list_widget.currentRow()
        if 0 <= selected_row < self.action_list_widget.count() - 1: # Can only move down if not the last item
            self.move_action_down_requested.emit(selected_row)

    def _update_move_button_state(self, current_row):
        """Enables/disables Edit, Remove, Move buttons based on selection."""
        has_selection = current_row >= 0
        is_first = current_row == 0
        is_last = current_row == self.action_list_widget.count() - 1

        self.edit_action_button.setEnabled(has_selection)
        self.remove_action_button.setEnabled(has_selection)
        self.move_up_button.setEnabled(has_selection and not is_first)
        self.move_down_button.setEnabled(has_selection and not is_last)

    def update_action_list(self, actions: List['Action']):
        """Refreshes the action list with proper indentation."""
        self.action_list_widget.clear()
        indent_level = 0
        # Need Action types here for indentation logic
        from core.scenario import ACTION_IF_OBJECT_FOUND, ACTION_END_IF, ACTION_LOOP_START, ACTION_LOOP_END # Import locally

        for i, action in enumerate(actions):
            # Adjust indent level BEFORE processing the item for END actions
            if action.type in [ACTION_END_IF, ACTION_LOOP_END]:
                indent_level = max(0, indent_level - 1)

            display_text = "    " * indent_level + self._format_action_display(i, action) # Use 4 spaces for indent
            self.action_list_widget.addItem(display_text)

            # Adjust indent level AFTER processing the item for START actions
            if action.type in [ACTION_IF_OBJECT_FOUND, ACTION_LOOP_START]: # Add other IFs/Loops later
                 indent_level += 1
        self._update_move_button_state(self.action_list_widget.currentRow()) # Update buttons after list refresh

    def highlight_action(self, index: int, color: QColor):
         item = self.action_list_widget.item(index)
         if item: item.setBackground(color)

    def clear_highlights(self, default_color: QColor):
        for i in range(self.action_list_widget.count()):
            item = self.action_list_widget.item(i)
            if item: item.setBackground(default_color)

    def set_current_row(self, index: int):
        if 0 <= index < self.action_list_widget.count(): self.action_list_widget.setCurrentRow(index)

    def get_default_background_color(self) -> QColor:
        return self.action_list_widget.palette().color(QPalette.ColorRole.Base)

    def set_running_state(self, is_running: bool):
        self.add_action_button.setEnabled(not is_running)
        # Disable edit/remove/move buttons when running
        self.edit_action_button.setEnabled(not is_running and self.action_list_widget.currentRow() >= 0)
        self.remove_action_button.setEnabled(not is_running and self.action_list_widget.currentRow() >= 0)
        self._update_move_button_state(self.action_list_widget.currentRow() if not is_running else -1) # Update move buttons based on running state
        self.action_list_widget.setEnabled(not is_running) # Disable list interaction

    def _format_action_display(self, index: int, action: 'Action') -> str:
        """Creates the display string for an action item."""
        from core.scenario import (
            ACTION_CLICK, ACTION_WAIT, ACTION_WAIT_FOR_OBJECT,
            ACTION_IF_OBJECT_FOUND, ACTION_END_IF, CLICK_TARGET_FOUND_OBJECT,
            ACTION_LOOP_START, ACTION_LOOP_END, ACTION_CHECK_OBJECT_BREAK_LOOP
            # ACTION_WAIT_FOR_TEXT, ACTION_IF_TEXT_FOUND, CLICK_TARGET_FOUND_TEXT # Add later
        )
        import os

        display_text = f"{index+1}. {action.type}"
        details = action.details
        try:
            if action.type == ACTION_CLICK:
                pos = details.get('position_name', 'N/A'); btn = details.get('button', 'left'); clk = details.get('click_type', 'single'); off_x = details.get('offset_x', 0); off_y = details.get('offset_y', 0)
                if pos == CLICK_TARGET_FOUND_OBJECT: display_text += f" [Target: Found Object, Offset:({off_x},{off_y}), Btn: {btn}, Type: {clk}]"
                # elif pos == CLICK_TARGET_FOUND_TEXT: display_text += f" [Target: Found Text, Offset:({off_x},{off_y}), Btn: {btn}, Type: {clk}]" # Add later
                else: display_text += f" [Pos: {pos}, Btn: {btn}, Type: {clk}]"
            elif action.type == ACTION_WAIT: dur = details.get('duration_ms', 'N/A'); display_text += f" [Duration: {dur} ms]"
            elif action.type in [ACTION_WAIT_FOR_OBJECT, ACTION_IF_OBJECT_FOUND, ACTION_CHECK_OBJECT_BREAK_LOOP]: # Shared display logic
                tmpl = os.path.basename(details.get('template_path', 'N/A')); conf = details.get('confidence', 0.8); region = details.get('region')
                prefix = "Break Loop If Found" if action.type == ACTION_CHECK_OBJECT_BREAK_LOOP else "Template"
                display_text += f" [{prefix}: {tmpl}, Conf: {conf:.2f}"
                if region: display_text += f", Region: {region[0]},{region[1]},{region[2]},{region[3]}"
                if action.type == ACTION_WAIT_FOR_OBJECT: timeout = details.get('timeout_ms', 'Infinite'); display_text += f", Timeout: {timeout}"
                display_text += "]"
            elif action.type == ACTION_LOOP_START:
                 iters = details.get('iterations', 1)
                 display_text += f" [Iterations: {'Infinite' if iters == 0 else iters}]"
            elif action.type == ACTION_LOOP_END:
                 break_cond = details.get('break_condition', 'none')
                 if break_cond == "last_if_success": display_text += " [Break If Last Condition Met]"
            elif action.type == ACTION_END_IF: pass
        except Exception as e: print(f"Error formatting action display: {e} for action {details}"); display_text += " [Error displaying details]"
        return display_text