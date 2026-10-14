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

        self.guide_bottom = -self.semi_end

        #Allocation
        self.surface_dict = None

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
        self.surface_dict = self.create_surfaces()
        inner_blade = []
        outer_blades = []

        entire_blade_annulus = -self.surface_dict['outer_cyl'] & +self.surface_dict['inner_cyl']
        inner_blade_cyl_reg = -self.surface_dict['mid_cyl'] & +self.surface_dict['inner_cyl']
        outer_blade_cyl_reg = -self.surface_dict['outer_cyl'] & +self.surface_dict['mid_cyl']

        # INNER ANNULAR RING DEFS
        # NOTE, REMEMBER TO ADD THE MATERIALS AT SOME POINT 

        inner_blade.append(openmc.Cell(
            name='blade universe water below',
            fill=None,
            region=inner_blade_cyl_reg & -self.surface_dict['bottom']
        ))
        inner_blade.append(openmc.Cell(
            name='blade universe water above',
            fill=None,
            region=inner_blade_cyl_reg & +self.surface_dict['top']
        ))

        inner_blade.append(openmc.Cell(
            name='central blade transparent section',
            fill=None,
            region=(inner_blade_cyl_reg & -self.surface_dict['top'] & +self.surface_dict['semi_end'])
        ))
        inner_blade.append(openmc.Cell(
            name='central blade semi-poison',
            fill=None,
            region=(inner_blade_cyl_reg & -self.surface_dict['semi_end'] & +self.surface_dict['semi_start'])
        ))
        inner_blade.append(openmc.Cell(
            name='central blade poison',
            fill=None,
            region=(inner_blade_cyl_reg & -self.surface_dict['semi_start'] & +self.surface_dict['bottom'])
        ))

        #OUTER ANNULAR RING DEFS
        wedge_planes = self.surface_dict['plane_list']
        plane_no = len(wedge_planes)
        for i in range(plane_no):
            
            
            wedge_region = +wedge_planes[i] & -wedge_planes[((i + 1) % plane_no)]

            below_water = openmc.Cell(
                name=f'outer blade {i+1} universe water below',
                fill=None,
                region=outer_blade_cyl_reg & -self.surface_dict['bottom'] & wedge_region
            )
            above_water = openmc.Cell(
                name=f'outer blade {i+1} universe water above',
                fill=None,
                region=outer_blade_cyl_reg & +self.surface_dict['top'] & wedge_region
            )
            
            outer_poison = openmc.Cell(
                name=f'outer central blade {i+1} poison',
                fill=None,
                region=(outer_blade_cyl_reg & -self.surface_dict['top'] & +self.surface_dict['semi_end'] & wedge_region)
            )
            outer_semi = openmc.Cell(
                name=f'outer central blade {i+1} semi-poison',
                fill=None,
                region=(outer_blade_cyl_reg & -self.surface_dict['semi_end'] & +self.surface_dict['semi_start'] & wedge_region)
            )
            outer_transparent = openmc.Cell(
                name=f'outer central blade {i+1} transparent section',
                fill=None,
                region=(outer_blade_cyl_reg & -self.surface_dict['semi_start'] & +self.surface_dict['bottom'] & wedge_region)
            )
            outer_blades.append([below_water, above_water, outer_poison, outer_semi, outer_transparent])


        return inner_blade, outer_blades
    
    def create_geometry(self):
        inner_blade, outer_blades = self.create_cells()

        univs = []
        univs.append(openmc.Universe(name='Inner annular control rod', cells=inner_blade))

        for i in range(len(outer_blades)):
            univs.append(openmc.Universe(
                name=f'outer central blade {i+1} universe',
                cells=outer_blades[i]
            ))

        return univs

    def create_channel_cell(self, z_insertions: list | None = None):
        '''Function for withdrawing central control blades.
        You must provide a list as long as the number of control blades (7)
        The first value will lead to the the withdrawal of reactivity, the other 6
        will insert reactivity in a given hexagonal region of the core.'''
        univs = self.create_geometry()
        inner_univ = univs[0]
        outer_univs = univs[1:]

        if self.surface_dict is None:
            raise ValueError('Surface dict is none, this is a problem')

        num_outer = len(outer_univs)
        if z_insertions is None:
            z_insertions = [0.0] * (num_outer + 1)

        inner_cyl = self.surface_dict['inner_cyl']
        mid_cyl = self.surface_dict['mid_cyl']
        outer_cyl = self.surface_dict['outer_cyl']

        # Physical limits of control blades
        guide_bot = openmc.ZPlane(z0=self.guide_bottom)
        guide_top = openmc.ZPlane(z0=self.end)

        channel_cells = []

        # -----------------------------------------------------------
        # 1. Inner Annular Channel Slot
        # -----------------------------------------------------------
        inner_channel_region = -mid_cyl & +inner_cyl & +guide_bot & -guide_top

            
        inner_cell = openmc.Cell(
            name='inner blade channel slot',
            region=inner_channel_region,
            fill=inner_univ,
            )
        inner_cell.translation = (0.0, 0.0, z_insertions[0])
        channel_cells.append(inner_cell)

        # -----------------------------------------------------------
        # 2. Outer Annular Wedge Channel Slots
        # -----------------------------------------------------------
        wedge_planes = self.surface_dict['plane_list']
        plane_no = len(wedge_planes)

        for i in range(plane_no):
            wedge_region = +wedge_planes[i] & -wedge_planes[((i + 1) % plane_no)]
            outer_slot_region = -outer_cyl & +mid_cyl & +guide_bot & -guide_top & wedge_region

            channel_cell = openmc.Cell(
                name=f'outer blade {i+1} channel slot',
                region=outer_slot_region,
                fill=outer_univs[i],
            )
            channel_cell.translation = (0.0, 0.0, z_insertions[i + 1])

            channel_cells.append(channel_cell)

        return channel_cells

                     
