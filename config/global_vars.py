"""
config/global_vars.py
Central registry for global dimensions, material conditions, 
and shared surface primitives.
"""
from dataclasses import dataclass

def in_to_cm(inches: float) -> float:
    """Convert inches to centimeters."""
    return inches * 2.54

@dataclass
class fluxtrap_class:
    r_in: float = 4.0 # Inner radius of the flux trap
    # NOTE, this may need to be adjusted based on the specific flux trap design
fluxtrap = fluxtrap_class()

@dataclass
class fuel_class:
    temp_var: float = 1.0
    meat_thickness: float = 0.13
    clad_thickness: float = in_to_cm(0.015)
    nominal_dist: float = 0.15
    fuel_inner: float = 8
    plate_num: int = 30
    fuel_outer: float = (meat_thickness + 2 * clad_thickness + nominal_dist) * plate_num - nominal_dist
fuel = fuel_class()

@dataclass
class vessel_class:
    temp_var: float = 1.0
vessel = vessel_class()

@dataclass
class materials_class:
    material_dict: None | dict = None

    def set_materials(self, material_dict: dict) -> None:
        """Set the material dictionary."""
        self.material_dict = material_dict
materials = materials_class()

@dataclass
class user_opts_class:
    run_mode: str = 'plot'  # Default run mode is 'plot'
    fuel_choice: str = 'u3si2'  # Default fuel choice is 'u3si2'
user_opts = user_opts_class()