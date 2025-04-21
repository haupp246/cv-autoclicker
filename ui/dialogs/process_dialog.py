# ui/dialogs/process_dialog.py

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QListWidget, QLineEdit, QPushButton, QDialogButtonBox,
    QListWidgetItem, QApplication
)
from PyQt6.QtCore import Qt
from system.process_utils import get_running_processes # Import the function

class ProcessDialog(QDialog):
    """Dialog to select a running process."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Target Process")
        self.setMinimumSize(400, 500)

        self.selected_process_name = None
        self._all_processes = [] # Store the full list (name, pid)

        layout = QVBoxLayout(self)

        # Filter Input
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter processes...")
        self.filter_input.textChanged.connect(self._filter_list)
        layout.addWidget(self.filter_input)

        # Process List
        self.process_list_widget = QListWidget()
        self.process_list_widget.itemDoubleClicked.connect(self.accept) # Double-click accepts
        layout.addWidget(self.process_list_widget)

        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self._populate_list()

    def _populate_list(self):
        """Fetches processes and populates the list widget."""
        self.process_list_widget.clear()
        self._all_processes = get_running_processes()

        if not self._all_processes:
             # Handle case where process fetching failed
             error_item = QListWidgetItem("Error fetching processes.")
             error_item.setForeground(Qt.GlobalColor.red)
             self.process_list_widget.addItem(error_item)
             # Disable OK button maybe? Or rely on user cancelling.
             return

        for name, pid in self._all_processes:
            item = QListWidgetItem(f"{name} (PID: {pid})")
            # Store the actual process name in the item's data
            item.setData(Qt.ItemDataRole.UserRole, name)
            self.process_list_widget.addItem(item)

        # Select the first item if list is not empty
        if self._all_processes:
            self.process_list_widget.setCurrentRow(0)


    def _filter_list(self):
        """Filters the displayed list based on the filter input."""
        filter_text = self.filter_input.text().lower()
        self.process_list_widget.clear() # Clear previous filter results

        if not self._all_processes:
             # Handle case where process fetching failed initially
             error_item = QListWidgetItem("Error fetching processes.")
             error_item.setForeground(Qt.GlobalColor.red)
             self.process_list_widget.addItem(error_item)
             return

        found = False
        for name, pid in self._all_processes:
            if filter_text in name.lower():
                item = QListWidgetItem(f"{name} (PID: {pid})")
                item.setData(Qt.ItemDataRole.UserRole, name)
                self.process_list_widget.addItem(item)
                if not found: # Select the first match
                    self.process_list_widget.setCurrentItem(item)
                    found = True

        # If filter is empty, show all (already handled by looping _all_processes)
        # If filter has text but no matches, list will be empty.


    def accept(self):
        """Sets the selected process name when OK is clicked."""
        current_item = self.process_list_widget.currentItem()
        if current_item:
            # Retrieve the stored process name
            self.selected_process_name = current_item.data(Qt.ItemDataRole.UserRole)
            if self.selected_process_name: # Ensure data was stored correctly
                 super().accept() # Close dialog with accepted state
            else:
                 # Handle case where data is missing (shouldn't happen often)
                 print("Error: No process name data found for selected item.")
                 # Optionally show a message box
                 super().reject() # Or reject if data is bad
        else:
            # Handle case where nothing is selected (e.g., filter yields no results)
            # Maybe show a small warning, or just do nothing / reject
            print("No process selected.")
            super().reject() # Reject if nothing valid is selected


    def get_selected_process(self):
        """Returns the name of the selected process."""
        return self.selected_process_name

# Example usage (for testing the dialog directly)
if __name__ == '__main__':
    import sys
    app = QApplication(sys.argv)
    dialog = ProcessDialog()
    if dialog.exec(): # exec() shows the dialog modally
        print(f"Selected Process: {dialog.get_selected_process()}")
    else:
        print("Dialog cancelled.")
    sys.exit()