import numpy as np
import openmc
from config.global_vars import element_ring_class, graveyard
from geometry.fuel_element import FuelElementGeometry


class FuelRingGeometry:
    def __init__(self):
        self.element_factory = FuelElementGeometry()
        self.elements_ring = 6
        self.wedge_deg = 360.0 / self.elements_ring

    def create_fuel_ring(self) -> openmc.Universe:
        ring_universe = openmc.Universe(name="fuel_ring_universe")

        # Create the fully bounded base element cell (0 to 60 deg, r_in to r_out)
        base_element_cell = self.element_factory.create_fuel_cell()
        # Place it inside a universe that can be rotated
        base_element_universe = openmc.Universe(cells=[base_element_cell])

        for i in range(self.elements_ring):
            angle = i * self.wedge_deg

            # Outer cell filling space with the rotated element universe
            sector_cell = openmc.Cell(
                name=f"fuel_sector_{i}",
                fill=base_element_universe,
                region=graveyard.fueled_region  # Axial bounding (Z bounds)
            )
            # Rotate by angle around Z-axis
            sector_cell.rotation = (0.0, 0.0, angle)
            ring_universe.add_cell(sector_cell)

        element_ring_class.set_universe(ring_universe)
        return ring_universe

    def create_fuel_ring_geometry(self) -> openmc.Geometry:
        ring_universe = self.create_fuel_ring()
        return openmc.Geometry(root=ring_universe)


