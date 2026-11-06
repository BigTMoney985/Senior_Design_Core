# THIS WILL CONTAIN RUN MODES AND WHATNOT
import openmc
from geometry.fuel_element import FuelElementGeometry
from matplotlib import pyplot as plt
from config import global_vars as gv
from materials.material_defs import create_materials
# from geometry.fuel_ring import FuelRingGeometry
from geometry.model import create_geometry
import matplotlib.patches as mpatches

material_dict, materials = create_materials(gv.user_opts.fuel_choice)
geom = create_geometry()

if gv.user_opts.run_mode == 'plot':
    plot = openmc.Plot()
    plot.filename = 'plot_1'
    plot.basis = 'xy'
    plot.origin = (0, 0, 75)
    plot.width = (34, 34)
    plot.pixels = (2160, 2160)
    plot.color_by = 'material'
    plot.show_overlaps = True

    color_map = {
        'aluminum': 'lightgray',
        'ss_304': 'darkgray',
        'be_metal': 'lightyellow',
        'b4c': 'darkgreen',
        'fuel': 'red',
        'water': 'blue',
    }

    if material_dict is not None:
        plot.colors = {
            material_dict[name]: color 
            for name, color in color_map.items() 
            if name in material_dict
        }

    print(f'Lobe Fuel Outer Rad: {gv.fuel.fuel_outer:.4f} cm')
    print(f'Fuel Thickness: {gv.fuel.fuel_outer - gv.fuel.fuel_inner:.4f} cm')
    print(f'Be Reflector Inner Rad: {gv.reflector.r_inner:.4f} cm')
    print(f'Be Reflector Outer Rad: {gv.reflector.r_outer:.4f} cm')
    
    plots = openmc.Plots([plot])
    model = openmc.Model(geometry=geom, materials=materials, plots=plots)
    model.plot_geometry()

    if gv.user_opts.legend:
        img = plt.imread(f'{plot.filename}.png')
        fig, ax = plt.subplots(figsize=(10, 8))
        ax.imshow(img)

        patches = [
            mpatches.Patch(color=color, label=mat.name)
            for mat, color in plot.colors.items()
        ]

        ax.legend(handles=patches, bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.axis('off')
        plt.savefig('slice_plot_with_legend.png', bbox_inches='tight', dpi=300)
        plt.close()

else:
    tallies = openmc.Tallies()
    
    mesh = openmc.RegularMesh()
    mesh.dimension = [500, 500]
    mesh.lower_left = [-25.0, -25.0] #type: ignore
    mesh.upper_right = [25.0, 25.0] #type: ignore
    mesh_filter = openmc.MeshFilter(mesh)
    tally = openmc.Tally(name='mesh tally')
    tally.filters = [mesh_filter]
    tally.scores = ['absorption', 'flux', 'fission']
    tallies.append(tally)

    fuel_therm_abs_rate = openmc.Tally(name='fuel therm. abs. rate')
    fuel_therm_abs_rate.scores = ['absorption']
    fuel_therm_abs_rate.filters = [
        openmc.EnergyFilter([0., 0.625]),
        openmc.MaterialFilter([material_dict['fuel']])
    ]
    tallies.append(fuel_therm_abs_rate)
    
    heating_tally = openmc.Tally(name='heating rate')
    heating_tally.scores = ['heating']
    tallies.append(heating_tally)

    bounds = [-25, -25, 0, 25, 25, 150]
    uniform_dist = openmc.stats.Box(bounds[:3], bounds[3:], only_fissionable=True) # type: ignore

    settings = openmc.Settings(
        run_mode='eigenvalue',
        particles=int(2e4),
        batches=250,
        inactive=15,
        source=openmc.IndependentSource(space=uniform_dist),
        output={'tallies': True},
    )

    # REACTOR KINETICS PARAMATERS FINDING ========================
    settings.ifp_n_generation = 10

    model = openmc.Model(
        geometry=geom,
        materials=materials,
        settings=settings,
        tallies=tallies,
    )
    #model.add_kinetics_parameters_tallies(num_groups=6)
    # This is broken right now, dw about it.

    model.export_to_model_xml()

    if gv.user_opts.compute_choice == 'local':
        model.run()

    else:
        print("exported model to xml files.")





