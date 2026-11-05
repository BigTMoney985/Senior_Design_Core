import openmc
import numpy as np
import config.global_vars as gv
from geometry.fuel_element import FuelElementGeometry
from geometry.control_blades.central_blades import central_blades_cl


def _oriented_halfspace(plane: openmc.Plane, ref_x: float, ref_y: float):
    """
    Returns +plane or -plane so that the reference point (ref_x, ref_y, 0.0)
    is strictly inside the returned halfspace.
    """
    val = plane.evaluate((ref_x, ref_y, 0.0))
    return +plane if val > 0 else -plane


class lobe_3:
    def __init__(self) -> None:
        self.element_factory = FuelElementGeometry()
        self.base_universe = self.element_factory.create_fuel_universe()

        # Fuel element radial dimensions (r_in = 4.0 cm, r_out = 8.3416 cm)
        self.r_in = self.element_factory.inner_thickness
        self.r_out = self.element_factory.outer_thickness
        self.fuel_thickness = self.r_out - self.r_in
        self.R0 = self.r_in + self.fuel_thickness / 2.0

        # Conformal control blades (r = 8.3916 to 8.7916 cm from hub center)
        # Used BOTH on the outside of the 3 main lobes AND hugging the central-trap
        # side of the 3 inward-curving pinch lobes!
        self.lobe_blade_builder = central_blades_cl(
            r_inner_override=self.r_out + gv.reflector.water_gap
        )
        self.lobe_blade_univs = self.lobe_blade_builder.create_geometry()
        self.r_blade_in = self.lobe_blade_builder.r_inner
        self.r_blade_mid = self.lobe_blade_builder.r_midpoint
        self.r_blade_out = self.lobe_blade_builder.r_out

        # Distance of each of the 6 hubs from (0,0) is 2 * R0 = 12.3416 cm
        self.hub_dist = 2.0 * self.R0
        self.core_outer_radius = self.hub_dist + self.r_blade_out + gv.reflector.water_gap

        # Update global state for Beryllium reflector sizing
        gv.control_blade.rad_in_central = self.hub_dist + self.r_blade_in
        gv.control_blade.rad_out_central = self.hub_dist + self.r_blade_out

        self.water_mat = gv.materials.get_materials()['water']

    def build_clover_cells(
        self,
        core_outer_cyl: openmc.ZCylinder,
        z_lobe_inner: float = -162.5,
        z_lobe_outer: list[float] | None = None,
        z_center_inner: float = -162.5,
        z_center_outer: list[float] | None = None,
    ) -> list[openmc.Cell]:
        """
        Builds the 18 fuel wedges, 12 outer-lobe conformal control blades,
        6 central-pinch conformal control blades hugging the central flux trap,
        and explicit disjoint water cells (zero global complement).
        """
        if z_lobe_outer is None:
            z_lobe_outer = [0.0] * 12
        if z_center_outer is None:
            z_center_outer = [0.0] * 6

        cells: list[openmc.Cell] = []

        # Axial bounds
        fuel_top = openmc.ZPlane(z0=gv.fuel.height)
        fuel_bot = openmc.ZPlane(z0=0.0)
        axial_fuel = +fuel_bot & -fuel_top

        guide_bot = openmc.ZPlane(z0=self.lobe_blade_builder.guide_bottom)
        guide_top = openmc.ZPlane(z0=self.lobe_blade_builder.end)
        axial_blade = +guide_bot & -guide_top

        # 3 Planes through the origin at 30 deg, 90 deg, 150 deg
        origin_planes = {}
        for ang in [30, 90, 150]:
            rad = np.radians(ang)
            origin_planes[ang] = openmc.Plane(a=-np.sin(rad), b=np.cos(rad), c=0.0, d=0.0)

        def get_origin_pie_slice(ang1_deg: float, ang2_deg: float):
            mid_rad = np.radians(0.5 * (ang1_deg + ang2_deg))
            mx, my = 5.0 * np.cos(mid_rad), 5.0 * np.sin(mid_rad)
            p1 = origin_planes[int(ang1_deg % 180)]
            p2 = origin_planes[int(ang2_deg % 180)]
            return _oriented_halfspace(p1, mx, my) & _oriented_halfspace(p2, mx, my)

        # 3 Positive Hub Centers (at 30°, 150°, 270°)
        pos_hub_angles = [30.0, 150.0, 270.0]
        pos_hubs = []
        for ang in pos_hub_angles:
            rad = np.radians(ang)
            cx, cy = self.hub_dist * np.cos(rad), self.hub_dist * np.sin(rad)

            rad_low = np.radians(ang - 60.0)
            nx_l, ny_l = -np.sin(rad_low), np.cos(rad_low)
            hex_plane_low = openmc.Plane(a=nx_l, b=ny_l, c=0.0, d=nx_l * cx + ny_l * cy)

            rad_high = np.radians(ang + 60.0)
            nx_h, ny_h = -np.sin(rad_high), np.cos(rad_high)
            hex_plane_high = openmc.Plane(a=nx_h, b=ny_h, c=0.0, d=nx_h * cx + ny_h * cy)

            pos_hubs.append({
                'cx': cx, 'cy': cy, 'ang': ang,
                'c_in': openmc.ZCylinder(x0=cx, y0=cy, r=self.r_in),
                'c_out': openmc.ZCylinder(x0=cx, y0=cy, r=self.r_out),
                'b_in': openmc.ZCylinder(x0=cx, y0=cy, r=self.r_blade_in),
                'b_mid': openmc.ZCylinder(x0=cx, y0=cy, r=self.r_blade_mid),
                'b_out': openmc.ZCylinder(x0=cx, y0=cy, r=self.r_blade_out),
                'hex_low': hex_plane_low,
                'hex_high': hex_plane_high,
            })

        # 3 Negative Hub Centers (at 90°, 210°, 330°) — now with conformal blade cylinders!
        neg_hub_angles = [90.0, 210.0, 330.0]
        neg_hubs = []
        for ang in neg_hub_angles:
            rad = np.radians(ang)
            cx, cy = self.hub_dist * np.cos(rad), self.hub_dist * np.sin(rad)
            neg_hubs.append({
                'cx': cx, 'cy': cy, 'ang': ang,
                'c_in': openmc.ZCylinder(x0=cx, y0=cy, r=self.r_in),
                'c_out': openmc.ZCylinder(x0=cx, y0=cy, r=self.r_out),
                'b_in': openmc.ZCylinder(x0=cx, y0=cy, r=self.r_blade_in),
                'b_mid': openmc.ZCylinder(x0=cx, y0=cy, r=self.r_blade_mid),
                'b_out': openmc.ZCylinder(x0=cx, y0=cy, r=self.r_blade_out),
            })

        lobe_inner_blade_univ = self.lobe_blade_univs[0]
        lobe_outer_blade_univ = self.lobe_blade_univs[1]
        blade_counter = 0

        # =====================================================================
        # PART A: THE 3 MAIN LOBES (Outward-curving 240° lobes on pos_hubs)
        # =====================================================================
        for lobe_idx, hub in enumerate(pos_hubs):
            cx, cy, ang = hub['cx'], hub['cy'], hub['ang']

            cells.append(openmc.Cell(
                name=f"lobe_{lobe_idx}_flux_trap_water",
                fill=self.water_mat,
                region=-hub['c_in'] & gv.graveyard.graveyard_region
            ))

            for w_idx in range(4):
                start_deg = ang - 120.0 + w_idx * 60.0
                mid_local_rad = np.radians(start_deg + 30.0)
                rx = cx + self.R0 * np.cos(mid_local_rad)
                ry = cy + self.R0 * np.sin(mid_local_rad)

                if w_idx in (0, 1):
                    pie_slice = get_origin_pie_slice(ang - 60.0, ang)
                else:
                    pie_slice = get_origin_pie_slice(ang, ang + 60.0)

                sector_planes = (
                    pie_slice
                    & _oriented_halfspace(hub['hex_low'], rx, ry)
                    & _oriented_halfspace(hub['hex_high'], rx, ry)
                )

                f_cell = openmc.Cell(
                    name=f"lobe_{lobe_idx}_fuel_wedge_{w_idx}",
                    fill=self.base_universe,
                    region=+hub['c_in'] & -hub['c_out'] & sector_planes & axial_fuel
                )
                f_cell.translation = (cx, cy, 0.0)
                f_cell.rotation = (0.0, 0.0, start_deg)
                cells.append(f_cell)

                cells.append(openmc.Cell(
                    name=f"lobe_{lobe_idx}_wedge_{w_idx}_water_above",
                    fill=self.water_mat,
                    region=+hub['c_in'] & -hub['c_out'] & sector_planes & +fuel_top & gv.graveyard.graveyard_region
                ))
                cells.append(openmc.Cell(
                    name=f"lobe_{lobe_idx}_wedge_{w_idx}_water_below",
                    fill=self.water_mat,
                    region=+hub['c_in'] & -hub['c_out'] & sector_planes & -fuel_bot & gv.graveyard.graveyard_region
                ))

                cells.append(openmc.Cell(
                    name=f"lobe_{lobe_idx}_wedge_{w_idx}_blade_gap_water",
                    fill=self.water_mat,
                    region=+hub['c_out'] & -hub['b_in'] & sector_planes & gv.graveyard.graveyard_region
                ))

                ib_cell = openmc.Cell(
                    name=f"lobe_{lobe_idx}_inner_blade_{w_idx}",
                    fill=lobe_inner_blade_univ,
                    region=+hub['b_in'] & -hub['b_mid'] & sector_planes & axial_blade
                )
                ib_cell.translation = (cx, cy, z_lobe_inner)
                ib_cell.rotation = (0.0, 0.0, start_deg)
                cells.append(ib_cell)

                ob_cell = openmc.Cell(
                    name=f"lobe_{lobe_idx}_outer_blade_{w_idx}",
                    fill=lobe_outer_blade_univ,
                    region=+hub['b_mid'] & -hub['b_out'] & sector_planes & axial_blade
                )
                ob_cell.translation = (cx, cy, z_lobe_outer[blade_counter])
                ob_cell.rotation = (0.0, 0.0, start_deg)
                cells.append(ob_cell)

                cells.append(openmc.Cell(
                    name=f"lobe_{lobe_idx}_blade_{w_idx}_water_above",
                    fill=self.water_mat,
                    region=+hub['b_in'] & -hub['b_out'] & sector_planes & +guide_top & gv.graveyard.graveyard_region
                ))
                cells.append(openmc.Cell(
                    name=f"lobe_{lobe_idx}_blade_{w_idx}_water_below",
                    fill=self.water_mat,
                    region=+hub['b_in'] & -hub['b_out'] & sector_planes & -guide_bot & gv.graveyard.graveyard_region
                ))

                cells.append(openmc.Cell(
                    name=f"lobe_{lobe_idx}_outer_water_{w_idx}",
                    fill=self.water_mat,
                    region=+hub['b_out'] & -core_outer_cyl & sector_planes & gv.graveyard.graveyard_region
                ))

                blade_counter += 1

        # =====================================================================
        # PART B: THE 6 INNER EQUILATERAL TRIANGLES
        # Note how hex_high and hex_low match the actual hexagon edge in each slice,
        # and each pinch fuel wedge now has conformal control blades hugging its
        # inside (central flux-trap) surface (+nhub['b_in'] to -nhub['b_out'])!
        # =====================================================================
        triangle_specs = [
            ( -30.0,  30.0, 0, 'hex_high', 2,  90.0),  # Seg 17 (around Neg Hub 2 at 330°)
            (  30.0,  90.0, 0, 'hex_low',  0, -90.0),  # Seg  4 (around Neg Hub 0 at  90°)
            (  90.0, 150.0, 1, 'hex_high', 0, -150.0), # Seg  5 (around Neg Hub 0 at  90°)
            ( 150.0, 210.0, 1, 'hex_low',  1,  30.0),  # Seg 10 (around Neg Hub 1 at 210°)
            ( 210.0, 270.0, 2, 'hex_high', 1, -30.0),  # Seg 11 (around Neg Hub 1 at 210°)
            ( 270.0, 330.0, 2, 'hex_low',  2, 150.0),  # Seg 16 (around Neg Hub 2 at 330°)
        ]

        for t_idx, (a1, a2, ph_idx, h_key, nh_idx, start_deg) in enumerate(triangle_specs):
            pie_slice = get_origin_pie_slice(a1, a2)
            hex_plane = pos_hubs[ph_idx][h_key]
            mid_rad = np.radians(0.5 * (a1 + a2))
            tx, ty = 2.0 * np.cos(mid_rad), 2.0 * np.sin(mid_rad)
            tri_region = pie_slice & _oriented_halfspace(hex_plane, tx, ty)

            nhub = neg_hubs[nh_idx]
            ncx, ncy = nhub['cx'], nhub['cy']

            # 1. Pinch hub inner water inside this triangle (-nhub['c_in'])
            cells.append(openmc.Cell(
                name=f"pinch_triangle_{t_idx}_hub_inner_water",
                fill=self.water_mat,
                region=-nhub['c_in'] & tri_region & gv.graveyard.graveyard_region
            ))

            # 2. Inward-curving fuel wedge (+nhub['c_in'] & -nhub['c_out'])
            pf_cell = openmc.Cell(
                name=f"pinch_fuel_wedge_{t_idx}",
                fill=self.base_universe,
                region=+nhub['c_in'] & -nhub['c_out'] & tri_region & axial_fuel
            )
            pf_cell.translation = (ncx, ncy, 0.0)
            pf_cell.rotation = (0.0, 0.0, start_deg)
            cells.append(pf_cell)

            # 3. Water above and below this inward-curving fuel wedge
            cells.append(openmc.Cell(
                name=f"pinch_wedge_{t_idx}_water_above",
                fill=self.water_mat,
                region=+nhub['c_in'] & -nhub['c_out'] & tri_region & +fuel_top & gv.graveyard.graveyard_region
            ))
            cells.append(openmc.Cell(
                name=f"pinch_wedge_{t_idx}_water_below",
                fill=self.water_mat,
                region=+nhub['c_in'] & -nhub['c_out'] & tri_region & -fuel_bot & gv.graveyard.graveyard_region
            ))

            # 4. Water gap between pinch fuel and central conformal control blade
            cells.append(openmc.Cell(
                name=f"pinch_wedge_{t_idx}_blade_gap_water",
                fill=self.water_mat,
                region=+nhub['c_out'] & -nhub['b_in'] & tri_region & gv.graveyard.graveyard_region
            ))

            # 5. Conformal Central Control Blade Layer 1 (hugging the inside of the pinch fuel!)
            pib_cell = openmc.Cell(
                name=f"central_conformal_inner_blade_{t_idx}",
                fill=lobe_inner_blade_univ,
                region=+nhub['b_in'] & -nhub['b_mid'] & tri_region & axial_blade
            )
            pib_cell.translation = (ncx, ncy, z_center_inner)
            pib_cell.rotation = (0.0, 0.0, start_deg)
            cells.append(pib_cell)

            # 6. Conformal Central Control Blade Layer 2 (hugging Layer 1 on the central trap side)
            pob_cell = openmc.Cell(
                name=f"central_conformal_outer_blade_{t_idx}",
                fill=lobe_outer_blade_univ,
                region=+nhub['b_mid'] & -nhub['b_out'] & tri_region & axial_blade
            )
            pob_cell.translation = (ncx, ncy, z_center_outer[t_idx])
            pob_cell.rotation = (0.0, 0.0, start_deg)
            cells.append(pob_cell)

            # 7. Water above and below the conformal central control blades
            cells.append(openmc.Cell(
                name=f"central_conformal_blade_{t_idx}_water_above",
                fill=self.water_mat,
                region=+nhub['b_in'] & -nhub['b_out'] & tri_region & +guide_top & gv.graveyard.graveyard_region
            ))
            cells.append(openmc.Cell(
                name=f"central_conformal_blade_{t_idx}_water_below",
                fill=self.water_mat,
                region=+nhub['b_in'] & -nhub['b_out'] & tri_region & -guide_bot & gv.graveyard.graveyard_region
            ))

            # 8. Central Triangular Flux-Trap Water Core (inside +nhub['b_out'] & tri_region)
            cells.append(openmc.Cell(
                name=f"central_triangular_flux_trap_water_{t_idx}",
                fill=self.water_mat,
                region=+nhub['b_out'] & tri_region & gv.graveyard.graveyard_region
            ))

        return cells