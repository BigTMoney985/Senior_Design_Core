import openmc 
import numpy as np
import config.global_vars as gv
from geometry.revolver.outer_snake import lobe_3
from geometry.surrounding_water import WaterGeometry
from geometry.central_reflector import be_reflector

def create_geometry(withdrawal: float = 0.0) -> openmc.Geometry:
    # 1. Initialize 3-lobe core + lobe control blades + central flux-trap control mechanism
    three_lobe_core = lobe_3()

    # 2. Initialize Beryllium reflector (automatically reads updated gv.control_blade.rad_out_central)
    be_geom = be_reflector()
    water_geom = WaterGeometry()

    # 3. Create shared reflector boundary cylinders
    surf_dict = water_geom.create_surfaces()
    be_cell = be_geom.create_be_cells(surf_dict['be_in'], surf_dict['be_out'])

    # 4. Build all explicit fuel, control blade, and water cells inside the core cylinder (-be_in)
    # Full withdrawal preset:
    #   z_lobe_inner = -162.5 (inner lobe blades withdrawn)
    #   z_lobe_outer = [0.0]*12 (12 outer lobe blades withdrawn)
    #   z_center_inner = -162.5 (central trap inner safety rod withdrawn)
    #   z_center_outer = [0.0]*6 (central trap outer blades withdrawn)

    # withdrawal variable goes from -162.5 to 0.0, where 0.0 is fully withdrawn and -162.5 is fully inserted.
    #NOTE: if withdrawal is set to zero, you can mess with the withdrawing manually here.
    core_cells = three_lobe_core.build_clover_cells(
        core_outer_cyl=surf_dict['be_in'],
        z_lobe_inner=(-162.5 - withdrawal), #-162.5 is out
        z_lobe_outer=[withdrawal] * 12, # 0 is out
        z_center_inner=(-162.5 - withdrawal), #-162.5 is out
        z_center_outer=[withdrawal] * 6, # 0 is out
    )

    # 5. Build outer reflector water cells
    outer_water_cells = water_geom.create_water_cells_around(surf_dict)

    # 6. Assemble intermediate universe
    intermediate_universe = openmc.Universe(cells=core_cells + [be_cell] + outer_water_cells)
    
    # 7. 60 degree wedge for variance reduction
    if not "root_universe" in locals():
        alpha = np.radians(60.0)
        vert_wedge = openmc.XPlane(x0=0.0, boundary_type='reflective')
        angle_wedge = openmc.Plane(b=-np.sin(alpha), a=(round(np.cos(alpha),6)), c=0.0, d=0.0, boundary_type='reflective')
        slice_cell = openmc.Cell(
            region = +vert_wedge & -angle_wedge,
            fill = intermediate_universe,
        )
        root_universe = openmc.Universe(cells=[slice_cell])
    root_geometry = openmc.Geometry(root=root_universe)
    
    return root_geometry