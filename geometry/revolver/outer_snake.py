import openmc
import numpy as np
import config.global_vars as gv
from geometry.fuel_element import FuelElementGeometry
from geometry.control_blades.central_blades import central_blades_cl

class lobe_3:
    def __init__(self) -> None:
        self.element_factory = FuelElementGeometry()
        self.base_universe = self.element_factory.create_fuel_universe()

        # Fuel element radial dimensions (r_in = 4.0 cm, r_out = 8.3416 cm)
        self.r_in = self.element_factory.inner_thickness
        self.r_out = self.element_factory.outer_thickness
        self.fuel_thickness = self.r_out - self.r_in
        self.R0 = self.r_in + self.fuel_thickness / 2.0

        # 1. Lobe-hugging control blades (r = 8.3916 to 8.7916 cm around each main lobe hub)
        self.lobe_blade_builder = central_blades_cl(
            r_inner_override=self.r_out + gv.reflector.water_gap
        )
        self.lobe_blade_univs = self.lobe_blade_builder.create_geometry()
        self.r_blade_in = self.lobe_blade_builder.r_inner
        self.r_blade_mid = self.lobe_blade_builder.r_midpoint
        self.r_blade_out = self.lobe_blade_builder.r_out

        # 2. Central triangular flux-trap control assembly (r = 3.50 to 3.90 cm at origin)
        self.central_blade_builder = central_blades_cl(
            r_inner_override=gv.control_blade.central_trap_r_in
        )
        self.central_blade_univs = self.central_blade_builder.create_geometry()
        self.r_ctrl_in = self.central_blade_builder.r_inner
        self.r_ctrl_mid = self.central_blade_builder.r_midpoint
        self.r_ctrl_out = self.central_blade_builder.r_out

        # Distance of each of the 6 hubs from (0,0) is exactly 2 * R0 = 12.3416 cm
        self.hub_dist = 2.0 * self.R0
        # Outer radius of the core region (furthest lobe blade tip + water gap)
        self.core_outer_radius = self.hub_dist + self.r_blade_out + gv.reflector.water_gap

        # Update global state so Beryllium reflector & water classes size themselves around the 3 lobes
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
        Builds all fuel, control blade, and explicit water cells inside -core_outer_cyl
        using the exact 9-plane hexagonal/radial decomposition (no giant complement cell).
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

        # ---------------------------------------------------------------------
        # DEFINE THE 9 FUNDAMENTAL PLANES
        # 3 directions: alpha = 30 deg, 90 deg, 150 deg
        # Normal vector n_k = (-sin(alpha_k), cos(alpha_k))
        # For each direction k in {0, 1, 2}:
        #   P_zero[k] : plane through origin (d = 0)
        #   P_pos[k]  : hexagon edge plane at d = +d_hex
        #   P_neg[k]  : hexagon edge plane at d = -d_hex
        # ---------------------------------------------------------------------
        d_hex = self.hub_dist * np.cos(np.radians(30.0))  # 10.688139 cm
        angles_deg = [30.0, 90.0, 150.0]
        P_zero, P_pos, P_neg = [], [], []

        for ang in angles_deg:
            rad = np.radians(ang)
            nx, ny = -np.sin(rad), np.cos(rad)
            P_zero.append(openmc.Plane(a=nx, b=ny, c=0.0, d=0.0))
            P_pos.append(openmc.Plane(a=nx, b=ny, c=0.0, d=d_hex))
            P_neg.append(openmc.Plane(a=nx, b=ny, c=0.0, d=-d_hex))

        # 6 Hub centers:
        # Positive (Main Lobe) Hubs at 30 deg, 150 deg, 270 deg (-90 deg)
        # Negative (Pinch) Hubs at 90 deg, 210 deg (-150 deg), 330 deg (-30 deg)
        pos_hub_angles = [30.0, 150.0, -90.0]
        neg_hub_angles = [90.0, -150.0, -30.0]

        pos_hubs = []
        for i, ang in enumerate(pos_hub_angles):
            rad = np.radians(ang)
            cx, cy = self.hub_dist * np.cos(rad), self.hub_dist * np.sin(rad)
            pos_hubs.append({
                'cx': cx, 'cy': cy, 'ang': ang,
                'c_in': openmc.ZCylinder(x0=cx, y0=cy, r=self.r_in),
                'c_out': openmc.ZCylinder(x0=cx, y0=cy, r=self.r_out),
                'b_in': openmc.ZCylinder(x0=cx, y0=cy, r=self.r_blade_in),
                'b_mid': openmc.ZCylinder(x0=cx, y0=cy, r=self.r_blade_mid),
                'b_out': openmc.ZCylinder(x0=cx, y0=cy, r=self.r_blade_out),
            })

        neg_hubs = []
        for i, ang in enumerate(neg_hub_angles):
            rad = np.radians(ang)
            cx, cy = self.hub_dist * np.cos(rad), self.hub_dist * np.sin(rad)
            neg_hubs.append({
                'cx': cx, 'cy': cy, 'ang': ang,
                'c_in': openmc.ZCylinder(x0=cx, y0=cy, r=self.r_in),
                'c_out': openmc.ZCylinder(x0=cx, y0=cy, r=self.r_out),
            })

        # ---------------------------------------------------------------------
        # PART A: THE 3 MAIN LOBES (Outward-curving 240° lobes on pos_hubs)
        # Each main lobe has 4 wedges of 60°:
        #   Lobe 0 (Hub at  30°): wedges at [-90..-30, -30..30,  30..90,  90..150]
        #   Lobe 1 (Hub at 150°): wedges at [ 30.. 90,  90..150, 150..210, 210..270]
        #   Lobe 2 (Hub at -90°): wedges at [150..210, 210..270, -90..-30, -30..30]
        # ---------------------------------------------------------------------
        lobe_wedge_specs = [
            # Lobe 0 (Hub 0 at 30 deg, lies on P_zero[0], P_neg[1], P_neg[2])
            [
                (-90.0, +P_neg[1] & -P_neg[2]),
                (-30.0, +P_neg[2] & -P_zero[0]),
                ( 30.0, +P_zero[0] & -P_neg[1]),
                ( 90.0, +P_zero[0] & +P_neg[1]),
            ],
            # Lobe 1 (Hub 1 at 150 deg, lies on P_zero[2], P_pos[0], P_pos[1])
            [
                ( 30.0, +P_pos[0] & -P_pos[1]),
                ( 90.0, +P_pos[1] & -P_zero[2]),
                (150.0, +P_zero[2] & -P_pos[0]),
                (210.0, +P_zero[2] & +P_pos[0]),
            ],
            # Lobe 2 (Hub 2 at -90 deg, lies on P_zero[1], P_neg[0], P_pos[2])
            [
                (150.0, +P_pos[2] & -P_neg[0]),
                (210.0, -P_neg[0] & -P_zero[1]),
                (-90.0, +P_zero[1] & -P_pos[2]),
                (-30.0, +P_zero[1] & +P_pos[2]),
            ],
        ]

        lobe_inner_blade_univ = self.lobe_blade_univs[0]
        lobe_outer_blade_univ = self.lobe_blade_univs[1]  # 0 to 60 deg base universe
        blade_counter = 0

        for lobe_idx, hub in enumerate(pos_hubs):
            cx, cy = hub['cx'], hub['cy']

            # 1. Explicit water cell inside the circular flux trap of this lobe (r < 4.0 cm)
            cells.append(openmc.Cell(
                name=f"lobe_{lobe_idx}_flux_trap_water",
                fill=self.water_mat,
                region=-hub['c_in'] & gv.graveyard.graveyard_region
            ))

            # 2. The 4 outward 60° sectors of this lobe
            for w_idx, (start_deg, sector_planes) in enumerate(lobe_wedge_specs[lobe_idx]):
                # 2a. Fuel wedge (r_in to r_out, z = 0 to height)
                f_reg = +hub['c_in'] & -hub['c_out'] & sector_planes & axial_fuel
                f_cell = openmc.Cell(
                    name=f"lobe_{lobe_idx}_fuel_wedge_{w_idx}",
                    fill=self.base_universe,
                    region=f_reg
                )
                f_cell.translation = (cx, cy, 0.0)
                f_cell.rotation = (0.0, 0.0, start_deg)
                cells.append(f_cell)

                # 2b. Water above and below this fuel wedge
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

                # 2c. Water gap between fuel and lobe control blade (r_out to r_blade_in)
                cells.append(openmc.Cell(
                    name=f"lobe_{lobe_idx}_wedge_{w_idx}_blade_gap_water",
                    fill=self.water_mat,
                    region=+hub['c_out'] & -hub['b_in'] & sector_planes & gv.graveyard.graveyard_region
                ))

                # 2d. Inner Lobe Control Blade (r_blade_in to r_blade_mid)
                ib_reg = +hub['b_in'] & -hub['b_mid'] & sector_planes & axial_blade
                ib_cell = openmc.Cell(
                    name=f"lobe_{lobe_idx}_inner_blade_{w_idx}",
                    fill=lobe_inner_blade_univ,
                    region=ib_reg
                )
                ib_cell.translation = (cx, cy, z_lobe_inner)
                ib_cell.rotation = (0.0, 0.0, start_deg)
                cells.append(ib_cell)

                # 2e. Outer Lobe Control Blade (r_blade_mid to r_blade_out)
                ob_reg = +hub['b_mid'] & -hub['b_out'] & sector_planes & axial_blade
                ob_cell = openmc.Cell(
                    name=f"lobe_{lobe_idx}_outer_blade_{w_idx}",
                    fill=lobe_outer_blade_univ,
                    region=ob_reg
                )
                ob_cell.translation = (cx, cy, z_lobe_outer[blade_counter])
                ob_cell.rotation = (0.0, 0.0, start_deg)
                cells.append(ob_cell)

                # 2f. Water above/below lobe control blades (if graveyard extends beyond guide_top/bot)
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

                # 2g. Explicit Outer Water between lobe control blade and Beryllium reflector
                cells.append(openmc.Cell(
                    name=f"lobe_{lobe_idx}_outer_water_{w_idx}",
                    fill=self.water_mat,
                    region=+hub['b_out'] & -core_outer_cyl & sector_planes & gv.graveyard.graveyard_region
                ))

                blade_counter += 1

        # ---------------------------------------------------------------------
        # PART B: THE 3 OUTER PINCH BAYS (Outside the hexagon edges at 90°, 210°, 330°)
        # Each pinch bay is bounded by the two hexagon edge planes meeting at neg_hub[k]
        # and extends outward to core_outer_cyl, plus the r < r_in circle of neg_hub[k].
        # ---------------------------------------------------------------------
        pinch_bay_HexOutside = [
            +P_pos[0] & -P_neg[2],  # Top bay around Neg Hub 0 (90 deg)
            -P_pos[1] & +P_pos[2],  # Bottom-left bay around Neg Hub 1 (-150 deg)
            -P_neg[0] & +P_neg[1],  # Bottom-right bay around Neg Hub 2 (-30 deg)
        ]

        for p_idx, nhub in enumerate(neg_hubs):
            # 1. Inner circle (r < 4.0 cm) of the negative pinch hub
            cells.append(openmc.Cell(
                name=f"pinch_hub_{p_idx}_inner_water",
                fill=self.water_mat,
                region=-nhub['c_in'] & -core_outer_cyl & gv.graveyard.graveyard_region
            ))
            # 2. Outer wedge beyond the hexagon edge planes (r >= 4.0 cm from neg_hub)
            cells.append(openmc.Cell(
                name=f"pinch_bay_{p_idx}_outer_water",
                fill=self.water_mat,
                region=+nhub['c_in'] & pinch_bay_HexOutside[p_idx] & -core_outer_cyl & gv.graveyard.graveyard_region
            ))

        # ---------------------------------------------------------------------
        # PART C: THE 6 EQUILATERAL TRIANGLES OF THE CENTRAL HEXAGON
        # Inside the hexagon of hub centers, the 3 origin planes P_zero[0..2]
        # divide the hexagon into 6 equilateral triangles. Each triangle contains:
        #   - 1 inward-curving fuel wedge (+nhub['c_in'] & -nhub['c_out'])
        #   - 1 explicit central water region between the central control assembly
        #     (+c_ctrl_out) and the inward-curving fuel wedge (+nhub['c_out'])
        #   - 1 slice of the central flux-trap control assembly (-c_ctrl_out)
        # ---------------------------------------------------------------------
        c_ctrl_in = self.central_blade_builder.surface_dict['inner_cyl']
        c_ctrl_mid = self.central_blade_builder.surface_dict['mid_cyl']
        c_ctrl_out = self.central_blade_builder.surface_dict['outer_cyl']

        # Each tuple: (neg_hub_index, start_angle_deg, triangle_plane_region, central_blade_sector_idx)
        central_triangles = [
            # Neg Hub 0 (90 deg):
            (0,  -90.0, +P_zero[0] & -P_zero[1] & +P_neg[2], 1),  # Seg 4 (30° to 90° from origin)
            (0, -150.0, +P_zero[1] & -P_zero[2] & -P_pos[0], 2),  # Seg 5 (90° to 150° from origin)
            # Neg Hub 1 (-150 deg):
            (1,   30.0, +P_zero[2] & -P_zero[0] & +P_pos[1], 3),  # Seg 10 (150° to 210° from origin)
            (1,  -30.0, +P_zero[0] & -P_zero[1] & -P_pos[2], 4),  # Seg 11 (210° to 270° from origin)
            # Neg Hub 2 (-30 deg):
            (2,  150.0, +P_zero[1] & -P_zero[2] & +P_neg[0], 5),  # Seg 16 (270° to 330° from origin)
            (2,   90.0, +P_zero[2] & -P_zero[0] & -P_neg[1], 0),  # Seg 17 (330° to 30° from origin)
        ]

        for t_idx, (nh_idx, start_deg, tri_planes, cb_idx) in enumerate(central_triangles):
            nhub = neg_hubs[nh_idx]
            cx, cy = nhub['cx'], nhub['cy']

            # 1. Inward-curving fuel wedge (sgn = -1)
            pf_reg = +nhub['c_in'] & -nhub['c_out'] & tri_planes & axial_fuel
            pf_cell = openmc.Cell(
                name=f"pinch_fuel_wedge_{t_idx}",
                fill=self.base_universe,
                region=pf_reg
            )
            pf_cell.translation = (cx, cy, 0.0)
            pf_cell.rotation = (0.0, 0.0, start_deg)
            cells.append(pf_cell)

            # 2. Water above and below this inward-curving fuel wedge
            cells.append(openmc.Cell(
                name=f"pinch_wedge_{t_idx}_water_above",
                fill=self.water_mat,
                region=+nhub['c_in'] & -nhub['c_out'] & tri_planes & +fuel_top & gv.graveyard.graveyard_region
            ))
            cells.append(openmc.Cell(
                name=f"pinch_wedge_{t_idx}_water_below",
                fill=self.water_mat,
                region=+nhub['c_in'] & -nhub['c_out'] & tri_planes & -fuel_bot & gv.graveyard.graveyard_region
            ))

            # 3. Explicit Central Triangular Flux-Trap Water (between central control rod and pinch fuel)
            cells.append(openmc.Cell(
                name=f"central_flux_trap_water_sector_{t_idx}",
                fill=self.water_mat,
                region=+c_ctrl_out & +nhub['c_out'] & tri_planes & gv.graveyard.graveyard_region
            ))

        # ---------------------------------------------------------------------
        # PART D: CENTRAL FLUX-TRAP CONTROL MECHANISM (Centered at (0,0))
        # Fits cleanly inside r = 3.90 cm within the central triangular cavity!
        # ---------------------------------------------------------------------
        # 1. Innermost central flux-trap water core (r < 3.50 cm)
        cells.append(openmc.Cell(
            name="central_flux_trap_inner_water_core",
            fill=self.water_mat,
            region=-c_ctrl_in & gv.graveyard.graveyard_region
        ))

        # 2. Central inner annular regulating/safety blade (r = 3.50 to 3.70 cm)
        c_inner_blade_cell = openmc.Cell(
            name="central_trap_inner_blade_slot",
            fill=self.central_blade_univs[0],
            region=+c_ctrl_in & -c_ctrl_mid & axial_blade
        )
        c_inner_blade_cell.translation = (0.0, 0.0, z_center_inner)
        cells.append(c_inner_blade_cell)

        # 3. Central outer 6 segmented blades (r = 3.70 to 3.90 cm)
        c_planes = self.central_blade_builder.surface_dict['plane_list']
        num_c_planes = len(c_planes)
        for i in range(num_c_planes):
            w_reg = +c_planes[i] & -c_planes[(i + 1) % num_c_planes]
            c_outer_cell = openmc.Cell(
                name=f"central_trap_outer_blade_slot_{i+1}",
                fill=self.central_blade_univs[i + 1],
                region=+c_ctrl_mid & -c_ctrl_out & w_reg & axial_blade
            )
            c_outer_cell.translation = (0.0, 0.0, z_center_outer[i])
            cells.append(c_outer_cell)

        # 4. Water above/below central control assembly if graveyard extends past guide planes
        cells.append(openmc.Cell(
            name="central_trap_blade_water_above",
            fill=self.water_mat,
            region=+c_ctrl_in & -c_ctrl_out & +guide_top & gv.graveyard.graveyard_region
        ))
        cells.append(openmc.Cell(
            name="central_trap_blade_water_below",
            fill=self.water_mat,
            region=+c_ctrl_in & -c_ctrl_out & -guide_bot & gv.graveyard.graveyard_region
        ))

        return cells