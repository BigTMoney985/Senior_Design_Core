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
        fuel_outer = openmc.ZCylinder(r=gv.fuel.fuel_outer)

        control_inner = openmc.ZCylinder(r=self.control_in) #type: ignore
        control_outer = openmc.ZCylinder(r=self.control_out) #type: ignore

        be_in = openmc.ZCylinder(r=gv.reflector.r_inner) #type: ignore
        be_out = openmc.ZCylinder(r=gv.reflector.r_outer) #type: ignore

        return inner_cyl, outer_cyl

    def create_water_cells(self, inner_cyl, outer_cyl):
        # 1. Flux trap / central cavity
        central_cell = openmc.Cell(
            name="central_water",
            fill=self.water_mat,
            region=-inner_cyl & gv.graveyard.graveyard_region
        )

        # 2. Outside water reflector up to the graveyard boundary
        outer_cell = openmc.Cell(
            name="water_before_control",
            fill=self.water_mat,
            region=+outer_cyl & gv.graveyard.graveyard_region
        )

        return [central_cell, outer_cell]
        


