# THIS WILL CONTAIN RUN MODES AND WHATNOT
import openmc
from geometry.fuel_plate import FuelPlateGeometry
from matplotlib import pyplot as plt
from config import global_vars as gv

# INITIALIZATION OF FUEL TYPE

plateclass = FuelPlateGeometry('u3si2')

cells = plateclass.create_plate_cells()

element_universe = openmc.Universe(cells=cells)

geom = openmc.Geometry(element_universe)

print(element_universe)



geom.export_to_xml()

plot = openmc.Plot()
plot.basis = 'xy'
plot.origin = (12, 8, 10)
plot.width = (15, 15)
plot.pixels = (2160, 2160)
plot.color_by = 'material'

# This part is to set the colors for each material in the plot.

material_dict = gv.materials.material_dict

if material_dict is not None:
    # I havent fixed the material colors yet lol
    color_map = {
        'aluminum': 'lightgray',
        'ss_304': 'darkgray',
        'ss_304L': 'dimgray',
        'concrete': 'lightblue',
        'air': 'white',
        'be_metal': 'lightyellow',
        'graphite': 'black',
        'boron': 'green',
        'borated_ss306': 'darkgreen',
        'fuel': 'red',
        'water': 'blue',
        'zr_barrier': 'orange'
    }

    plot.colors = {material_dict[name]: color for name, color in color_map.items() if name in material_dict}


plots = openmc.Plots([plot])
plots.export_to_xml()

openmc.plot_geometry()





