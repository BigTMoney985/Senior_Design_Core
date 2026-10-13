"""
config/global_vars.py
Central registry for global dimensions, material conditions, 
and shared surface primitives.
"""
from dataclasses import dataclass
import openmc

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
    meat_thickness: float = 0.13 # Thickness of the fuel meat in cm
    clad_thickness: float = in_to_cm(0.015)
    nominal_dist: float = 0.15 #Distance between the outer clad of one plate and the inner clad of the next plate
    fuel_inner: float = 8 # Inner radius of the fuel element
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


# MORE TECHNICAL VARIABLES FOR FUEL ELEMENTS
# THESE ARE NOT USER-DEFINED, BUT ARE USED INTERNALLY FOR GEOMETRY AND MATERIAL DEFINITIONS
@dataclass
class _element_cell_class:
    region: None | openmc.Region = None
    universe: None | openmc.Universe = None
    default_cell: None | openmc.Cell = None

    def set_vars(self, region: openmc.Region, universe: openmc.Universe) -> None:
        """Set the region and universe for the fuel element cell."""
        self.region = region

        if universe is None:
            raise ValueError("Universe cannot be None. Please provide a valid openmc.Universe object.")
        self.universe = universe

        if self.default_cell is None:
            self.default_cell = openmc.Cell(region=self.region, fill=self.universe)

    def clear_cell(self) -> None:
        """Clear the default cell."""
        self.default_cell = None
element_cell_class = _element_cell_class()