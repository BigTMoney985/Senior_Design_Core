import openmc 
import numpy as np
from config.global_vars import fuel, fluxtrap
#from materials.material_defs import create_materials
from geometry.fuel_element import FuelElementGeometry

class FuelRingGeometry:
    def __init__(self):
        self.element_base = FuelElementGeometry().create_fuel_cell()  # This will be set when create_fuel_ring is called
        self.elements_ring = 8  # Number of elements in a ring (45-degree angles)
        self.ring_universe = openmc.Universe()  # Universe to hold the ring of fuel elements

    def create_fuel_ring(self):

        for i in range(self.elements_ring):
            angle = i * (360 / self.elements_ring)

            if i == 0:
                # For the first element, we can just use the base element without rotation
                rotated_element = self.element_base

            else:
                # For subsequent elements, we need to rotate the base element
                rotated_element = openmc.Cell(region=self.element_base.region, fill=self.element_base.fill)
                rotated_element.rotation = (0, 0, np.radians(angle))  # Rotate around the z-axis

            rotated_element.id = self.element_base.id * 100 + i  # Assign a unique ID to each rotated element
            self.ring_universe.add_cell(rotated_element)

        return self.ring_universe

    def create_fuel_ring_geometry(self) -> openmc.Geometry:
        ring_universe = self.create_fuel_ring()
        geom = openmc.Geometry(ring_universe)
        return geom


