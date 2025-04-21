# core/scenario.py

import json
import os
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field

# --- Action Type Constants ---
ACTION_CLICK = "CLICK"
ACTION_WAIT = "WAIT"
ACTION_WAIT_FOR_OBJECT = "WAIT_FOR_OBJECT"
ACTION_IF_OBJECT_FOUND = "IF_OBJECT_FOUND"
ACTION_END_IF = "END_IF"
ACTION_LOOP_START = "LOOP_START"
ACTION_LOOP_END = "LOOP_END"
ACTION_CHECK_OBJECT_BREAK_LOOP = "CHECK_OBJECT_BREAK_LOOP" # Added
# ACTION_WAIT_FOR_TEXT = "WAIT_FOR_TEXT" # Add later
# ACTION_IF_TEXT_FOUND = "IF_TEXT_FOUND" # Add later

# --- Update ACTION_TYPES list ---
ACTION_TYPES = [
    ACTION_CLICK,
    ACTION_WAIT,
    ACTION_WAIT_FOR_OBJECT,
    ACTION_IF_OBJECT_FOUND,
    ACTION_LOOP_START,
    ACTION_LOOP_END,
    ACTION_CHECK_OBJECT_BREAK_LOOP, # Added
    ACTION_END_IF,
    # ACTION_WAIT_FOR_TEXT, # Add later
    # ACTION_IF_TEXT_FOUND, # Add later
]

# Special value for position_name when clicking on found object/text
CLICK_TARGET_FOUND_OBJECT = "@found_object"
# CLICK_TARGET_FOUND_TEXT = "@found_text" # Add later

# --- Position Dataclass ---
@dataclass
class Position:
    """Represents a named coordinate relative to a target window."""
    name: str
    relative_x: int
    relative_y: int

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "relative_x": self.relative_x, "relative_y": self.relative_y}

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'Position':
        if not all(k in data for k in ("name", "relative_x", "relative_y")):
            raise ValueError("Invalid position data dictionary (missing relative coords)")
        return Position(
            name=str(data["name"]),
            relative_x=int(data["relative_x"]),
            relative_y=int(data["relative_y"])
        )

# --- Action Dataclass ---
@dataclass
class Action:
    """Represents a single action in a scenario."""
    type: str
    details: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def click(
        position_name: Optional[str] = None,
        button: str = 'left',
        click_type: str = 'single',
        offset_x: int = 0,
        offset_y: int = 0,
        click_target: str = "position" # "position", "found_object", "found_text"
        ):
        """Creates a CLICK action."""
        if click_target == "found_object":
            position_name = CLICK_TARGET_FOUND_OBJECT
        # elif click_target == "found_text": # Add later
        #      position_name = CLICK_TARGET_FOUND_TEXT
        elif not position_name:
             raise ValueError("Position name must be provided if click_target is 'position'.")

        return Action(type=ACTION_CLICK, details={
            "position_name": position_name, # Name, "@found_object", or "@found_text"
            "button": button, "click_type": click_type,
            "offset_x": offset_x, "offset_y": offset_y,
        })

    @staticmethod
    def wait(duration_ms: int):
        """Creates a WAIT action."""
        if duration_ms <= 0: raise ValueError("Wait duration must be positive.")
        return Action(type=ACTION_WAIT, details={"duration_ms": duration_ms})

    @staticmethod
    def wait_for_object(template_path: str, confidence: float = 0.8, region: Optional[Tuple[int, int, int, int]] = None, timeout_ms: Optional[int] = None):
        """Creates a WAIT_FOR_OBJECT action."""
        if not 0.0 <= confidence <= 1.0: raise ValueError("Confidence must be between 0.0 and 1.0")
        if timeout_ms is not None and timeout_ms <= 0: raise ValueError("Timeout must be positive if specified.")
        return Action(type=ACTION_WAIT_FOR_OBJECT, details={"template_path": template_path, "confidence": confidence, "region": region, "timeout_ms": timeout_ms})

    @staticmethod
    def if_object_found(template_path: str, confidence: float = 0.8, region: Optional[Tuple[int, int, int, int]] = None):
        """Creates an IF_OBJECT_FOUND action."""
        if not 0.0 <= confidence <= 1.0: raise ValueError("Confidence must be between 0.0 and 1.0")
        return Action(type=ACTION_IF_OBJECT_FOUND, details={"template_path": template_path, "confidence": confidence, "region": region})

    @staticmethod
    def end_if():
        """Creates an END_IF action."""
        return Action(type=ACTION_END_IF, details={})

    @staticmethod
    def loop_start(iterations: int):
        """Creates a LOOP_START action. iterations=0 means infinite loop."""
        if iterations < 0: raise ValueError("Loop iterations cannot be negative.")
        return Action(type=ACTION_LOOP_START, details={"iterations": iterations})

    @staticmethod
    def loop_end(break_condition: str = "none"):
        """
        Creates a LOOP_END action.
        Args:
            break_condition: "none", "last_if_success"
        """
        valid_conditions = ["none", "last_if_success"] # Add more later
        if break_condition not in valid_conditions:
            raise ValueError(f"Invalid loop break condition: {break_condition}")
        return Action(type=ACTION_LOOP_END, details={"break_condition": break_condition})

    @staticmethod
    def check_object_break_loop(template_path: str, confidence: float = 0.8, region: Optional[Tuple[int, int, int, int]] = None):
        """Creates a CHECK_OBJECT_BREAK_LOOP action."""
        if not 0.0 <= confidence <= 1.0: raise ValueError("Confidence must be between 0.0 and 1.0")
        return Action(type=ACTION_CHECK_OBJECT_BREAK_LOOP, details={
            "template_path": template_path,
            "confidence": confidence,
            "region": region
        })

    # --- Serialization/Deserialization ---
    def to_dict(self) -> Dict[str, Any]:
        """Converts action to a dictionary for saving."""
        return {"type": self.type, "details": self.details}

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'Action':
        """Creates an action from a dictionary (loaded from file)."""
        if "type" not in data:
            raise ValueError("Invalid action data dictionary: missing 'type'")
        # Basic validation for region format if needed
        if data.get("details", {}).get("region") is not None:
            region = data["details"]["region"]
            if not isinstance(region, list) or len(region) != 4 or not all(isinstance(n, int) for n in region):
                 print(f"Warning: Invalid region format in loaded action: {region}. Setting region to None.")
                 data["details"]["region"] = None # Correct invalid format
        return Action(type=str(data["type"]), details=data.get("details", {}))


# --- Scenario Dataclass ---
@dataclass
class Scenario:
    """Holds all data for a complete automation scenario."""
    scenario_name: str = "Untitled Scenario"
    target_process_name: Optional[str] = None
    require_focus: bool = False
    positions: List[Position] = field(default_factory=list)
    actions: List[Action] = field(default_factory=list)
    is_modified: bool = field(default=False, compare=False, repr=False)
    filepath: Optional[str] = field(default=None, compare=False, repr=False)
    # --- Add Global Loop Setting ---
    global_repetitions: int = 1 # Default to run once

    def _mark_modified(self):
        """Internal helper to mark the scenario as modified."""
        if not self.is_modified:
            self.is_modified = True

    def set_name(self, name: str):
        """Sets the scenario name and marks as modified."""
        if self.scenario_name != name:
            self.scenario_name = name
            self._mark_modified()

    def set_target_process(self, name: Optional[str]):
        """Sets the target process name and marks as modified."""
        if self.target_process_name != name:
            self.target_process_name = name
            self._mark_modified()

    def set_require_focus(self, required: bool):
        """Sets the require focus flag and marks as modified."""
        if self.require_focus != required:
            self.require_focus = required
            self._mark_modified()

    # --- Add setter for global repetitions ---
    def set_global_repetitions(self, repetitions: int):
        if repetitions < 0: repetitions = 0 # Treat negative as infinite
        if self.global_repetitions != repetitions:
            self.global_repetitions = repetitions
            self._mark_modified()

    def add_position(self, name: str, relative_x: int, relative_y: int):
        """Adds a position with relative coordinates."""
        if self.get_position_by_name(name):
            raise ValueError(f"Position name '{name}' already exists.")
        self.positions.append(Position(name=name, relative_x=relative_x, relative_y=relative_y))
        self._mark_modified()

    def remove_position_by_name(self, name: str):
        """Removes a position by name."""
        initial_len = len(self.positions)
        self.positions = [p for p in self.positions if p.name != name]
        if len(self.positions) < initial_len:
            self._mark_modified()

    def get_position_by_name(self, name: str) -> Optional[Position]:
        """Finds a position by its name."""
        for pos in self.positions:
            if pos.name == name:
                return pos
        return None

    def get_position_names(self) -> List[str]:
        """Returns a list of all position names."""
        return [p.name for p in self.positions]

    def add_action(self, action: Action, index: Optional[int] = None):
        """Adds an action, optionally at a specific index."""
        if index is None or index < 0 or index >= len(self.actions):
            self.actions.append(action)
        else:
            self.actions.insert(index, action)
        self._mark_modified()

    def remove_action(self, index: int):
        """Removes an action at a specific index."""
        if 0 <= index < len(self.actions):
            del self.actions[index]
            self._mark_modified()

    def to_dict(self) -> Dict[str, Any]:
        """Converts the scenario to a dictionary for saving."""
        return {
            "scenario_name": self.scenario_name,
            "target_process": self.target_process_name,
            "require_focus": self.require_focus,
            "global_repetitions": self.global_repetitions,            
            "positions": [p.to_dict() for p in self.positions],
            "actions": [a.to_dict() for a in self.actions],
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'Scenario':
        """Creates a scenario from a dictionary (loaded from file)."""
        try:
            name = data.get("scenario_name", "Untitled Scenario")
            scenario = Scenario(
                scenario_name=name,
                target_process_name=data.get("target_process"),
                require_focus=data.get("require_focus", False),
                global_repetitions=int(data.get("global_repetitions", 1)) # Added
            )
            scenario.positions = [Position.from_dict(p_data) for p_data in data.get("positions", [])]
            scenario.actions = [Action.from_dict(a_data) for a_data in data.get("actions", [])]
            scenario.is_modified = False # Loaded scenario is initially unmodified
            return scenario
        except (KeyError, ValueError, TypeError) as e:
            print(f"Error parsing scenario data: {e}")
            raise ValueError(f"Invalid scenario data format: {e}")

    def save_to_file(self, filepath: str):
        """Saves the scenario to a JSON file."""
        try:
            # Ensure the scenario name matches the filename if default
            base_name = os.path.splitext(os.path.basename(filepath))[0]
            if self.scenario_name == "Untitled Scenario" or not self.scenario_name:
                 self.scenario_name = base_name

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.to_dict(), f, indent=4)
            self.filepath = filepath
            self.is_modified = False # Mark as saved
        except IOError as e:
            print(f"Error saving scenario to {filepath}: {e}")
            raise

    @staticmethod
    def load_from_file(filepath: str) -> 'Scenario':
        """Loads a scenario from a JSON file."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            scenario = Scenario.from_dict(data)
            scenario.filepath = filepath # Store the path
            scenario.is_modified = False # Mark as unmodified after load
            return scenario
        except (IOError, json.JSONDecodeError, ValueError) as e:
            print(f"Error loading scenario from {filepath}: {e}")
            raise