import openmc 
import config.global_vars as gv

class WaterGeometry:
    def __init__(self) -> None:
        self.water_mat = gv.materials.material_dict['water'] # type: ignore
        self.fuel_top = openmc.ZPlane(z0=gv.fuel.height)
        self.fuel_bot = openmc.ZPlane(z0=0.0)

    def create_surfaces(self):
        """Surfaces shared across outer reflector and water boundaries."""
        be_in = openmc.ZCylinder(r=gv.reflector.r_inner) # type: ignore
        be_out = openmc.ZCylinder(r=gv.reflector.r_outer) # type: ignore

        return {
            'be_in': be_in,
            'be_out': be_out,
        }

    def create_water_cells_around(self, surf_dict):
        # 1. Above Beryllium reflector
        above_be_cell = openmc.Cell(
            name='above central be water',
            fill=self.water_mat,
            region=+surf_dict['be_in'] & -surf_dict['be_out'] & +self.fuel_top & gv.graveyard.graveyard_region
        )

        # 2. Below Beryllium reflector
        below_be_cell = openmc.Cell(
            name='below central be water',
            fill=self.water_mat,
            region=+surf_dict['be_in'] & -surf_dict['be_out'] & -self.fuel_bot & gv.graveyard.graveyard_region
        )

        # 3. Outside Beryllium reflector out to vacuum boundary
        outside_be_cell = openmc.Cell(
            name='outside central be water',
            fill=self.water_mat,
            region=+surf_dict['be_out'] & gv.graveyard.graveyard_region
        )

        return [above_be_cell, below_be_cell, outside_be_cell]
        


