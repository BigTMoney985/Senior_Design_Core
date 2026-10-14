try:
    import openmc # type: ignore
except ImportError:
    raise ImportError("The openmc module is required but not installed.")

import config.global_vars as gv


def create_materials(mat_choice: str):
    '''Create and return a set of predefined materials based on the chosen material type.'''
    valid_choices = ['u3si2', 'u3o8', 'u10mo']

    if mat_choice not in valid_choices:
        raise ValueError(f"Invalid material choice: {mat_choice}. Valid choices are: {valid_choices}")
    
    # Materials definitions

    # LWR
    water = openmc.Material(name='Water')
    water.add_element('H', 2)
    water.add_element('O', 1)
    water.set_density('g/cm3', 1.0)
    water.add_s_alpha_beta('c_H_in_H2O')

    # Al-6061
    aluminum = openmc.Material(name='Al-6061')
    aluminum.add_element('Al', 0.96, 'wo')
    aluminum.add_element('Mg', 0.01, 'wo')
    aluminum.add_element('Si', 0.006, 'wo')
    aluminum.add_element('Fe', 0.0035, 'wo')
    aluminum.add_element('Cu', 0.0025, 'wo')
    aluminum.add_element('Zn', 0.002, 'wo')
    aluminum.add_element('Ti', 0.0005, 'wo')
    aluminum.add_element('Cr', 0.002, 'wo')
    aluminum.set_density('g/cm3', 2.7)

    # Stainless Steel 304
    ss_304 = openmc.Material(name='SS-304')
    ss_304.add_element('Fe', 0.68, 'wo')
    ss_304.add_element('Cr', 0.18, 'wo')
    ss_304.add_element('Ni', 0.10, 'wo')
    ss_304.add_element('Mn', 0.02, 'wo')
    ss_304.add_element('Si', 0.01, 'wo')
    ss_304.add_element('C', 0.001, 'wo')
    ss_304.set_density('g/cm3', 8.0)

    # Steel 304L
    ss_304L = openmc.Material(name='SS-304L')
    ss_304L.add_element('Fe', 0.68, 'wo')
    ss_304L.add_element('Cr', 0.18, 'wo')
    ss_304L.add_element('Ni', 0.10, 'wo')
    ss_304L.add_element('Mn', 0.02, 'wo')
    ss_304L.add_element('Si', 0.01, 'wo')
    ss_304L.add_element('C', 0.0005, 'wo')
    ss_304L.set_density('g/cm3', 8.0)

    # Zr Barrier
    zr_barrier = openmc.Material(name='Zr Barrier')
    zr_barrier.add_element('Zr', 1)
    zr_barrier.set_density('g/cm3', 6.52)

    # Concrete
    concrete = openmc.Material(name='Concrete')
    concrete.add_element('O', 0.53, 'wo')
    concrete.add_element('Si', 0.33, 'wo')
    concrete.add_element('Ca', 0.08, 'wo')
    concrete.add_element('Al', 0.02, 'wo')
    concrete.add_element('Fe', 0.02, 'wo')
    concrete.set_density('g/cm3', 2.3)

    # Air (1 atm)
    air = openmc.Material(name='Air')
    air.add_element('N', 0.78, 'wo')
    air.add_element('O', 0.21, 'wo')
    air.add_element('Ar', 0.01, 'wo')
    air.set_density('g/cm3', 0.001225)

    # Be Metal
    be_metal = openmc.Material(name='Be Metal')
    be_metal.add_element('Be', 1)
    be_metal.set_density('g/cm3', 1.85)
    be_metal.add_s_alpha_beta('c_Be')

    # Graphite
    graphite = openmc.Material(name='Graphite')
    graphite.add_element('C', 1)
    graphite.set_density('g/cm3', 1.7)
    graphite.add_s_alpha_beta('c_Graphite')

    # Boron
    boron = openmc.Material(name='Boron')
    boron.add_element('B', 1)
    boron.set_density('g/cm3', 2.34)

    # Borinated SS306
    borated_ss306 = openmc.Material.mix_materials([ss_304, boron], fracs=[0.98, 0.02], percent_type='wo')

    #==============================FUEL CANDIDATES===============================

    if mat_choice.lower() == 'u3si2':
        # U3Si2-Al
        u3si2 = openmc.Material(name='U3Si2')
        u3si2.add_element('U', 3, enrichment=19.75) #Check 4.8 g/U/cm3
        u3si2.add_element('Si', 2)
        u3si2.set_density('g/cm3', 11.97) 

        fuel = openmc.Material.mix_materials([u3si2, aluminum], fracs=[0.52, 0.48], percent_type='wo')
        fuel.set_density('g/cm3', 11.8)
        #fuel.add_s_alpha_beta('c_Al27')

    elif mat_choice.lower() == 'u3o8':
        # U3O8
        u3o8 = openmc.Material(name='U3O8')
        u3o8.add_element('U', 3, enrichment=19.75)
        u3o8.add_element('O', 8)
        u3o8.set_density('g/cm3', 10.96)
        fuel = u3o8

    elif mat_choice.lower() == 'u10mo':
        # U-10Mo
        u10mo = openmc.Material(name='U-10Mo')
        u10mo.add_element('U', 0.9, enrichment=19.75, percent_type='wo')
        u10mo.add_element('Mo', 0.1, percent_type='wo')
        u10mo.set_density('g/cm3', 17.2)
        # NOTE, REMEMBER TO ADD A FEW uM OF ZIRCONIUM BETWEEN THE FUEL AND THE CLAD
        fuel = u10mo
    else:
        raise ValueError(f"Invalid material choice: {mat_choice}. Valid choices are: 'u3si2', 'u3o8', 'u10mo'")

    aluminum.add_s_alpha_beta('c_Al27')
    # This has to be put here otherwise it does not work.

    materials_dict = {
        'aluminum': aluminum,
        'ss_304': ss_304,
        'ss_304L': ss_304L,
        'concrete': concrete,
        'air': air,
        'be_metal': be_metal,
        'graphite': graphite,
        'boron': boron,
        'borated_ss306': borated_ss306,
        'fuel': fuel,
        'water': water,
        'zr_barrier': zr_barrier,
    }

    materials = openmc.Materials(list(materials_dict.values()))
    materials.export_to_xml()

    
    gv.materials.set_materials(material_dict=materials_dict)  # Store the materials dictionary in global_vars

    return materials_dict


def u_gcc(fuel):
    '''Find density in g/cc of Uranium in fuel meat'''
    # u238_amu = 238.05078826  # g/mol
    # u235_amu = 235.0439299  # g/mol
    # dict = fuel.get_element_atom_densities('U')
    # at_dens = dict['U']
    u_mass_density = fuel.get_mass_density('U238') + fuel.get_mass_density('U235')

    return u_mass_density

# print(f' Uranium Silicide Uranium density: {u_gcc(silicide):.2f}g/cc')
# print(f' U3O8 Uranium density: {u_gcc(u3o8):.2f}g/cc')
# print(f' U-10Mo Uranium density: {u_gcc(u10mo):.2f}g/cc')