import openmc
import config.global_vars as gv

class central_blades:
    def __init__(self) -> None:
        self.r_inner = gv.reflector.water_gap + gv.fuel.fuel_outer
        self.r_midpoint = self.r_inner + gv.control_blade.blade_thickness
        self.r_out = self.r_midpoint + gv.control_blade.blade_thickness

    def create_surfaces(self):
        pass