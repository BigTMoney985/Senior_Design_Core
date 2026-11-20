import openmc
import numpy as np


def tally_generator():
    tallies = openmc.Tallies()
            
    # ==================================
    # Full core flux tally
    # ==================================

    # mesh = openmc.RegularMesh()
    # mesh.dimension = [200, 200, 1]
    # mesh.lower_left = [0.0, 0.0, 70.0] #type: ignore
    # mesh.upper_right = [20.0, 20.0, 80.0] #type: ignore
    # mesh_filter = openmc.MeshFilter(mesh)
    # tally = openmc.Tally(name='mesh tally')
    # tally.filters = [mesh_filter, 
    #                 openmc.ParticleFilter(['neutron']), 
    #                 openmc.EnergyFilter([0., 1.0, 20.0e6])]
    # tally.scores = ['absorption', 'flux', 'fission']
    # tallies.append(tally)

    # ==================================
    # Wedge flux tally
    # ==================================
    r_grid = np.linspace(0.0, 20.0, 150)          # 150 radial bins (cm)
    phi_grid = np.linspace(0.0, np.pi / 3.0, 120)  # 120 azimuthal bins across a 60 deg wedge
    cyl_mesh = openmc.CylindricalMesh(
        r_grid=r_grid, # pyright: ignore[reportArgumentType]
        phi_grid=phi_grid, # pyright: ignore[reportArgumentType]
        z_grid=np.array([70.0, 80.0]), # pyright: ignore[reportArgumentType]
        origin=(0.0, 0.0, 70.0),
    )

    evil_ass_tally = openmc.Tally(name="Cylindrical Flux",)
    evil_ass_tally.filters = [
        openmc.MeshFilter(cyl_mesh), 
        openmc.ParticleFilter(['neutron']), 
        openmc.EnergyFilter([0., 1.0, 20.0e6])
        ]
    evil_ass_tally.scores = ["flux"]
    tallies.append(evil_ass_tally)
    # ==================================
    # Full core heating tally
    # ==================================

    # three_d_mesh = openmc.RegularMesh()
    # three_d_mesh.dimension = [500, 500, 600]
    # three_d_mesh.lower_left = [-18.0, -18.0, 0.0] #type: ignore
    # three_d_mesh.upper_right = [18.0, 18.0, 150.0] #type: ignore
    # three_d_mesh_filter = openmc.MeshFilter(three_d_mesh)
    # heating_tally_3d = openmc.Tally(name='3D heating tally')
    # heating_tally_3d.filters = [three_d_mesh_filter]
    # heating_tally_3d.scores = ['heating']
    # tallies.append(heating_tally_3d)

    # fuel_therm_abs_rate = openmc.Tally(name='fuel therm. abs. rate')
    # fuel_therm_abs_rate.scores = ['absorption']
    # fuel_therm_abs_rate.filters = [
    #     openmc.EnergyFilter([0., 0.625]),
    #     openmc.MaterialFilter([material_dict['fuel']]),
    #     openmc.ParticleFilter(['neutron'])
    # ]
    # tallies.append(fuel_therm_abs_rate)

    heating_tally = openmc.Tally(name='heating rate')
    heating_tally.scores = ['heating']
    tallies.append(heating_tally)

    return tallies