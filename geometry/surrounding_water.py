import openmc 
import config.global_vars as gv

class WaterGeometry:
    def __init__(self) -> None:
        self.r_central = gv.fuel.fuel_inner
        self.r_outer = gv.fuel.fuel_outer
        self.water_mat = gv.materials.material_dict['water'] # type: ignore

    def create_surfaces(self):
        """Surfaces shared across water and fuel boundaries."""
        inner_cyl = openmc.ZCylinder(r=self.r_central)
        outer_cyl = openmc.ZCylinder(r=self.r_outer)
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
            name="outer_water",
            fill=self.water_mat,
            region=+outer_cyl & gv.graveyard.graveyard_region
        )

        return [central_cell, outer_cell]
        


