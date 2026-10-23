import numpy as np
import openmc
from config.global_vars import fuel, user_opts, materials, element_cell_class
from materials.material_defs import create_materials


class FuelElementGeometry:
    def __init__(self):
        self.fuel_choice = user_opts.fuel_choice

        # Angle of sector (60 degrees)
        # Line equation: -sin(theta)*x + cos(theta)*y = 0
        theta = np.deg2rad(60.0)
        a_norm = -np.sin(theta)
        b_norm = np.cos(theta)
        # Note: sqrt(a^2 + b^2) == 1.0, so d is exact physical offset

        clad_edge_thick = fuel.clad_thickness * 2.0

        # Element boundary planes (Sector from 0 rad to theta rad)
        self.element_left_bound = openmc.YPlane(y0=0.0)
        self.element_angle = openmc.Plane(a=a_norm, b=b_norm, c=0.0, d=0.0)

        # Inset planes bounding the active fuel meat & channels
        self.fuel_left = openmc.YPlane(y0=clad_edge_thick)
        # Shift inward into the sector (d < 0 moves the plane towards -y inside quadrant 1)
        self.fuel_angle = openmc.Plane(a=a_norm, b=b_norm, c=0.0, d=-clad_edge_thick)

        # Surfaces stored for reuse in create_fuel_cell
        self.inner_clad_surfaces = []
        self.outer_clad_surfaces = []

        self.fuel_universe = None

    def get_planes(self):
        return self.element_left_bound, self.fuel_left, self.fuel_angle, self.element_angle

    def define_plates(self):
        if self.fuel_choice.lower() not in ['u3si2', 'u3o8', 'u10mo']:
            raise ValueError(f"Invalid fuel choice: {self.fuel_choice}. Valid choices are: 'u3si2', 'u3o8', 'u10mo'")
        if self.fuel_choice.lower() == 'u10mo':
            raise NotImplementedError("U10Mo fuel choice is not yet implemented.")

        inner_clad_surfaces = []
        inner_meat_surfaces = []
        outer_meat_surfaces = []
        outer_clad_surfaces = []

        for i in range(fuel.plate_num):
            r_in_clad = fuel.fuel_inner + i * (fuel.clad_thickness * 2 + fuel.nominal_dist + fuel.meat_thickness)
            r_in_meat = r_in_clad + fuel.clad_thickness
            r_out_meat = r_in_meat + fuel.meat_thickness
            r_out_clad = r_out_meat + fuel.clad_thickness

            inner_clad_surfaces.append(openmc.ZCylinder(r=r_in_clad))
            inner_meat_surfaces.append(openmc.ZCylinder(r=r_in_meat))
            outer_meat_surfaces.append(openmc.ZCylinder(r=r_out_meat))
            outer_clad_surfaces.append(openmc.ZCylinder(r=r_out_clad))

        self.inner_clad_surfaces = inner_clad_surfaces
        self.outer_clad_surfaces = outer_clad_surfaces
        fuel.fuel_outer = outer_clad_surfaces[-1].r

        return inner_clad_surfaces, inner_meat_surfaces, outer_meat_surfaces, outer_clad_surfaces

    def create_plate_cells(self):
        (
            inner_clad_surfaces,
            inner_meat_surfaces,
            outer_meat_surfaces,
            outer_clad_surfaces
        ) = self.define_plates()

        materials_dict: dict[str, openmc.Material] | None = materials.material_dict
        if materials_dict is None:
            materials_dict, _ = create_materials(self.fuel_choice)
            materials.set_materials(material_dict=materials_dict)

        if materials_dict is None:
            raise ValueError("Materials dict is not defined")

        mat_al = materials_dict['aluminum']
        mat_fuel = materials_dict['fuel']
        mat_water = materials_dict['water']

        cells = []

        # Radial extent spanning all plates
        r_span = +inner_clad_surfaces[0] & -outer_clad_surfaces[-1]

        # Azimuthal edge cladding on the left (y ~ 0) and right (theta edge)
        # Both are inside the sector: (+element_left_bound & -element_angle)
        clad_left = r_span & +self.element_left_bound & -self.fuel_left
        clad_right = r_span & -self.element_angle & +self.fuel_angle

        cells.append(openmc.Cell(name="side_clad_left", region=clad_left, fill=mat_al))
        cells.append(openmc.Cell(name="side_clad_right", region=clad_right, fill=mat_al))

        # Active sector: bounded azimuthally between fuel_left and fuel_angle
        active_azimuth = +self.fuel_left & -self.fuel_angle

        for i in range(fuel.plate_num):
            clad_inner_region = +inner_clad_surfaces[i] & -inner_meat_surfaces[i] & active_azimuth
            meat_region = +inner_meat_surfaces[i] & -outer_meat_surfaces[i] & active_azimuth
            clad_outer_region = +outer_meat_surfaces[i] & -outer_clad_surfaces[i] & active_azimuth

            cells.append(openmc.Cell(name=f"clad_in_{i}", region=clad_inner_region, fill=mat_al))
            cells.append(openmc.Cell(name=f"fuel_{i}", region=meat_region, fill=mat_fuel))
            cells.append(openmc.Cell(name=f"clad_out_{i}", region=clad_outer_region, fill=mat_al))

            # Water channels between successive plates
            if i != fuel.plate_num - 1:
                water_region = +outer_clad_surfaces[i] & -inner_clad_surfaces[i + 1] & active_azimuth
                cells.append(openmc.Cell(name=f"water_{i}", region=water_region, fill=mat_water))

        return cells

    def create_fuel_universe(self) -> openmc.Universe:
        cells = self.create_plate_cells()
        self.fuel_universe = openmc.Universe(cells=cells)
        return self.fuel_universe

    def create_fuel_geometry(self) -> openmc.Geometry:
        element_universe = self.create_fuel_universe()
        return openmc.Geometry(element_universe)

    def create_fuel_cell(self) -> openmc.Cell:
        if self.fuel_universe is None:
            self.create_fuel_universe()

        # Reuses exact surface objects to prevent coincident surface artifacts
        element_region = (
            +self.inner_clad_surfaces[0] &
            -self.outer_clad_surfaces[-1] &
            +self.element_left_bound &
            -self.element_angle
        )

        element_cell_class.set_vars(region=element_region, universe=self.fuel_universe) #type: ignore
        return openmc.Cell(name="fuel_element_cell", region=element_region, fill=self.fuel_universe)




    


    
