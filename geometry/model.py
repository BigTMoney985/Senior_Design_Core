import openmc 
import config.global_vars as gv
from geometry.fuel_ring import FuelRingGeometry
from geometry.surrounding_water import WaterGeometry
from geometry.central_reflector import be_reflector
from geometry.control_blades.central_blades import central_blades_cl

def create_geometry():
    fuel_ring_geometry = FuelRingGeometry()
    water_geom = WaterGeometry()
    control_blades = central_blades_cl()

    # Create shared boundary cylinders
    surf_dict = water_geom.create_surfaces()

    # 1. Water cells (central cavity + outer reflector)
    water_cells = water_geom.create_water_cells_inner(surf_dict)

    # 2. Fuel ring cell (bounded strictly to the annular space)
    ring_cell = openmc.Cell(
        name="fuel_ring_annulus",
        fill=fuel_ring_geometry.create_fuel_ring(),
        region=+surf_dict['inner_cyl'] & -surf_dict['outer_cyl'] & gv.graveyard.graveyard_region
    )

    # 3. Be reflector region
    be_geom = be_reflector() # This has to be here or the code breaks
    inner_cyl, outer_cyl = be_geom.create_surfaces()
    be_cell = be_geom.create_be_cells(inner_cyl, outer_cyl)

    # 4 Control blade region

    control_blades_cell = control_blades.create_channel_cell([gv.fuel.height, 67, 0, 0, 0, 0, 0,])

    # 5. Assemble root universe
    root_universe = openmc.Universe(cells=water_cells + [ring_cell] + [be_cell] + control_blades_cell)
    root_geometry = openmc.Geometry(root=root_universe)
    root_geometry.export_to_xml()

    return root_geometry