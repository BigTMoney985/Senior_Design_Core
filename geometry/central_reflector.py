import openmc 
import config.global_vars as gv

class be_reflector:
    def __init__(self) -> None:
        if gv.control_blade.rad_out_central is not None:
            self.r_inner = gv.reflector.water_gap + gv.control_blade.rad_out_central
        self.r_outer = self.r_inner + gv.reflector.be_thickness
        self.be_met = gv.materials.material_dict['be_metal'] # type: ignore

    def create_surfaces(self):
        """Surfaces shared across water and fuel boundaries."""
        inner_cyl = openmc.ZCylinder(r=self.r_inner)
        outer_cyl = openmc.ZCylinder(r=self.r_outer)
        return inner_cyl, outer_cyl

    def create_be_cells(self, inner_cyl, outer_cyl):

        # 1. Right outside of fuel boundary
        outer_cell = openmc.Cell(
            name="be_reflector",
            fill=self.be_met,
            region=+inner_cyl & -outer_cyl & gv.graveyard.graveyard_region
        )

        return outer_cell



