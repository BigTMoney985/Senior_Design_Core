# THIS WILL CONTAIN RUN MODES AND WHATNOT
import openmc
from geometry.fuel_plate import FuelPlateGeometry
from matplotlib import pyplot as plt

plateclass = FuelPlateGeometry('u3si2')

clad_cells, fuel_cells, water_cells = plateclass.create_plate_cells()

