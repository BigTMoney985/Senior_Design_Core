# THIS WILL CONTAIN RUN MODES AND WHATNOT
import openmc
from geometry.fuel_element import FuelElementGeometry
from matplotlib import pyplot as plt
from config import global_vars as gv
from materials.material_defs import create_materials
from geometry.fuel_ring import FuelRingGeometry



# INITIALIZATION OF FUEL TYPE
material_dict = create_materials(gv.user_opts.fuel_choice)
fuel_geometry = FuelElementGeometry()
fuel_ring_geometry = FuelRingGeometry()
geom = fuel_ring_geometry.create_fuel_ring_geometry()  # Create the fuel ring geometry
geom.export_to_xml()

universe = gv.element_ring_class.universe  # Get the universe from the global variable

# PLOTTING THE FUEL ELEMENT GEOMETRY
plot = openmc.Plot()
plot.basis = 'xy'
plot.origin = (0, 0, 10)
plot.width = (40, 40)
plot.pixels = (2160, 2160)
plot.color_by = 'material'

# This part is to set the colors for each material in the plot.

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





