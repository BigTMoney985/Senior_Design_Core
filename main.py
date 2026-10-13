# THIS WILL CONTAIN RUN MODES AND WHATNOT
import openmc
from geometry.fuel_plate import FuelPlateGeometry
from matplotlib import pyplot as plt

plateclass = FuelPlateGeometry('u3si2')

clad_cells, fuel_cells, water_cells = plateclass.create_plate_cells()

cells = clad_cells + fuel_cells + water_cells

print(type(cells))

element_universe = openmc.Universe(cells=cells)

geom = openmc.Geometry(element_universe)

print(element_universe)



geom.export_to_xml()

plot = openmc.Plot()
plot.origin = (10, 10, 10)
plot.width = (20, 20)
plot.pixels = (1400, 1400)
plot.color_by = 'material'


plot.colors = {
    aluminum: 'lightgray',
    ss_304: 'darkgray',
    ss_304L: 'dimgray',
    concrete: 'lightblue',
    air: 'white',
    be_metal: 'lightyellow',
    graphite: 'black',
    boron: 'green',
    borated_ss306: 'darkgreen',
    fuel: 'red',
    water: 'blue',
    zr_barrier: 'orange'
}


plots = openmc.Plots([plot])
plots.export_to_xml()

openmc.plot_geometry()





