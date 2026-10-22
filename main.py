# THIS WILL CONTAIN RUN MODES AND WHATNOT
import openmc
from geometry.fuel_element import FuelElementGeometry
from matplotlib import pyplot as plt
from config import global_vars as gv
from materials.material_defs import create_materials
# from geometry.fuel_ring import FuelRingGeometry
from geometry.model import create_geometry

material_dict, materials = create_materials(gv.user_opts.fuel_choice)
geom = create_geometry()

if gv.user_opts.run_mode == 'plot':
    # PLOTTING THE FUEL ELEMENT GEOMETRY
    plot = openmc.Plot()
    #plot.show_overlaps = True
    #plot.overlap_color = 'orange'
    plot.basis = 'xy'
    plot.origin = (6, 6, 75)
    plot.width = (10, 10)
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
            'b4c': 'darkgreen',
            'fuel': 'red',
            'water': 'blue',
            'zr_barrier': 'orange'
        }

        plot.colors = {material_dict[name]: color for name, color in color_map.items() if name in material_dict}


    plots = openmc.Plots([plot])
    # plots.export_to_xml()
    # geom.export_to_xml()
    # materials.export_to_xml()

    model = openmc.Model(
        geometry=geom,
        materials=materials,
        plots=plots
    )
        

    model.plot_geometry()



else:
    # TALLIES =================================
    # material_filter = openmc.MaterialFilter([material_dict['water'].id, material_dict['fuel'].id, material_dict['aluminum'].id])
    tallies = openmc.Tallies()
    
    mesh = openmc.RegularMesh()
    mesh.dimension = [500, 500]
    mesh.lower_left = [-20.0, -20.0]  # pyright: ignore[reportAttributeAccessIssue]
    mesh.upper_right = [20.0, 20.0] # pyright: ignore[reportAttributeAccessIssue]
    mesh_filter = openmc.MeshFilter(mesh)
    tally = openmc.Tally(name='mesh tally')
    tally.filters = [mesh_filter]
    tally.scores = ['absorption', 'flux', 'fission']
    tallies.append(tally)

    # Thermal Flux Utilization tallies
    fuel_therm_abs_rate = openmc.Tally(name='fuel therm. abs. rate')
    fuel_therm_abs_rate.scores = ['absorption']
    fuel_therm_abs_rate.filters = [openmc.EnergyFilter([0., 0.625]),
                                openmc.MaterialFilter([material_dict['fuel']])]

    tallies.append(fuel_therm_abs_rate)

    # tallies.export_to_xml()

    
    bounds = [-20, -20, 0, 20, 20, 120,]
    uniform_dist = openmc.stats.Box(bounds[:3], bounds[3:], only_fissionable=True) # pyright: ignore[reportAttributeAccessIssue]

    settings = openmc.Settings(
        run_mode = 'eigenvalue',
        particles = int(1e4),
        batches = 250,
        inactive = 15,
        source = openmc.IndependentSource(space=uniform_dist),
        output = {'tallies': True},
    )

    # REACTOR KINETICS PARAMATERS FINDING ========================
    settings.ifp_n_generation = 10

    model = openmc.Model(
        geometry=geom,
        materials=materials,
        settings=settings,
    )
    model.add_kinetics_parameters_tallies(num_groups=6)

    model.export_to_model_xml()

    model.run()





