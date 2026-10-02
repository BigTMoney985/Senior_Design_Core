import openmc 
import numpy as np
from config.global_vars import fuel, fluxtrap

element_left_bound = openmc.YPlane(y0=0)
fuel_left = openmc.YPlane(y0=fuel.clad_thickness)
# element_inner = openmc.ZCylinder(r=fuel.fuel_inner)
element_outer = openmc.ZCylinder(r=fuel.fuel_outer)
fuel_angle = openmc.Plane(a=-1.0, b=1.0, c=0.0, d=np.sqrt(2)*fuel.clad_thickness)
element_angle = openmc.Plane(a=-1.0, b=1.0, c=0, d=0)

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
    
