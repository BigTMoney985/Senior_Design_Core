import openmc 
import numpy as np
import config.global_vars as gv
from materials.material_defs import create_materials
from geometry.fuel_element import FuelElementGeometry
from geometry.fuel_ring import FuelRingGeometry


# INITIALIZATION OF FUEL TYPE
material_dict = create_materials(gv.user_opts.fuel_choice)
fuel_geometry = FuelElementGeometry() # Create one fuel element
fuel_ring_geometry = FuelRingGeometry() # Create inner ring


ring_univ = fuel_ring_geometry.create_fuel_ring()  # Create the fuel ring geometry