import openmc
import numpy as np
import config.global_vars as gv
from geometry.fuel_element import FuelElementGeometry
from geometry.control_blades.central_blades import central_blades_cl


def _clean_trig(ang_deg: float) -> tuple[float, float]:
    """
    Returns (cos, sin) with exact floating-point values for multiples of 30 degrees
    (snapping 0.0, +/-0.5, and +/-1.0) to prevent 1e-16 float drift on planes and hubs.
    """
    rad = np.radians(ang_deg % 360.0)
    c, s = float(np.cos(rad)), float(np.sin(rad))
    for exact in (0.0, 0.5, -0.5, 1.0, -1.0):
        if abs(c - exact) < 1e-14:
            c = exact
        if abs(s - exact) < 1e-14:
            s = exact
    return c, s


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

        # Fuel element radial dimensions (r_in = 3.0 cm, r_out = 7.1716 cm)
        self.r_in = float(self.element_factory.inner_thickness)
        self.r_out = float(np.round(self.element_factory.outer_thickness, 6))
        self.fuel_thickness = self.r_out - self.r_in
        self.R0 = float(np.round(self.r_in + self.fuel_thickness / 2.0, 6))

        # Conformal control blades
        # Used BOTH on the outside of the 3 main lobes AND hugging the inside
        # (central flux-trap side) of the 3 inward-curving pinch lobes!
        self.lobe_blade_builder = central_blades_cl(
            r_inner_override=self.r_out + gv.reflector.water_gap
        )
        self.lobe_blade_univs = self.lobe_blade_builder.create_geometry()
        self.r_blade_in = float(self.lobe_blade_builder.r_inner)
        self.r_blade_mid = float(self.lobe_blade_builder.r_midpoint)
        self.r_blade_out = float(self.lobe_blade_builder.r_out)

        # Distance of each of the 6 hubs from (0,0) is 2 * R0
        self.hub_dist = 2.0 * self.R0
        self.core_outer_radius = self.hub_dist + self.r_blade_out + gv.reflector.water_gap

        # Update global state for Beryllium reflector sizing
        gv.control_blade.rad_in_central = self.hub_dist + self.r_blade_in
        gv.control_blade.rad_out_central = self.hub_dist + self.r_blade_out

        mats = gv.materials.get_materials()
        self.water_mat = mats['water']
        self.al_mat = mats['aluminum']

        # Add fast O(1) exterior buffer cells to child universes so 1e-15 cm
        # coordinate-transformation rounding at ZCylinder/Plane borders never loses particles
        self._pad_child_universes()

    def _pad_child_universes(self) -> None:
        """
        Adds an exterior buffer cell outside the local bounding surfaces of the fuel
        and control blade universes. Because parent cells in Universe 9 strictly clip
        the geometry, these buffer cells are only ever entered if floating-point
        rotation/translation rounding places a boundary particle ~1e-15 cm outside
        the child universe's local surfaces.
        """
        # 1. Pad Fuel Element Universe (base_universe)
        u1_cells = list(self.base_universe.cells.values())
        assert u1_cells[0].region is not None
        side_clad_surfaces = u1_cells[0].region.get_surfaces()
        u1_cyls = sorted(
            [s for s in side_clad_surfaces.values() if isinstance(s, openmc.ZCylinder)],
            key=lambda c: float(c.r)
        )
        u1_r_in_surf, u1_r_out_surf = u1_cyls[0], u1_cyls[-1]
        u1_left_bound, _, _, u1_angle_bound = self.element_factory.get_planes()

        u1_buffer_reg = (
            -u1_r_in_surf
            | +u1_r_out_surf
            | -u1_left_bound
            | +u1_angle_bound
        )
        self.base_universe.add_cell(openmc.Cell(
            name="fuel_univ_float_drift_buffer",
            fill=self.al_mat,
            region=u1_buffer_reg
        ))

        # 2. Pad Inner Annular Blade Universe (lobe_blade_univs[0])
        sd = self.lobe_blade_builder.surface_dict
        assert sd is not None
        inner_cyl: openmc.ZCylinder = sd['inner_cyl']
        mid_cyl: openmc.ZCylinder = sd['mid_cyl']
        outer_cyl: openmc.ZCylinder = sd['outer_cyl']
        wedge_planes: list[openmc.Plane] = sd['plane_list']

        u2_buffer_reg = -inner_cyl | +mid_cyl
        self.lobe_blade_univs[0].add_cell(openmc.Cell(
            name="inner_blade_univ_float_drift_buffer",
            fill=self.water_mat,
            region=u2_buffer_reg
        ))

        # 3. Pad Outer Segmented Blade Universes (lobe_blade_univs[1:])
        plane_no = len(wedge_planes)
        for i, outer_u in enumerate(self.lobe_blade_univs[1:]):
            u3_buffer_reg = (
                -mid_cyl
                | +outer_cyl
                | -wedge_planes[i]
                | +wedge_planes[(i + 1) % plane_no]
            )
            outer_u.add_cell(openmc.Cell(
                name=f"outer_blade_{i+1}_univ_float_drift_buffer",
                fill=self.water_mat,
                region=u3_buffer_reg
            ))

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
        origin_planes: dict[int, openmc.Plane] = {}
        for ang in [30, 90, 150]:
            c, s = _clean_trig(ang)
            origin_planes[ang] = openmc.Plane(a=-s, b=c, c=0.0, d=0.0)

        def get_origin_pie_slice(ang1_deg: float, ang2_deg: float):
            c, s = _clean_trig(0.5 * (ang1_deg + ang2_deg))
            mx, my = 5.0 * c, 5.0 * s
            p1 = origin_planes[int(ang1_deg % 180)]
            p2 = origin_planes[int(ang2_deg % 180)]
            return _oriented_halfspace(p1, mx, my) & _oriented_halfspace(p2, mx, my)

        # 3 Positive Hub Centers (at 30°, 150°, 270°)
        pos_hub_angles = [30.0, 150.0, 270.0]
        pos_hubs = []
        for ang in pos_hub_angles:
            c, s = _clean_trig(ang)
            cx, cy = self.hub_dist * c, self.hub_dist * s

            c_l, s_l = _clean_trig(ang - 60.0)
            nx_l, ny_l = -s_l, c_l
            hex_plane_low = openmc.Plane(a=nx_l, b=ny_l, c=0.0, d=nx_l * cx + ny_l * cy)

            c_h, s_h = _clean_trig(ang + 60.0)
            nx_h, ny_h = -s_h, c_h
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

        # 3 Negative Hub Centers (at 90°, 210°, 330°)
        neg_hub_angles = [90.0, 210.0, 330.0]
        neg_hubs = []
        for ang in neg_hub_angles:
            c, s = _clean_trig(ang)
            cx, cy = self.hub_dist * c, self.hub_dist * s
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

            # Main lobe circular flux trap (r < r_in around pos_hub)
            cells.append(openmc.Cell(
                name=f"lobe_{lobe_idx}_flux_trap_water",
                fill=self.water_mat,
                region=-hub['c_in'] & gv.graveyard.graveyard_region
            ))

            for w_idx in range(4):
                start_deg = ang - 120.0 + w_idx * 60.0
                c_mid, s_mid = _clean_trig(start_deg + 30.0)
                rx = cx + self.R0 * c_mid
                ry = cy + self.R0 * s_mid

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
        # Each triangle contains 1 inward-curving pinch fuel wedge, conformal
        # control blades hugging its central-trap wall, and 1/6th of the
        # central triangular flux trap water!
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
            c_mid, s_mid = _clean_trig(0.5 * (a1 + a2))
            tx, ty = 2.0 * c_mid, 2.0 * s_mid
            tri_region = pie_slice & _oriented_halfspace(hex_plane, tx, ty)

            nhub = neg_hubs[nh_idx]
            ncx, ncy = nhub['cx'], nhub['cy']

            # Exclude the Positive Hub's inner flux trap (+pos_hubs[ph_idx]['c_in'])
            # so the triangle's corner at the Positive Hub never overlaps lobe_X_flux_trap_water!
            phub_c_in = pos_hubs[ph_idx]['c_in']
            safe_tri = tri_region & +phub_c_in

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
                region=+nhub['c_out'] & -nhub['b_in'] & safe_tri & gv.graveyard.graveyard_region
            ))

            # 5. Conformal Central Control Blade Layer 1 (hugging the inside of the pinch fuel)
            pib_cell = openmc.Cell(
                name=f"central_conformal_inner_blade_{t_idx}",
                fill=lobe_inner_blade_univ,
                region=+nhub['b_in'] & -nhub['b_mid'] & safe_tri & axial_blade
            )
            pib_cell.translation = (ncx, ncy, z_center_inner)
            pib_cell.rotation = (0.0, 0.0, start_deg)
            cells.append(pib_cell)

            # 6. Conformal Central Control Blade Layer 2 (hugging Layer 1 on the central trap side)
            pob_cell = openmc.Cell(
                name=f"central_conformal_outer_blade_{t_idx}",
                fill=lobe_outer_blade_univ,
                region=+nhub['b_mid'] & -nhub['b_out'] & safe_tri & axial_blade
            )
            pob_cell.translation = (ncx, ncy, z_center_outer[t_idx])
            pob_cell.rotation = (0.0, 0.0, start_deg)
            cells.append(pob_cell)

            # 7. Water above and below the conformal central control blades
            cells.append(openmc.Cell(
                name=f"central_conformal_blade_{t_idx}_water_above",
                fill=self.water_mat,
                region=+nhub['b_in'] & -nhub['b_out'] & safe_tri & +guide_top & gv.graveyard.graveyard_region
            ))
            cells.append(openmc.Cell(
                name=f"central_conformal_blade_{t_idx}_water_below",
                fill=self.water_mat,
                region=+nhub['b_in'] & -nhub['b_out'] & safe_tri & -guide_bot & gv.graveyard.graveyard_region
            ))

            # 8. Central Triangular Flux-Trap Water Core
            # Bounded by +nhub['b_out'] (inside the central cavity) and safe_tri (+phub_c_in)
            cells.append(openmc.Cell(
                name=f"central_triangular_flux_trap_water_{t_idx}",
                fill=self.water_mat,
                region=+nhub['b_out'] & safe_tri & gv.graveyard.graveyard_region
            ))

        return cells