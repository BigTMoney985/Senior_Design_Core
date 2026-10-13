import openmc 
import numpy as np
from config.global_vars import fuel, fluxtrap
#from materials.material_defs import create_materials
from geometry.fuel_element import FuelElementGeometry

element = FuelElementGeometry().create_fuel_cell() # Create the fuel element universe

elements_ring = 8 # Number of elements in a ring as they have 45 degree angles :O

for i in range(elements_ring):
    angle = i * (360 / elements_ring)



