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
    compute_choice: str = 'hpc' # options: 'local', 'hpc'
    legend: bool = True     # Has Materials Legend on the plot
    fuel_choice: str = 'u3si2'  # options: 'u3si2', 'u3o8', 'u10mo'
user_opts = user_opts_class()

@dataclass
class reflector_class:
    be_thickness: float = 15.0  # beryllium thickness
    water_gap: float = 0.1     # gap dist of water between control element and fuel or reflector

    # INTERNAL VARS
    r_inner: float | None = None
    r_outer: float | None = None
reflector = reflector_class()

@dataclass
class control_blade_class:
    blade_thickness: float = 0.2    # Thickness of each blade layer
    central_blade_num: int = 6      # Number of blades in the central area / per 360 deg
    percent_semi_abs: float = 0.125 # Proportion of blade that is semi-absorber (SS-304)


    # INTERNAL VARS (Outer lobe blades & overall core outer radius)
    rad_out_central: float | None = None
    rad_in_central: float | None = None
control_blade = control_blade_class()

@dataclass
class fluxtrap_class:
    r_in: float = 3.0  # Inner radius of each lobe flux trap and inscribed central cavity
fluxtrap = fluxtrap_class()

@dataclass
class fuel_class:
    temp_var: float = 1.0
    meat_thickness: float = 0.08
    clad_thickness: float = in_to_cm(0.015)
    nominal_dist: float = 0.08
    fuel_inner: float = 3.0 # from 4.0
    plate_num: int = 18
    height: float = 150.0

    # Updated dynamically when FuelElementGeometry.define_plates() runs (~8.3416 cm)
    fuel_outer: float = 8.3416
fuel = fuel_class()

@dataclass
class vessel_class:
    temp_var: float = 1.0
vessel = vessel_class()

@dataclass
class materials_class:
    material_dict: dict[str, openmc.Material] | None = None

    def set_materials(self, material_dict: dict[str, openmc.Material]) -> None:
        """Set the material dictionary."""
        self.material_dict = material_dict

    def get_materials(self) -> dict[str, openmc.Material]:
        if self.material_dict is None:
            raise ValueError('Material Dict is not assigned')
        return self.material_dict
materials = materials_class()

@dataclass
class graveyard_class:
    graveyard_r: float = 150.0

    def __init__(self):
        grave_cyl = openmc.ZCylinder(r=self.graveyard_r, boundary_type='vacuum')
        grave_top = openmc.ZPlane(z0=(2 * fuel.height), boundary_type='vacuum')
        grave_bot = openmc.ZPlane(z0=-fuel.height, boundary_type='vacuum')

        fueled_top = openmc.ZPlane(z0=fuel.height)
        fueled_bot = openmc.ZPlane(z0=0.0)

        self.graveyard_region = -grave_cyl & +grave_bot & -grave_top
        self.fueled_region = -fueled_top & +fueled_bot & -grave_cyl
graveyard = graveyard_class()

@dataclass
class _element_cell_class:
    region: None | openmc.Region = None
    universe: None | openmc.Universe = None
    default_cell: None | openmc.Cell = None

    def set_vars(self, region: openmc.Region, universe: openmc.Universe) -> None:
        self.region = region
        if universe is None:
            raise ValueError("Universe cannot be None.")
        self.universe = universe
        if self.default_cell is None:
            self.default_cell = openmc.Cell(region=self.region, fill=self.universe)

    def clear_cell(self) -> None:
        self.default_cell = None
element_cell_class = _element_cell_class()

@dataclass
class _element_ring_class:
    universe: None | openmc.Universe = None

    def set_universe(self, universe: openmc.Universe) -> None:
        if universe is None:
            raise ValueError("Universe cannot be None.")
        self.universe = universe

    def clear_universe(self) -> None:
        self.universe = None
element_ring_class = _element_ring_class()