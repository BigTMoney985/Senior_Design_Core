import openmc 
import numpy as np
from config.global_vars import fuel, fluxtrap, element_ring_class, element_cell_class
#from materials.material_defs import create_materials
from geometry.fuel_element import FuelElementGeometry

class FuelRingGeometry:
    def __init__(self):
        self.element_factory = FuelElementGeometry()
        # Ensure universe is generated
        self.base_universe = self.element_factory.create_fuel_universe()
        
        self.elements_ring = 8
        self.wedge_deg = 360.0 / self.elements_ring

        # Radii matching the element bounds
        self.r_in = openmc.ZCylinder(r=self.element_factory.inner_thickness)
        self.r_out = openmc.ZCylinder(r=self.element_factory.outer_thickness)

    def create_fuel_ring(self) -> openmc.Universe:
        ring_universe = openmc.Universe()

        for i in range(self.elements_ring):
            angle_start = i * self.wedge_deg
            angle_end = (i + 1) * self.wedge_deg

            t1 = np.radians(angle_start)
            t2 = np.radians(angle_end)

            # Radial planes through origin: -sin(theta)*x + cos(theta)*y = 0
            p1 = openmc.Plane(a=-np.sin(t1), b=np.cos(t1), c=0.0, d=0.0)
            p2 = openmc.Plane(a=-np.sin(t2), b=np.cos(t2), c=0.0, d=0.0)

            # Wedge between angle_start and angle_end within the radial boundaries
            wedge_region = +self.r_in & -self.r_out & +p1 & -p2

            # Cell filling this sector with rotated base_universe
            wedge_cell = openmc.Cell(
                region=wedge_region,
                fill=self.base_universe,
            )
            wedge_cell.rotation=(0.0, 0.0, angle_start)
            ring_universe.add_cell(wedge_cell)

        return ring_universe

    def create_fuel_ring_geometry(self) -> openmc.Geometry:
        ring_universe = self.create_fuel_ring()
        element_ring_class.set_universe(ring_universe)
        return openmc.Geometry(root=ring_universe)


