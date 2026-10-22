import openmc 
import config.global_vars as gv
from geometry.fuel_ring import FuelRingGeometry
from geometry.surrounding_water import WaterGeometry
from geometry.central_reflector import be_reflector
from geometry.control_blades.central_blades import central_blades_cl

def create_geometry():
    fuel_ring_geometry = FuelRingGeometry()
    control_blades = central_blades_cl()
    be_geom = be_reflector() # This has to be here or the code breaks
    water_geom = WaterGeometry()

    # Create shared boundary cylinders
    surf_dict = water_geom.create_surfaces()

    # 1. Water cells (central cavity + outer reflector)
    water_cells = water_geom.create_water_cells_inner(surf_dict)
    water_cells += water_geom.create_water_cells_around(surf_dict)

    # 2. Fuel ring cell (bounded strictly to the annular space)
    ring_cell = openmc.Cell(
        name="fuel_ring_annulus",
        fill=fuel_ring_geometry.create_fuel_ring(),
        region=+surf_dict['inner_cyl'] & -surf_dict['outer_cyl'] & gv.graveyard.graveyard_region
    )

    # 3. Be reflector region
    inner_cyl, outer_cyl = be_geom.create_surfaces()
    be_cell = be_geom.create_be_cells(inner_cyl, outer_cyl)

    # 4 Control blade region
    
    # Curent full withdrawal for main central blade is -162.5, with full insertion of it being 0.
    # Current full withdrawal for all other is 0, with full insertion at -162.5 (-150 * 1.125)
    control_blades_cell = control_blades.create_channel_cell([-162.50, 0, 0, 0, 0, 0, 0,])

    

    # 5. Assemble root universe
    root_universe = openmc.Universe(cells=water_cells + [ring_cell] + [be_cell] + control_blades_cell)
    root_geometry = openmc.Geometry(root=root_universe)
    #root_geometry.export_to_xml()   |   NOT NEEDED SINCE GEOMETRY IS PULLED

    return root_geometry