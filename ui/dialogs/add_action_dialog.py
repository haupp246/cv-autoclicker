# ui/dialogs/add_action_dialog.py

import os
from typing import List, Optional, Tuple
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QPushButton,
    QCheckBox, QListWidget, QMessageBox, QInputDialog, QComboBox, QSpinBox,
    QDialogButtonBox, QFileDialog, QDoubleSpinBox, QWidget, QLabel
)
from PyQt6.QtCore import Qt
# Import Action types and Action class
from core.scenario import (
    Action, ACTION_TYPES, ACTION_CLICK, ACTION_WAIT, ACTION_WAIT_FOR_OBJECT,
    ACTION_IF_OBJECT_FOUND, ACTION_END_IF, CLICK_TARGET_FOUND_OBJECT,
    ACTION_LOOP_START, ACTION_LOOP_END, ACTION_CHECK_OBJECT_BREAK_LOOP
    # ACTION_WAIT_FOR_TEXT, ACTION_IF_TEXT_FOUND, CLICK_TARGET_FOUND_TEXT # Add later
)


class AddActionDialog(QDialog):
    """Dialog for adding/configuring a new scenario action."""

    def __init__(self, available_positions: List[str], parent=None, edit_action: Optional[Action] = None):
        super().__init__(parent)
        self.available_positions = available_positions
        self.action_data = None
        self.edit_mode = edit_action is not None

        self.setWindowTitle("Edit Action" if self.edit_mode else "Add Action")

        # --- Setup UI Widgets (same as before) ---
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        self.action_type_combo = QComboBox()
        self.action_type_combo.addItems(ACTION_TYPES)
        self.action_type_combo.currentTextChanged.connect(self._update_options)
        form_layout.addRow("Action Type:", self.action_type_combo)
        # CLICK options
        self.click_options_widget = QWidget()
        click_layout = QFormLayout(self.click_options_widget)
        click_layout.setContentsMargins(0, 0, 0, 0)
        self.click_target_combo = QComboBox()
        self.click_target_combo.addItems(["Position", "Found Object"])
        self.click_target_combo.currentTextChanged.connect(
            self._update_click_options)
        click_layout.addRow("Click Target:", self.click_target_combo)
        self.click_position_label = QLabel("Position:")
        self.click_position_combo = QComboBox()
        click_layout.addRow(self.click_position_label,
                            self.click_position_combo)
        self.click_offset_label = QLabel("Offset (X, Y):")
        offset_layout = QHBoxLayout()
        self.click_offset_x_spinbox = QSpinBox()
        self.click_offset_x_spinbox.setRange(-5000, 5000)
        self.click_offset_y_spinbox = QSpinBox()
        self.click_offset_y_spinbox.setRange(-5000, 5000)
        offset_layout.addWidget(self.click_offset_x_spinbox)
        offset_layout.addWidget(self.click_offset_y_spinbox)
        click_layout.addRow(self.click_offset_label, offset_layout)
        self.click_button_combo = QComboBox()
        self.click_button_combo.addItems(["left", "right", "middle"])
        self.click_type_combo = QComboBox()
        self.click_type_combo.addItems(["single", "double"])
        click_layout.addRow("Button:", self.click_button_combo)
        click_layout.addRow("Click Type:", self.click_type_combo)
        form_layout.addRow(self.click_options_widget)
        # WAIT options
        self.wait_options_widget = QWidget()
        wait_layout = QFormLayout(self.wait_options_widget)
        wait_layout.setContentsMargins(0, 0, 0, 0)
        self.wait_duration_spinbox = QSpinBox()
        self.wait_duration_spinbox.setRange(10, 600000)
        self.wait_duration_spinbox.setValue(1000)
        self.wait_duration_spinbox.setSuffix(" ms")
        wait_layout.addRow("Duration:", self.wait_duration_spinbox)
        form_layout.addRow(self.wait_options_widget)
        # Find Object options
        self.find_object_widget = QWidget()
        find_object_layout = QFormLayout(self.find_object_widget)
        find_object_layout.setContentsMargins(0, 0, 0, 0)
        template_layout = QHBoxLayout()
        self.template_path_input = QLineEdit()
        self.template_path_input.setPlaceholderText(
            "Path to template image (.png, .jpg, etc.)")
        template_browse_button = QPushButton("Browse...")
        template_browse_button.clicked.connect(self._browse_template_image)
        template_layout.addWidget(self.template_path_input, 1)
        template_layout.addWidget(template_browse_button)
        find_object_layout.addRow("Template Image:", template_layout)
        self.confidence_spinbox = QDoubleSpinBox()
        self.confidence_spinbox.setRange(0.1, 1.0)
        self.confidence_spinbox.setSingleStep(0.05)
        self.confidence_spinbox.setValue(0.8)
        self.confidence_spinbox.setDecimals(2)
        find_object_layout.addRow("Min Confidence:", self.confidence_spinbox)
        self.obj_timeout_label = QLabel("Timeout:")
        self.obj_timeout_spinbox = QSpinBox()
        self.obj_timeout_spinbox.setRange(0, 3600000)
        self.obj_timeout_spinbox.setValue(0)
        self.obj_timeout_spinbox.setSuffix(" ms (0=Infinite)")
        find_object_layout.addRow(
            self.obj_timeout_label, self.obj_timeout_spinbox)
        self.obj_region_input = QLineEdit()
        self.obj_region_input.setPlaceholderText(
            "Optional: x,y,w,h (e.g., 100,150,300,200)")
        find_object_layout.addRow("Search Region:", self.obj_region_input)
        form_layout.addRow(self.find_object_widget)
        # LOOP_START options
        self.loop_start_widget = QWidget()
        loop_start_layout = QFormLayout(self.loop_start_widget)
        loop_start_layout.setContentsMargins(0, 0, 0, 0)
        self.loop_iterations_spinbox = QSpinBox()
        self.loop_iterations_spinbox.setRange(0, 99999)
        self.loop_iterations_spinbox.setValue(1)
        self.loop_iterations_spinbox.setSpecialValueText("Infinite")
        loop_start_layout.addRow(
            "Iterations (0=Infinite):", self.loop_iterations_spinbox)
        form_layout.addRow(self.loop_start_widget)
        # END_IF / LOOP_END options
        self.end_block_widget = QWidget()
        end_block_layout = QFormLayout(self.end_block_widget)
        end_block_layout.setContentsMargins(0, 0, 0, 0)
        self.end_block_label = QLabel("")
        self.loop_break_condition_label = QLabel("Break Loop If:")
        self.loop_break_condition_combo = QComboBox()
        self.loop_break_condition_combo.addItems(
            ["Never (Standard)", "Last IF Succeeded"])
        end_block_layout.addRow(self.end_block_label)
        end_block_layout.addRow(
            self.loop_break_condition_label, self.loop_break_condition_combo)
        form_layout.addRow(self.end_block_widget)

        layout.addLayout(form_layout)
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self._create_action)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        # --- Populate fields if editing ---
        if self.edit_mode and edit_action:
            self._populate_for_edit(edit_action)
            # Don't allow changing type when editing
            self.action_type_combo.setEnabled(False)
        else:
            # Populate position combo only if not editing (or if needed for default)
            if not self.available_positions:
                self.click_position_combo.addItem("No positions recorded!")
                self.click_position_combo.setEnabled(False)
            else:
                self.click_position_combo.addItems(self.available_positions)

        self._update_options()  # Set initial visibility

    def _populate_for_edit(self, action: Action):
        """Fills the dialog fields with data from an existing action."""
        self.action_type_combo.setCurrentText(action.type)
        details = action.details

        if action.type == ACTION_CLICK:
            pos_name = details.get("position_name")
            if pos_name == CLICK_TARGET_FOUND_OBJECT:
                self.click_target_combo.setCurrentText("Found Object")
            # Add Found Text later
            else:
                self.click_target_combo.setCurrentText("Position")
                # Populate position combo first
                if not self.available_positions: self.click_position_combo.addItem("No positions recorded!"); self.click_position_combo.setEnabled(False)
                else: self.click_position_combo.addItems(self.available_positions)
                self.click_position_combo.setCurrentText(pos_name or "") # Select existing pos

            self.click_offset_x_spinbox.setValue(details.get("offset_x", 0))
            self.click_offset_y_spinbox.setValue(details.get("offset_y", 0))
            self.click_button_combo.setCurrentText(details.get("button", "left"))
            self.click_type_combo.setCurrentText(details.get("click_type", "single"))

        elif action.type == ACTION_WAIT:
            self.wait_duration_spinbox.setValue(details.get("duration_ms", 1000))

        elif action.type in [ACTION_WAIT_FOR_OBJECT, ACTION_IF_OBJECT_FOUND, ACTION_CHECK_OBJECT_BREAK_LOOP]:
            self.template_path_input.setText(details.get("template_path", ""))
            self.confidence_spinbox.setValue(details.get("confidence", 0.8))
            region = details.get("region")
            self.obj_region_input.setText(",".join(map(str, region)) if region else "")
            if action.type == ACTION_WAIT_FOR_OBJECT:
                self.obj_timeout_spinbox.setValue(details.get("timeout_ms", 0))

        elif action.type == ACTION_LOOP_START:
            self.loop_iterations_spinbox.setValue(details.get("iterations", 1))

        elif action.type == ACTION_LOOP_END:
            break_cond = details.get("break_condition", "none")
            if break_cond == "last_if_success": self.loop_break_condition_combo.setCurrentText("Last IF Succeeded")
            else: self.loop_break_condition_combo.setCurrentText("Never (Standard)")

    def _browse_template_image(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Select Template Image", "", "Image Files (*.png *.jpg *.jpeg *.bmp);;All Files (*)")
        if filepath:
            self.template_path_input.setText(filepath)

    def _parse_region(self, region_str: str) -> Optional[Tuple[int, int, int, int]]:
        if not region_str.strip():
            return None
        try:
            parts = [int(p.strip()) for p in region_str.split(',')]
            if len(parts) == 4 and parts[2] > 0 and parts[3] > 0:
                return tuple(parts)
            else:
                raise ValueError(
                    "Region must have 4 positive numbers (x, y, width, height).")
        except Exception as e:
            raise ValueError(f"Invalid region format: {e}")

    def _update_click_options(self):
        is_pos_target = self.click_target_combo.currentText() == "Position"
        is_found_target = not is_pos_target
        self.click_position_label.setVisible(is_pos_target)
        self.click_position_combo.setVisible(is_pos_target)
        self.click_offset_label.setVisible(is_found_target)
        self.click_offset_x_spinbox.setVisible(is_found_target)
        self.click_offset_y_spinbox.setVisible(is_found_target)
        self._update_ok_button_state()

    def _update_options(self):
        selected_type = self.action_type_combo.currentText()
        is_click = selected_type == ACTION_CLICK
        is_wait = selected_type == ACTION_WAIT
        is_wait_obj = selected_type == ACTION_WAIT_FOR_OBJECT
        is_if_obj = selected_type == ACTION_IF_OBJECT_FOUND
        is_check_break = selected_type == ACTION_CHECK_OBJECT_BREAK_LOOP
        is_find_obj = is_wait_obj or is_if_obj or is_check_break
        is_loop_start = selected_type == ACTION_LOOP_START
        is_end_if = selected_type == ACTION_END_IF
        is_loop_end = selected_type == ACTION_LOOP_END
        is_end_block = is_end_if or is_loop_end

        self.click_options_widget.setVisible(is_click)
        self.wait_options_widget.setVisible(is_wait)
        self.find_object_widget.setVisible(is_find_obj)
        self.loop_start_widget.setVisible(is_loop_start)
        self.end_block_widget.setVisible(is_end_block)

        # Show/hide timeout only for WAIT_FOR_OBJECT
        self.obj_timeout_label.setVisible(is_wait_obj)
        self.obj_timeout_spinbox.setVisible(is_wait_obj)

        # Show/hide break condition only for LOOP_END
        self.loop_break_condition_label.setVisible(is_loop_end)
        self.loop_break_condition_combo.setVisible(is_loop_end)

        # Set label for END block
        if is_end_if:
            self.end_block_label.setText("Marks the end of an IF block.")
        elif is_loop_end:
            self.end_block_label.setText("Marks the end of a LOOP block.")
        else:
            self.end_block_label.setText("")  # Clear if not end block

        if is_click:
            self._update_click_options()
        else:
            self._update_ok_button_state()

        if hasattr(self, 'template_path_input'):
            self.template_path_input.textChanged.connect(
                self._update_ok_button_state)

    def _update_ok_button_state(self):
        ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        if not ok_button:
            return
        selected_type = self.action_type_combo.currentText()
        can_accept = True
        if selected_type == ACTION_CLICK:
            is_pos_target = self.click_target_combo.currentText() == "Position"
            if is_pos_target and not self.available_positions:
                can_accept = False
        elif selected_type in [ACTION_WAIT_FOR_OBJECT, ACTION_IF_OBJECT_FOUND, ACTION_CHECK_OBJECT_BREAK_LOOP]:
            can_accept = bool(self.template_path_input.text())
        elif selected_type in [ACTION_WAIT, ACTION_END_IF, ACTION_LOOP_START, ACTION_LOOP_END]:
            pass
        else:
            can_accept = False
        ok_button.setEnabled(can_accept)

    def _create_action(self):
        selected_type = self.action_type_combo.currentText()
        try:
            if selected_type == ACTION_CLICK:
                click_target = self.click_target_combo.currentText().lower().replace(" ", "_")
                pos_name = None
                if click_target == "position":
                    pos_name = self.click_position_combo.currentText()
                self.action_data = Action.click(position_name=pos_name, button=self.click_button_combo.currentText(), click_type=self.click_type_combo.currentText(
                ), offset_x=self.click_offset_x_spinbox.value(), offset_y=self.click_offset_y_spinbox.value(), click_target=click_target)
            elif selected_type == ACTION_WAIT:
                self.action_data = Action.wait(
                    duration_ms=self.wait_duration_spinbox.value())
            elif selected_type == ACTION_WAIT_FOR_OBJECT:
                template = self.template_path_input.text().strip()
                region = self._parse_region(self.obj_region_input.text())
                timeout = self.obj_timeout_spinbox.value()
                if not template or not os.path.exists(template):
                    raise ValueError(
                        f"Template image path invalid or not found: '{template}'")
                self.action_data = Action.wait_for_object(template_path=template, confidence=self.confidence_spinbox.value(
                ), region=region, timeout_ms=timeout if timeout > 0 else None)
            elif selected_type == ACTION_IF_OBJECT_FOUND:
                template = self.template_path_input.text().strip()
                region = self._parse_region(self.obj_region_input.text())
                if not template or not os.path.exists(template):
                    raise ValueError(
                        f"Template image path invalid or not found: '{template}'")
                self.action_data = Action.if_object_found(
                    template_path=template, confidence=self.confidence_spinbox.value(), region=region)
            elif selected_type == ACTION_CHECK_OBJECT_BREAK_LOOP:
                template = self.template_path_input.text().strip()
                region = self._parse_region(self.obj_region_input.text())
                if not template or not os.path.exists(template):
                    raise ValueError(
                        f"Template image path invalid or not found: '{template}'")
                self.action_data = Action.check_object_break_loop(
                    template_path=template, confidence=self.confidence_spinbox.value(), region=region)
            elif selected_type == ACTION_LOOP_START:
                self.action_data = Action.loop_start(
                    iterations=self.loop_iterations_spinbox.value())
            elif selected_type == ACTION_LOOP_END:
                break_cond_text = self.loop_break_condition_combo.currentText()
                break_cond = "none"
                if break_cond_text == "Last IF Succeeded":
                    break_cond = "last_if_success"
                self.action_data = Action.loop_end(break_condition=break_cond)
            elif selected_type == ACTION_END_IF:
                self.action_data = Action.end_if()
            else:
                raise NotImplementedError(
                    f"Action type '{selected_type}' creation logic is missing.")
            self.accept()
        except Exception as e:
            QMessageBox.warning(self, "Invalid Input", str(e))
            self.action_data = None

    def get_action(self) -> Optional[Action]:
        return self.action_data
