import openmc 
import numpy as np
from config.global_vars import fuel, user_opts
from materials.material_defs import create_materials


class FuelPlateGeometry:
    def __init__(self):
        self.fuel_choice = user_opts.fuel_choice
        self.element_left_bound = openmc.YPlane(y0=0) #left bound of full element
        self.fuel_left = openmc.YPlane(y0=fuel.clad_thickness) # left bound of the fuel region.
        self.fuel_angle = openmc.Plane(a=-1.0, b=1.0, c=0.0, d=np.sqrt(2)*fuel.clad_thickness)
        self.element_angle = openmc.Plane(a=-1.0, b=1.0, c=0, d=0)

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

        materials_dict = create_materials(self.fuel_choice)
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

            if i != fuel.plate_num - 1:
                water_region = +outer_clad_thickness[i] & -inner_clad_surfaces[i+1] & -self.fuel_angle & +self.fuel_left

            clad_cells.append(openmc.Cell(region=clad_inner_region, fill=materials_dict['aluminum']))
            fuel_cells.append(openmc.Cell(region=meat_region, fill=materials_dict['fuel']))
            clad_cells.append(openmc.Cell(region=clad_outer_region, fill=materials_dict['aluminum']))
            if i != fuel.plate_num - 1:
                water_cells.append(openmc.Cell(region=water_region, fill=materials_dict['water']))

                cells_full = clad_cells + fuel_cells + water_cells

        return cells_full

def create_fuel_geometry() -> openmc.Geometry:
    plateclass = FuelPlateGeometry()
    cells = plateclass.create_plate_cells()
    element_universe = openmc.Universe(cells=cells)
    geom = openmc.Geometry(element_universe)
    #geom.export_to_xml()
    return geom



    


    
