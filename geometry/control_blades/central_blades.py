import openmc
import numpy as np
import config.global_vars as gv

class central_blades:
    def __init__(self) -> None:
        self.r_inner = gv.reflector.water_gap + gv.fuel.fuel_outer
        self.r_midpoint = self.r_inner + gv.control_blade.blade_thickness
        self.r_out = self.r_midpoint + gv.control_blade.blade_thickness
        self.blade_deg = 360.0 / gv.control_blade.central_blade_num

        #Axial changes
        self.bottom = 0
        self.semi_start = gv.fuel.height
        self.semi_end = (1 + gv.control_blade.percent_semi_abs) * gv.fuel.height
        self.end = self.semi_end + gv.fuel.height

        gv.control_blade.rad_out_central = self.r_out
    def create_surfaces(self):

        inner_cyl = openmc.ZCylinder(r=self.r_inner)
        mid_cyl = openmc.ZCylinder(r=self.r_midpoint)
        outer_cyl = openmc.ZCylinder(r=self.r_out)

        bottom = openmc.ZPlane(z0=0)
        semi_start = openmc.ZPlane(z0=self.semi_start)
        semi_end = openmc.ZPlane(z0=self.semi_end)
        top = openmc.ZPlane(z0=self.end)

        planes = []
        for i in range(gv.control_blade.central_blade_num):
            plane_angle = i * self.blade_deg

            t1 = np.radians(plane_angle)

            #rotated planes thru origin: -sin(theta)x + cos(theta)y = 0
            plane = openmc.Plane(a=-np.sin(t1), b=np.cos(t1), c=0.0, d=0.0)
            planes.append(plane)

        surface_dict = {
            'inner_cyl': inner_cyl,
            'mid_cyl': mid_cyl,
            'outer_cyl': outer_cyl,
            'plane_list': planes,
            'bottom': bottom,
            'semi_start': semi_start,
            'semi_end': semi_end,
            'top': top,
        }

        return surface_dict

    def create_cells(self):
        surface_dict = self.create_surfaces()

        inner_blade_cyl_reg = -surface_dict['mid_cyl'] & +surface_dict['inner_cyl']
        outer_blade_cyl_reg = -surface_dict['outer_cyl'] & +surface_dict['mid_cyl']

        # INNER ANNULAR RING DEFS
        # NOTE, REMEMBER TO ADD THE MATERIALS AT SOME POINT 
        inner_poison = openmc.Cell(
            name='central blade poison',
            fill=None,
            region=(inner_blade_cyl_reg & -surface_dict['top'] & +surface_dict['semi_end'])
        )
        inner_semi = openmc.Cell(
            name='central blade semi-poison',
            fill=None,
            region=(inner_blade_cyl_reg & -surface_dict['semi_end'] & +surface_dict['semi_start'])
        )
        inner_transparent = openmc.Cell(
            name='central blade transparent section',
            fill=None,
            region=(inner_blade_cyl_reg & -surface_dict['semi_start'] & +surface_dict['bottom'])
        )

        #OUTER ANNULAR RING DEFS
        blades = []
        wedge_planes = surface_dict['plane_list']
        plane_no = len(wedge_planes)
        for i in range(plane_no):
            
            
            wedge_region = +wedge_planes[i] & -wedge_planes[((i + 1) % plane_no)]
            
            outer_poison = openmc.Cell(
                name='central blade poison',
                fill=None,
                region=(outer_blade_cyl_reg & -surface_dict['top'] & +surface_dict['semi_end'] & wedge_region)
            )
            outer_semi = openmc.Cell(
                name='central blade semi-poison',
                fill=None,
                region=(outer_blade_cyl_reg & -surface_dict['semi_end'] & +surface_dict['semi_start'] & wedge_region)
            )
            outer_transparent = openmc.Cell(
                name='central blade transparent section',
                fill=None,
                region=(outer_blade_cyl_reg & -surface_dict['semi_start'] & +surface_dict['bottom'] & wedge_region)
            )

        pass
