import openmc 
import numpy as np
from config.global_vars import fuel, fluxtrap

element_left_bound = openmc.YPlane(y0=0) #left bound of full element
fuel_left = openmc.YPlane(y0=fuel.clad_thickness) # left bound of the fuel region.
fuel_angle = openmc.Plane(a=-1.0, b=1.0, c=0.0, d=np.sqrt(2)*fuel.clad_thickness)
element_angle = openmc.Plane(a=-1.0, b=1.0, c=0, d=0)

    #return element_left_bound, fuel_left, fuel_angle, element_angle

# ==================== DEFINING PLATES ====================
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

#surfaces = [inner_clad_surfaces, inner_meat_thickness, outer_meat_thickness, outer_clad_thickness]
#surfaces[0] -> inner_clad_surfaces
#surfaces[1] -> inner_meat_thickness
#surfaces[2] -> outer_meat_thickness
#surfaces[3] -> outer_clad_thickness

clad_cells = []
fuel_cells = []
water_cells = []

for i in range(fuel.plate_num):
    if i == 0:
        clad_left = +element_left_bound & -fuel_left & -outer_clad_thickness[-1] & inner_clad_surfaces[0]
        clad_right = +inner_clad_surfaces[0] & -outer_clad_thickness[-1] & -element_angle & +fuel_angle

        clad_cells.append(openmc.Cell(region=clad_left))
        clad_cells.append(openmc.Cell(region=clad_right))

    clad_inner_region = +inner_clad_surfaces[i] & -inner_meat_thickness[i] & -fuel_angle & +fuel_left
    meat_region = +inner_meat_thickness[i] & -outer_meat_thickness[i] & -fuel_angle & +fuel_left
    clad_outer_region = +outer_meat_thickness[i] & -outer_clad_thickness[i] & -fuel_angle & +fuel_left

    if i != fuel.plate_num - 1:
        water_region = +outer_clad_thickness[i] & -inner_clad_surfaces[i+1] & -fuel_angle & +fuel_left

    clad_cells.append(openmc.Cell(region=clad_inner_region))
    fuel_cells.append(openmc.Cell(region=meat_region))
    clad_cells.append(openmc.Cell(region=clad_outer_region))
    if i != fuel.plate_num - 1:
        water_cells.append(openmc.Cell(region=water_region))
        

    


    
