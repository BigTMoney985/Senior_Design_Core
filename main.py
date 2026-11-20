#!/usr/bin/env python
# THIS WILL CONTAIN RUN MODES AND WHATNOT
import openmc
import openmc.deplete
from matplotlib import pyplot as plt
from config import global_vars as gv
from materials.material_defs import create_materials
from tallies.tally_gen import tally_generator
from geometry.model import create_geometry
import matplotlib.patches as mpatches
import argparse
import math

parser = argparse.ArgumentParser()
parser.add_argument('--run-mode', '-r', choices=['plot', 'model', 'search', 'deplete'], default='model')
parser.add_argument('--compute-choice', '-c', choices=['local', 'hpc'], default='hpc')
parser.add_argument('--no-tally', action='store_true', help='Disable tallies in the model')
args = parser.parse_args()

gv.user_opts.run_mode = args.run_mode
gv.user_opts.compute_choice = args.compute_choice

material_dict, materials = create_materials(gv.user_opts.fuel_choice)

def create_run_model(withdrawal: float = 0.0) -> openmc.Model:
    geom = create_geometry(withdrawal=withdrawal)

    if not args.no_tally:
        tallies = tally_generator()

    else:
        tallies = openmc.Tallies()

    #bounds = [-20, -20, 0, 20, 20, 150] # for regular unwedged model
    bounds = [0, 0, 0, 20, 20, 150] # for wedged model
    uniform_dist = openmc.stats.Box(bounds[:3], bounds[3:]) # type: ignore

    entropy_mesh = openmc.RegularMesh()

    settings = openmc.Settings(
        run_mode='eigenvalue',
        particles=int(3e4),
        batches=200,
        inactive=30,
        source=openmc.IndependentSource(space=uniform_dist, constraints={'fissionable': True}),
        #output={'tallies': True},
        photon_transport = True,
        max_lost_particles = 400,
    )

    n = math.ceil((settings.particles / 20.0)**(1.0 / 3.0))
    entropy_mesh = openmc.RegularMesh()
    entropy_mesh.dimension = [n, n, n]
    entropy_mesh.lower_left = [0, 0, 0] # type: ignore
    entropy_mesh.upper_right = [20, 20, 150] # type: ignore

    settings.entropy_mesh = entropy_mesh

    # REACTOR KINETICS PARAMATERS FINDING ========================
    #settings.ifp_n_generation = 10

    model = openmc.Model(
        geometry=geom,
        materials=materials,
        settings=settings,
        tallies=tallies,
    )
    #model.add_kinetics_parameters_tallies(num_groups=6)
    # This is broken right now, dw about it.

    return model

# ================================================
# WITHDRAWAL SETTINGS FOR MAIN MODEL RUN
# ================================================
if gv.user_opts.run_mode == 'model':
    model = create_run_model(withdrawal=-82.0) # fully withdrawn is 0.0, fully inserted is -162.5

    

    model.export_to_model_xml()

    if gv.user_opts.compute_choice == 'local':
        model.run()

    else:
        print("exported model to xml files.")


elif gv.user_opts.run_mode == 'deplete':
    model = create_run_model(withdrawal=-82.0) # fully withdrawn is 0.0, fully inserted is -162.5

    # ===========================================
    # DEPLETION SETTINGS
    # ===========================================
    fission_q = {"U235": 202e+6}  # energy in eV
    power = (50.0e6 / 6) #MW after model is sliced.
    timesteps = [1, 1, 1, 1, 1, 1] # Days
    op = openmc.deplete.CoupledOperator(
        model,
        "chain.xml",
        fission_q=fission_q,
        diff_burnable_mats=True,
    )

    integrator = openmc.deplete.CECMIntegrator(op, timesteps, power, timestep_units='d')
    integrator.integrate()


elif gv.user_opts.run_mode == 'search':
    withdraw_val, guesses, keffs = openmc.search_for_keff(
        model_builder=create_run_model,
        initial_guess=-80.0,
        target=1.0,
        bracket=[-162.5, 0.0],
        tol=1e-2,
        print_iterations=True,
        run_args={'mpi_args': ['mpiexec', '-n', '8']} # Assumes hpc
    )

elif gv.user_opts.run_mode == 'plot':
    geom = create_geometry(withdrawal=-73.0) # fully withdrawn at 0.0

    plot = openmc.Plot()
    plot.filename = 'plot_1'
    plot.basis = 'xy'
    plot.origin = (14.5, 8, 75) # plot.origin = (0, 0, 75)
    plot.width = (10, 10) # plot.width = (40, 40)
    plot.pixels = (2160, 2160)
    plot.color_by = 'material'
    plot.show_overlaps = True
    plot.overlap_color = 'yellow'

    color_map = {
        'aluminum': 'lightgray',
        'ss_304': 'darkgray',
        'be_metal': 'maroon',
        'hf_steel': 'darkgreen',
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

        extent = [-20.0, 20.0, -20.0, 20.0]

        fig, ax = plt.subplots(figsize=(10, 8))
        ax.imshow(img, origin='upper', extent=extent) # type: ignore
        ax.set_xticks(range(-20, 21, 5))
        ax.set_yticks(range(-20, 21, 5))
        ax.set_xlabel("x [cm]")
        ax.set_ylabel("y [cm]")
        ax.tick_params(axis='both', which='both', direction='out', length=5)

        patches = [
            mpatches.Patch(color=color, label=mat.name)
            for mat, color in plot.colors.items()
        ]

        ax.legend(handles=patches, bbox_to_anchor=(1.05, 1), loc='upper left')
        #plt.axis('off')
        plt.savefig('slice_plot_with_legend.png', bbox_inches='tight', dpi=300)
        plt.close()

else:
    raise ValueError(f"Invalid run mode: {gv.user_opts.run_mode}. Valid options are 'plot', 'model', or 'search'.")





