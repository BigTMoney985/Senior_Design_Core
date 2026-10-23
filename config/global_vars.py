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

# ==================== USER OPTIONS ====================
@dataclass
class user_opts_class:
    run_mode: str = 'plot'  # Default run mode is 'plot'
    legend: bool = True # Has Materials Legend on the plot
    fuel_choice: str = 'u3si2'  # options: 'u3si2', 'u3o8', 'u10mo'
user_opts = user_opts_class()

@dataclass
class reflector_class:
    be_thickness = 15 # beryllium thickness
    water_gap = 0.05 # gap dist of water between control element and fuel or reflector

    #INTERNAL VARS
    r_inner: float | None = None
    r_outer: float | None = None
reflector = reflector_class()

@dataclass
class control_blade_class:
    blade_thickness = 0.2 # Thickness of each blade, central blades are two in series, so thickness will be double
    central_blade_num = 6 #number of blades in the central area
    percent_semi_abs = 0.125 #The proportion of the blade that can absorb some, but not many, neutrons.

    #INTERNAL VARS
    rad_out_central: float | None = None # Will be changed once blades are initialized
    rad_in_central: float | None = None # radius of the control blades inner
control_blade = control_blade_class()

@dataclass
class fluxtrap_class:
    r_in: float = 4.0 # Inner radius of the flux trap
    # NOTE, this may need to be adjusted based on the specific flux trap design
fluxtrap = fluxtrap_class()

@dataclass
class fuel_class:
    temp_var: float = 1.0
    meat_thickness: float = 0.08 # Thickness of the fuel meat in cm
    clad_thickness: float = in_to_cm(0.015) #thickness of the clad
    nominal_dist: float = 0.09 #Distance between the outer clad of one plate and the inner clad of the next plate
    fuel_inner: float = 4 # Inner radius of the fuel element
    plate_num: int = 18 #number of fuel plates in the fuel element
    height: float = 150 # How tall the elements are?

    #PLACEHOLDER VALUE ============
    fuel_outer: float = 67
fuel = fuel_class()

@dataclass
class vessel_class:
    temp_var: float = 1.0
vessel = vessel_class()

# EVERYTHING BELOW HERE IS NOT NECESSARILY USER-DEFINED, BUT IS USED INTERNALLY FOR GEOMETRY AND MATERIAL DEFINITIONS

@dataclass
class materials_class:
    material_dict: None | dict = None

    def set_materials(self, material_dict: dict) -> None:
        """Set the material dictionary."""
        self.material_dict = material_dict

    def get_materials(self):
        if self.material_dict is None:
            raise ValueError('Material Dict is not assigned')
        else:
            return self.material_dict
materials = materials_class()

@dataclass
class graveyard_class:
    graveyard_r: float = 150

    def __init__(self):
        grave_cyl = openmc.ZCylinder(r=self.graveyard_r, boundary_type='vacuum')
        grave_top = openmc.ZPlane(z0=(2*fuel.height), boundary_type='vacuum')
        grave_bot = openmc.ZPlane(z0=-fuel.height, boundary_type='vacuum')

        fueled_top = openmc.ZPlane(z0=(fuel.height), boundary_type='vacuum')
        fueled_bot = openmc.ZPlane(z0=0, boundary_type='vacuum')

        self.graveyard_region = -grave_cyl & +grave_bot & -grave_top
        self.fueled_region = -fueled_top & +fueled_bot & -grave_cyl
graveyard = graveyard_class()




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

@dataclass
class _element_ring_class:
    universe: None | openmc.Universe = None

    def set_universe(self, universe: openmc.Universe) -> None:
        """Set the universe for the fuel element ring."""
        if universe is None:
            raise ValueError("Universe cannot be None. Please provide a valid openmc.Universe object.")
        self.universe = universe

    def clear_universe(self) -> None:
        """Clear the universe."""
        self.universe = None
element_ring_class = _element_ring_class()