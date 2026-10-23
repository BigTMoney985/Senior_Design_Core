import openmc 
import numpy as np
from config.global_vars import fuel, user_opts, materials, element_cell_class
from materials.material_defs import create_materials


class FuelElementGeometry:
    def __init__(self):
        # DEFINED FUEL-TYPE
        self.fuel_choice = user_opts.fuel_choice


        # DEFINED BOUNDARIES FOR THE FUEL ELEMENT
        self.element_left_bound = openmc.YPlane(y0=0) #left bound of full element
        self.fuel_left = openmc.YPlane(y0=(fuel.clad_thickness * 2)) # left bound of the fuel region.
        self.fuel_angle = openmc.Plane(a=-1.0, b=1.0, c=0.0, d=2*fuel.clad_thickness)
        self.element_angle = openmc.Plane(a=-1.0, b=1.0, c=0, d=0)

        self.outer_thickness = fuel.fuel_inner # This will be set when define_plates is called
        self.inner_thickness = fuel.fuel_outer # This will be set when define_plates is called

        # DEFINED UNIVERSE FOR THE FUEL ELEMENT
        self.fuel_universe = None # This will be set when create_fuel_universe is called

    def get_planes(self):
        return self.element_left_bound, self.fuel_left, self.fuel_angle, self.element_angle

    def define_plates(self):
        if self.fuel_choice.lower() not in ['u3si2', 'u3o8', 'u10mo']:
            raise ValueError(f"Invalid fuel choice: {self.fuel_choice}. Valid choices are: 'u3si2', 'u3o8', 'u10mo'")
        if self.fuel_choice.lower() == 'u10mo':
            raise NotImplementedError("U10Mo fuel choice is not yet implemented.")
        #u10mo is not implemented because the u10mo needs a zr layer and I did not do that.
        
        inner_clad_surfaces = []
        inner_meat_thickness = []
        outer_meat_thickness = []
        outer_clad_thickness = []
        for i in range(fuel.plate_num):
            _in_clad_surf = fuel.fuel_inner + i * (fuel.clad_thickness * 2 + fuel.nominal_dist + fuel.meat_thickness)
            _inner_meat_thickness = fuel.clad_thickness + _in_clad_surf
            _outer_meat_thickness = _inner_meat_thickness + fuel.meat_thickness
            _outer_clad_thickness = _outer_meat_thickness + fuel.clad_thickness

            inner_clad_surfaces.append(openmc.ZCylinder(r=_in_clad_surf))
            inner_meat_thickness.append(openmc.ZCylinder(r=_inner_meat_thickness))
            outer_meat_thickness.append(openmc.ZCylinder(r=_outer_meat_thickness))
            outer_clad_thickness.append(openmc.ZCylinder(r=_outer_clad_thickness))

            if i == fuel.plate_num - 1:
                self.outer_thickness = _outer_clad_thickness
                fuel.fuel_outer = self.outer_thickness
                self.inner_thickness = inner_clad_surfaces[0].r


        return inner_clad_surfaces, inner_meat_thickness, outer_meat_thickness, outer_clad_thickness
# ==================== DEFINING PLATES ====================

#surfaces = [inner_clad_surfaces, inner_meat_thickness, outer_meat_thickness, outer_clad_thickness]
#surfaces[0] -> inner_clad_surfaces
#surfaces[1] -> inner_meat_thickness
#surfaces[2] -> outer_meat_thickness
#surfaces[3] -> outer_clad_thickness

    def create_plate_cells(self):
        inner_clad_surfaces, inner_meat_thickness, outer_meat_thickness, outer_clad_thickness = self.define_plates()
        # Creating surfaces to actually work with

        materials_dict: dict[str, openmc.Material] | None = materials.material_dict

        if materials_dict is None:
            materials_dict, _ = create_materials(self.fuel_choice)
            materials.set_materials(material_dict=materials_dict) # pyright: ignore[reportArgumentType]

        if materials_dict is None:
            raise ValueError('Materials dict is not defined')

        # Creating materials dictionary for the fuel, cladding, and water cells

        clad_cells = []
        fuel_cells = []
        water_cells = []

        for i in range(fuel.plate_num):
            if i == 0:
                clad_left = +self.element_left_bound & -self.fuel_left & -outer_clad_thickness[-1] & +inner_clad_surfaces[0]
                clad_right = +inner_clad_surfaces[0] & -outer_clad_thickness[-1] & +self.element_angle & -self.fuel_angle

                clad_cells.append(openmc.Cell(region=clad_left, fill=materials_dict['aluminum']))
                clad_cells.append(openmc.Cell(region=clad_right, fill=materials_dict['aluminum']))
                # This adds the left and right cladding of each fuel element

            clad_inner_region = +inner_clad_surfaces[i] & -inner_meat_thickness[i] & -self.fuel_angle & +self.fuel_left
            meat_region = +inner_meat_thickness[i] & -outer_meat_thickness[i] & -self.fuel_angle & +self.fuel_left
            clad_outer_region = +outer_meat_thickness[i] & -outer_clad_thickness[i] & -self.fuel_angle & +self.fuel_left

            clad_cells.append(openmc.Cell(region=clad_inner_region, fill=materials_dict['aluminum']))
            fuel_cells.append(openmc.Cell(region=meat_region, fill=materials_dict['fuel']))
            clad_cells.append(openmc.Cell(region=clad_outer_region, fill=materials_dict['aluminum']))

            if i != fuel.plate_num - 1:
                water_region = +outer_clad_thickness[i] & -inner_clad_surfaces[i+1] & -self.fuel_angle & +self.fuel_left
                water_cells.append(openmc.Cell(region=water_region, fill=materials_dict['water']))

        # Outside the loop:
        return clad_cells + fuel_cells + water_cells

    def create_fuel_universe(self) -> openmc.Universe:
            '''Create a universe that contains the entire fuel element. This universe can be used for rotation or other transformations.'''
            cells = self.create_plate_cells()
            element_universe = openmc.Universe(cells=cells)
            self.fuel_universe = element_universe  # Store the universe in the instance variable
            return self.fuel_universe

    def create_fuel_geometry(self) -> openmc.Geometry:
        '''Create the fuel geometry and return an OpenMC Geometry object.'''
        element_universe = self.create_fuel_universe()
        geom = openmc.Geometry(element_universe)
        return geom


    def create_fuel_cell(self) -> openmc.Cell:
        if self.fuel_universe is None:
            self.create_fuel_universe()

        element_bound_out = openmc.ZCylinder(r=self.outer_thickness)
        element_bound_in = openmc.ZCylinder(r=self.inner_thickness)

        # FIXED: Use element_angle (45 deg) instead of fuel_angle
        # In OpenMC CSG, element_angle is a=-1, b=1 -> -x + y = 0.
        # Below y = x means (-x + y <= 0), which is the negative halfspace (-self.element_angle)
        element_region = +element_bound_in & -element_bound_out & -self.element_angle & +self.element_left_bound

        element_cell_class.set_vars(region=element_region, universe=self.fuel_universe) # type: ignore
        return openmc.Cell(region=element_region, fill=self.fuel_universe)





    


    
