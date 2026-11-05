import openmc
import numpy as np #type: ignore
import config.global_vars as gv

class central_blades_cl:
    def __init__(self, r_inner_override: float | None = None) -> None:
        if r_inner_override is not None:
            self.r_inner = r_inner_override
        else:
            self.r_inner = gv.reflector.water_gap + gv.fuel.fuel_outer

        self.r_midpoint = self.r_inner + gv.control_blade.blade_thickness
        self.r_out = self.r_midpoint + gv.control_blade.blade_thickness
        self.blade_deg = 360.0 / gv.control_blade.central_blade_num

        # Axial elevations
        self.bottom = 0.0
        self.semi_start = gv.fuel.height
        self.semi_end = (1.0 + gv.control_blade.percent_semi_abs) * gv.fuel.height
        self.end = self.semi_end + gv.fuel.height
        self.guide_bottom = -self.semi_end

        self.surface_dict = None

        material_dict = gv.materials.get_materials()
        self.water = material_dict['water']
        self.b4c = material_dict['b4c']
        self.ss304 = material_dict['ss_304']
        self.aluminum = material_dict['aluminum']

        if r_inner_override is None:
            gv.control_blade.rad_in_central = self.r_inner
            gv.control_blade.rad_out_central = self.r_out

    def create_surfaces(self):
        inner_cyl = openmc.ZCylinder(r=self.r_inner)
        mid_cyl = openmc.ZCylinder(r=self.r_midpoint)
        outer_cyl = openmc.ZCylinder(r=self.r_out)

        bottom = openmc.ZPlane(z0=0.0)
        semi_start = openmc.ZPlane(z0=self.semi_start)
        semi_end = openmc.ZPlane(z0=self.semi_end)
        top = openmc.ZPlane(z0=self.end)

        planes = []
        for i in range(gv.control_blade.central_blade_num):
            t1 = np.radians(i * self.blade_deg)
            plane = openmc.Plane(a=-np.sin(t1), b=np.cos(t1), c=0.0, d=0.0)
            planes.append(plane)

        self.surface_dict = {
            'inner_cyl': inner_cyl,
            'mid_cyl': mid_cyl,
            'outer_cyl': outer_cyl,
            'plane_list': planes,
            'bottom': bottom,
            'semi_start': semi_start,
            'semi_end': semi_end,
            'top': top,
        }
        return self.surface_dict

    def create_cells(self):
        self.surface_dict = self.create_surfaces()
        inner_blade = []
        outer_blades = []

        inner_blade_cyl_reg = -self.surface_dict['mid_cyl'] & +self.surface_dict['inner_cyl']
        outer_blade_cyl_reg = -self.surface_dict['outer_cyl'] & +self.surface_dict['mid_cyl']

        # Inner annular safety/regulating blade universe
        inner_blade.append(openmc.Cell(
            name='blade universe water below',
            fill=self.water,
            region=inner_blade_cyl_reg & -self.surface_dict['bottom']
        ))
        inner_blade.append(openmc.Cell(
            name='blade universe water above',
            fill=self.water,
            region=inner_blade_cyl_reg & +self.surface_dict['top']
        ))
        inner_blade.append(openmc.Cell(
            name='central blade transparent section',
            fill=self.aluminum,
            region=inner_blade_cyl_reg & -self.surface_dict['top'] & +self.surface_dict['semi_end']
        ))
        inner_blade.append(openmc.Cell(
            name='central blade semi-poison',
            fill=self.ss304,
            region=inner_blade_cyl_reg & -self.surface_dict['semi_end'] & +self.surface_dict['semi_start']
        ))
        inner_blade.append(openmc.Cell(
            name='central blade poison',
            fill=self.b4c,
            region=inner_blade_cyl_reg & -self.surface_dict['semi_start'] & +self.surface_dict['bottom']
        ))

        # Outer 60-deg segmented blade universes
        wedge_planes = self.surface_dict['plane_list']
        plane_no = len(wedge_planes)
        for i in range(plane_no):
            wedge_region = +wedge_planes[i] & -wedge_planes[(i + 1) % plane_no]

            below_water = openmc.Cell(
                name=f'outer blade {i+1} universe water below',
                fill=self.water,
                region=outer_blade_cyl_reg & -self.surface_dict['bottom'] & wedge_region
            )
            above_water = openmc.Cell(
                name=f'outer blade {i+1} universe water above',
                fill=self.water,
                region=outer_blade_cyl_reg & +self.surface_dict['top'] & wedge_region
            )
            outer_poison = openmc.Cell(
                name=f'outer central blade {i+1} poison',
                fill=self.b4c,
                region=outer_blade_cyl_reg & -self.surface_dict['top'] & +self.surface_dict['semi_end'] & wedge_region
            )
            outer_semi = openmc.Cell(
                name=f'outer central blade {i+1} semi-poison',
                fill=self.ss304,
                region=outer_blade_cyl_reg & -self.surface_dict['semi_end'] & +self.surface_dict['semi_start'] & wedge_region
            )
            outer_transparent = openmc.Cell(
                name=f'outer central blade {i+1} transparent section',
                fill=self.aluminum,
                region=outer_blade_cyl_reg & -self.surface_dict['semi_start'] & +self.surface_dict['bottom'] & wedge_region
            )
            outer_blades.append([below_water, above_water, outer_poison, outer_semi, outer_transparent])

        return inner_blade, outer_blades

    def create_geometry(self):
        inner_blade, outer_blades = self.create_cells()
        univs = [openmc.Universe(name='Inner annular control rod', cells=inner_blade)]
        for i in range(len(outer_blades)):
            univs.append(openmc.Universe(
                name=f'outer central blade {i+1} universe',
                cells=outer_blades[i]
            ))
        return univs

                     
