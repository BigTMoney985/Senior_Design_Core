import openmc 
import config.global_vars as gv
from materials.material_defs import create_materials
from geometry.fuel_element import FuelElementGeometry
from geometry.fuel_ring import FuelRingGeometry

class WaterGeometry:
    def __init__(self) -> None:
        self.water_central = gv.fuel.fuel_inner
        self.water_outer = gv.fuel.fuel_outer
        self.water_mat = gv.materials.material_dict['water'] # type: ignore
        pass

    def central_water(self):

        central_water_reg = openmc.ZCylinder(r=self.water_central)
        central_water_cell = openmc.Cell(fill=self.water_mat, region=-central_water_reg)
        


