import openmc
import config.global_vars as gv

from geometry.fuel_element import FuelElementGeometry

class lobe_3:
    def __init__(self) -> None:
        self.element_factory = FuelElementGeometry()
        self.base_universe = self.element_factory.create_fuel_universe()
        pass