import openmc 
import config.global_vars as gv

class WaterGeometry:
    def __init__(self) -> None:
        self.r_central = gv.fuel.fuel_inner
        self.r_outer = gv.fuel.fuel_outer
        self.water_mat = gv.materials.material_dict['water'] # type: ignore

        self.control_in = gv.control_blade.rad_in_central
        self.control_out = gv.control_blade.rad_out_central
        

    def create_surfaces(self):
        """Surfaces shared across water and fuel boundaries."""
        inner_cyl = openmc.ZCylinder(r=self.r_central)
        outer_cyl = openmc.ZCylinder(r=self.r_outer)

        control_inner = openmc.ZCylinder(r=self.control_in) #type: ignore
        control_outer = openmc.ZCylinder(r=self.control_out) #type: ignore

        be_in = openmc.ZCylinder(r=gv.reflector.r_inner) #type: ignore
        be_out = openmc.ZCylinder(r=gv.reflector.r_outer) #type: ignore

        surf_dict = {
            'inner_cyl': inner_cyl,
            'outer_cyl': outer_cyl,
            'control_outer': control_outer,
            'control_inner': control_inner,
            'be_in': be_in,
            'be_out': be_out,
        }

        return surf_dict

    def create_water_cells_inner(self, surf_dict):
        # 1. Flux trap / central cavity
        central_cell = openmc.Cell(
            name="central_water",
            fill=self.water_mat,
            region=-surf_dict['inner_cyl'] & gv.graveyard.graveyard_region
        )

        # 2. Outside water reflector up to inner control rods
        in_blade_cell = openmc.Cell(
            name="water_before_control",
            fill=self.water_mat,
            region=+surf_dict['outer_cyl'] & gv.graveyard.graveyard_region & -surf_dict['control_inner']
        )

        # 3. Water reflector between blades and Be
        out_blade_cell = openmc.Cell(
           name="water_after_control",
            fill=self.water_mat,
            region=-surf_dict['be_in'] & gv.graveyard.graveyard_region & +surf_dict['control_outer']
        )

        # 4. Water reflector outside of Be
        out_be_cell = openmc.Cell(
            name="water_after_be",
            fill=self.water_mat,
            region=+surf_dict['be_out'] & gv.graveyard.graveyard_region
        )

        return [central_cell, in_blade_cell, out_blade_cell, out_be_cell]
        


