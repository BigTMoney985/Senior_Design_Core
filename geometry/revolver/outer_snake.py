from dataclasses import dataclass
import openmc
import numpy as np
import config.global_vars as gv
from geometry.fuel_element import FuelElementGeometry
from geometry.control_blades.central_blades import central_blades_cl


# =============================================================================
# GEOMETRY HELPER FUNCTIONS & DATA STRUCTURES
# =============================================================================

def _clean_trig(angle_deg: float) -> tuple[float, float]:
    """
    Returns (cos, sin) with exact floating-point values for multiples of 30 degrees
    (snapping 0.0, +/-0.5, and +/-1.0) to prevent 1e-16 float drift on planes and hubs.
    """
    rad = np.radians(angle_deg % 360.0)
    cos_val, sin_val = float(np.cos(rad)), float(np.sin(rad))
    for exact in (0.0, 0.5, -0.5, 1.0, -1.0):
        if abs(cos_val - exact) < 1e-14:
            cos_val = exact
        if abs(sin_val - exact) < 1e-14:
            sin_val = exact
    return cos_val, sin_val


def _oriented_halfspace(plane: openmc.Plane, ref_x: float, ref_y: float):
    """
    Returns +plane or -plane so that the reference point (ref_x, ref_y, 0.0)
    lies strictly inside the returned halfspace.
    """
    val = plane.evaluate((ref_x, ref_y, 0.0))
    return +plane if val > 0 else -plane


@dataclass(frozen=True)
class HubGeometry:
    """Stores the center coordinates, concentric ZCylinders, and chord planes for a hub."""
    cx: float
    cy: float
    angle_deg: float
    cyl_fuel_in: openmc.ZCylinder
    cyl_fuel_out: openmc.ZCylinder
    cyl_blade_in: openmc.ZCylinder
    cyl_blade_mid: openmc.ZCylinder
    cyl_blade_out: openmc.ZCylinder
    hex_plane_low: openmc.Plane | None = None
    hex_plane_high: openmc.Plane | None = None


@dataclass(frozen=True)
class PinchTriangleSpec:
    """Defines one of the 6 inner equilateral triangles around the central flux trap."""
    sector_start_deg: float
    sector_end_deg: float
    pos_hub_index: int
    use_high_hex_plane: bool
    neg_hub_index: int
    local_rotation_deg: float


# =============================================================================
# MAIN 3-LOBE SERPENTINE CORE BUILDER
# =============================================================================

class lobe_3:
    def __init__(self) -> None:
        # 1. Build the 60-degree base fuel wedge universe
        self.element_factory = FuelElementGeometry()
        self.base_universe = self.element_factory.create_fuel_universe()

        # Fuel element radial dimensions (r_in = 3.0 cm, r_out = 7.1716 cm)
        self.r_in = float(self.element_factory.inner_thickness)
        self.r_out = float(np.round(self.element_factory.outer_thickness, 6))
        self.fuel_thickness = self.r_out - self.r_in
        self.R0 = float(np.round(self.r_in + self.fuel_thickness / 2.0, 6))

        # 2. Build the conformal control blade universes
        self.lobe_blade_builder = central_blades_cl(
            r_inner_override=self.r_out + gv.reflector.water_gap
        )
        self.lobe_blade_univs = self.lobe_blade_builder.create_geometry()
        self.r_blade_in = float(self.lobe_blade_builder.r_inner)
        self.r_blade_mid = float(self.lobe_blade_builder.r_midpoint)
        self.r_blade_out = float(self.lobe_blade_builder.r_out)

        # 3. Hub spacing and overall core outer radius
        # Each of the 6 hubs sits at a radial distance of 2 * R0 from the origin (0,0)
        self.hub_dist = 2.0 * self.R0
        self.core_outer_radius = self.hub_dist + self.r_blade_out + gv.reflector.water_gap

        # Update global state for outer Beryllium reflector sizing
        gv.control_blade.rad_in_central = self.hub_dist + self.r_blade_in
        gv.control_blade.rad_out_central = self.hub_dist + self.r_blade_out

        # 4. Materials
        mats = gv.materials.get_materials()
        self.water_mat = mats['water']
        self.al_mat = mats['aluminum']

        # 5. Pad child universes against 1e-15 cm coordinate-transformation float drift
        self._pad_child_universes()

        # 6. Assign distinct blade universes for Main Lobes vs. Central Flux Trap:
        # - Inner blade layer (Layer 1): annular blade (already has Aluminum follower)
        # - Main-lobe outer 60-deg wedge blade (Layer 2): default Be-metal transparent section
        # - Central flux-trap outer 60-deg wedge blade (Layer 2): Aluminum transparent section
        self.inner_blade_univ = self.lobe_blade_univs[0]
        self.outer_lobe_blade_univ = self.lobe_blade_univs[1]
        self.central_outer_blade_univ = self._create_aluminum_outer_blade_universe(
            base_outer_blade_univ=self.lobe_blade_univs[1]
        )

    def _create_aluminum_outer_blade_universe(
        self,
        base_outer_blade_univ: openmc.Universe,
    ) -> openmc.Universe:
        """
        Creates a copy of the 60-degree wedge control blade universe for the central
        flux-trap blades, replacing the Be-metal transparent section with Aluminum.
        """
        central_blade_cells: list[openmc.Cell] = []
        for cell in base_outer_blade_univ.cells.values():
            is_transparent_follower = "transparent section" in (cell.name or "").lower()
            cell_fill = self.al_mat if is_transparent_follower else cell.fill
            cell_name = (
                f"{cell.name} (Al)" if is_transparent_follower else cell.name
            )
            central_blade_cells.append(openmc.Cell(
                name=cell_name,
                fill=cell_fill,
                region=cell.region,
            ))

        return openmc.Universe(
            name="central_trap_outer_blade_al_universe",
            cells=central_blade_cells,
        )

    def _pad_child_universes(self) -> None:
        """
        Adds an exterior buffer cell outside the local bounding surfaces of the fuel
        and control blade universes. Because parent cells in Universe 9 strictly clip
        the geometry, these buffer cells are only ever entered if floating-point
        rotation/translation rounding places a boundary particle ~1e-15 cm outside
        the child universe's local surfaces.
        """
        # 1. Pad Fuel Element Universe (base_universe)
        all_u1_surfaces: dict[int, openmc.Surface] = {}
        for cell in self.base_universe.cells.values():
            if cell.region is not None:
                all_u1_surfaces.update(cell.region.get_surfaces())

        u1_cyls = sorted(
            [s for s in all_u1_surfaces.values() if isinstance(s, openmc.ZCylinder)],
            key=lambda c: float(c.r)  # type: ignore
        )
        u1_left_bound, _, _, u1_angle_bound = self.element_factory.get_planes()

        u1_buffer_terms = []
        if u1_cyls:
            u1_r_in_surf, u1_r_out_surf = u1_cyls[0], u1_cyls[-1]
            u1_buffer_terms.extend([-u1_r_in_surf, +u1_r_out_surf])
        if u1_left_bound.id in all_u1_surfaces:
            u1_buffer_terms.append(-u1_left_bound)
        if u1_angle_bound.id in all_u1_surfaces:
            u1_buffer_terms.append(+u1_angle_bound)

        if u1_buffer_terms:
            self.base_universe.add_cell(openmc.Cell(
                name="fuel_univ_float_drift_buffer",
                fill=self.al_mat,
                region=openmc.Union(u1_buffer_terms),
            ))

        # 2. Pad Inner Annular Blade Universe (lobe_blade_univs[0])
        sd = self.lobe_blade_builder.surface_dict
        assert sd is not None
        inner_cyl: openmc.ZCylinder = sd['inner_cyl']
        mid_cyl: openmc.ZCylinder = sd['mid_cyl']
        outer_cyl: openmc.ZCylinder = sd['outer_cyl']
        wedge_planes: list[openmc.Plane] = sd['plane_list']

        u2_surfaces: dict[int, openmc.Surface] = {}
        for cell in self.lobe_blade_univs[0].cells.values():
            if cell.region is not None:
                u2_surfaces.update(cell.region.get_surfaces())

        if inner_cyl.id in u2_surfaces and mid_cyl.id in u2_surfaces:
            self.lobe_blade_univs[0].add_cell(openmc.Cell(
                name="inner_blade_univ_float_drift_buffer",
                fill=self.water_mat,
                region=-inner_cyl | +mid_cyl,
            ))

        # 3. Pad Outer Segmented Blade Universes (lobe_blade_univs[1:])
        plane_no = len(wedge_planes)
        for i, outer_u in enumerate(self.lobe_blade_univs[1:]):
            u3_surfaces: dict[int, openmc.Surface] = {}
            for cell in outer_u.cells.values():
                if cell.region is not None:
                    u3_surfaces.update(cell.region.get_surfaces())

            if mid_cyl.id in u3_surfaces and outer_cyl.id in u3_surfaces:
                u3_buffer_reg = (
                    -mid_cyl
                    | +outer_cyl
                    | -wedge_planes[i]
                    | +wedge_planes[(i + 1) % plane_no]
                )
                outer_u.add_cell(openmc.Cell(
                    name=f"outer_blade_{i+1}_univ_float_drift_buffer",
                    fill=self.water_mat,
                    region=u3_buffer_reg,
                ))

    def _create_hub(self, angle_deg: float, include_hex_planes: bool) -> HubGeometry:
        """Creates the concentric ZCylinders and optional hexagonal chord planes for a hub."""
        cos_a, sin_a = _clean_trig(angle_deg)
        cx = self.hub_dist * cos_a
        cy = self.hub_dist * sin_a

        hex_plane_low = None
        hex_plane_high = None
        if include_hex_planes:
            cos_low, sin_low = _clean_trig(angle_deg - 60.0)
            nx_low, ny_low = -sin_low, cos_low
            hex_plane_low = openmc.Plane(
                a=nx_low, b=ny_low, c=0.0, d=nx_low * cx + ny_low * cy
            )

            cos_high, sin_high = _clean_trig(angle_deg + 60.0)
            nx_high, ny_high = -sin_high, cos_high
            hex_plane_high = openmc.Plane(
                a=nx_high, b=ny_high, c=0.0, d=nx_high * cx + ny_high * cy
            )

        return HubGeometry(
            cx=cx,
            cy=cy,
            angle_deg=angle_deg,
            cyl_fuel_in=openmc.ZCylinder(x0=cx, y0=cy, r=self.r_in),
            cyl_fuel_out=openmc.ZCylinder(x0=cx, y0=cy, r=self.r_out),
            cyl_blade_in=openmc.ZCylinder(x0=cx, y0=cy, r=self.r_blade_in),
            cyl_blade_mid=openmc.ZCylinder(x0=cx, y0=cy, r=self.r_blade_mid),
            cyl_blade_out=openmc.ZCylinder(x0=cx, y0=cy, r=self.r_blade_out),
            hex_plane_low=hex_plane_low,
            hex_plane_high=hex_plane_high,
        )

    def _build_lobe_wedge_sector(
        self,
        lobe_idx: int,
        wedge_idx: int,
        hub: HubGeometry,
        sector_planes: openmc.Region,
        start_deg: float,
        z_lobe_inner: float,
        z_lobe_outer_pos: float,
        fuel_top: openmc.ZPlane,
        fuel_bot: openmc.ZPlane,
        guide_top: openmc.ZPlane,
        guide_bot: openmc.ZPlane,
        core_outer_cyl: openmc.ZCylinder,
    ) -> list[openmc.Cell]:
        """
        Builds all radial and axial cells within a single 60-degree wedge sector
        of an outward-curving main lobe.
        """
        axial_fuel = +fuel_bot & -fuel_top
        axial_blade = +guide_bot & -guide_top
        graveyard = gv.graveyard.graveyard_region

        fuel_radial = +hub.cyl_fuel_in & -hub.cyl_fuel_out & sector_planes
        gap_radial = +hub.cyl_fuel_out & -hub.cyl_blade_in & sector_planes
        inner_blade_radial = +hub.cyl_blade_in & -hub.cyl_blade_mid & sector_planes
        outer_blade_radial = +hub.cyl_blade_mid & -hub.cyl_blade_out & sector_planes
        both_blades_radial = +hub.cyl_blade_in & -hub.cyl_blade_out & sector_planes
        outer_water_radial = +hub.cyl_blade_out & -core_outer_cyl & sector_planes

        # 1. Fuel wedge and axial water above/below
        fuel_cell = openmc.Cell(
            name=f"lobe_{lobe_idx}_fuel_wedge_{wedge_idx}",
            fill=self.base_universe,
            region=fuel_radial & axial_fuel,
        )
        fuel_cell.translation = (hub.cx, hub.cy, 0.0)
        fuel_cell.rotation = (0.0, 0.0, start_deg)

        fuel_water_above = openmc.Cell(
            name=f"lobe_{lobe_idx}_wedge_{wedge_idx}_water_above",
            fill=self.water_mat,
            region=fuel_radial & +fuel_top & graveyard,
        )
        fuel_water_below = openmc.Cell(
            name=f"lobe_{lobe_idx}_wedge_{wedge_idx}_water_below",
            fill=self.water_mat,
            region=fuel_radial & -fuel_bot & graveyard,
        )

        # 2. Water gap between fuel and control blade
        blade_gap_water = openmc.Cell(
            name=f"lobe_{lobe_idx}_wedge_{wedge_idx}_blade_gap_water",
            fill=self.water_mat,
            region=gap_radial & graveyard,
        )

        # 3. Inner (annular) and Outer (60-deg wedge with Be follower) control blades
        inner_blade_cell = openmc.Cell(
            name=f"lobe_{lobe_idx}_inner_blade_{wedge_idx}",
            fill=self.inner_blade_univ,
            region=inner_blade_radial & axial_blade,
        )
        inner_blade_cell.translation = (hub.cx, hub.cy, z_lobe_inner)
        inner_blade_cell.rotation = (0.0, 0.0, start_deg)

        outer_blade_cell = openmc.Cell(
            name=f"lobe_{lobe_idx}_outer_blade_{wedge_idx}",
            fill=self.outer_lobe_blade_univ,
            region=outer_blade_radial & axial_blade,
        )
        outer_blade_cell.translation = (hub.cx, hub.cy, z_lobe_outer_pos)
        outer_blade_cell.rotation = (0.0, 0.0, start_deg)

        # 4. Water above/below control blades and outside blade to core boundary
        blade_water_above = openmc.Cell(
            name=f"lobe_{lobe_idx}_blade_{wedge_idx}_water_above",
            fill=self.water_mat,
            region=both_blades_radial & +guide_top & graveyard,
        )
        blade_water_below = openmc.Cell(
            name=f"lobe_{lobe_idx}_blade_{wedge_idx}_water_below",
            fill=self.water_mat,
            region=both_blades_radial & -guide_bot & graveyard,
        )
        outer_water = openmc.Cell(
            name=f"lobe_{lobe_idx}_outer_water_{wedge_idx}",
            fill=self.water_mat,
            region=outer_water_radial & graveyard,
        )

        return [
            fuel_cell,
            fuel_water_above,
            fuel_water_below,
            blade_gap_water,
            inner_blade_cell,
            outer_blade_cell,
            blade_water_above,
            blade_water_below,
            outer_water,
        ]

    def _build_pinch_triangle(
        self,
        tri_idx: int,
        spec: PinchTriangleSpec,
        pie_slice: openmc.Region,
        pos_hub: HubGeometry,
        neg_hub: HubGeometry,
        z_center_inner: float,
        z_center_outer_pos: float,
        fuel_top: openmc.ZPlane,
        fuel_bot: openmc.ZPlane,
        guide_top: openmc.ZPlane,
        guide_bot: openmc.ZPlane,
    ) -> list[openmc.Cell]:
        """
        Builds all cells inside one of the 6 inner equilateral triangles, using the
        Aluminum-follower 60-degree wedge universe for the blade closest to the central trap.
        """
        axial_fuel = +fuel_bot & -fuel_top
        axial_blade = +guide_bot & -guide_top
        graveyard = gv.graveyard.graveyard_region

        hex_plane = (
            pos_hub.hex_plane_high if spec.use_high_hex_plane else pos_hub.hex_plane_low
        )
        assert hex_plane is not None

        mid_angle = 0.5 * (spec.sector_start_deg + spec.sector_end_deg)
        cos_mid, sin_mid = _clean_trig(mid_angle)
        test_x, test_y = 2.0 * cos_mid, 2.0 * sin_mid
        tri_region = pie_slice & _oriented_halfspace(hex_plane, test_x, test_y)

        # Exclude the Positive Hub's inner flux trap (+pos_hub.cyl_fuel_in) so the
        # triangle corner at the Positive Hub never overlaps lobe_X_flux_trap_water
        safe_tri = tri_region & +pos_hub.cyl_fuel_in

        # 1. Outer concave pocket water behind the pinch fuel wedge
        hub_inner_water = openmc.Cell(
            name=f"pinch_triangle_{tri_idx}_hub_inner_water",
            fill=self.water_mat,
            region=-neg_hub.cyl_fuel_in & tri_region & graveyard,
        )

        # 2. Inward-curving pinch fuel wedge and axial water above/below
        fuel_radial = +neg_hub.cyl_fuel_in & -neg_hub.cyl_fuel_out & tri_region
        pinch_fuel_cell = openmc.Cell(
            name=f"pinch_fuel_wedge_{tri_idx}",
            fill=self.base_universe,
            region=fuel_radial & axial_fuel,
        )
        pinch_fuel_cell.translation = (neg_hub.cx, neg_hub.cy, 0.0)
        pinch_fuel_cell.rotation = (0.0, 0.0, spec.local_rotation_deg)

        pinch_water_above = openmc.Cell(
            name=f"pinch_wedge_{tri_idx}_water_above",
            fill=self.water_mat,
            region=fuel_radial & +fuel_top & graveyard,
        )
        pinch_water_below = openmc.Cell(
            name=f"pinch_wedge_{tri_idx}_water_below",
            fill=self.water_mat,
            region=fuel_radial & -fuel_bot & graveyard,
        )

        # 3. Water gap between pinch fuel wedge and central conformal blades
        blade_gap_water = openmc.Cell(
            name=f"pinch_wedge_{tri_idx}_blade_gap_water",
            fill=self.water_mat,
            region=+neg_hub.cyl_fuel_out & -neg_hub.cyl_blade_in & safe_tri & graveyard,
        )

        # 4. Central Conformal Control Blades:
        #    - Layer 1 (inner_blade_univ): annular blade hugging the pinch fuel
        #    - Layer 2 (central_outer_blade_univ): 60-deg wedge blade closest to the
        #      central flux trap, using Aluminum for its transparent section!
        central_inner_blade = openmc.Cell(
            name=f"central_conformal_inner_blade_{tri_idx}",
            fill=self.inner_blade_univ,
            region=+neg_hub.cyl_blade_in & -neg_hub.cyl_blade_mid & safe_tri & axial_blade,
        )
        central_inner_blade.translation = (neg_hub.cx, neg_hub.cy, z_center_inner)
        central_inner_blade.rotation = (0.0, 0.0, spec.local_rotation_deg)

        central_outer_blade = openmc.Cell(
            name=f"central_conformal_outer_blade_{tri_idx}",
            fill=self.central_outer_blade_univ,
            region=+neg_hub.cyl_blade_mid & -neg_hub.cyl_blade_out & safe_tri & axial_blade,
        )
        central_outer_blade.translation = (neg_hub.cx, neg_hub.cy, z_center_outer_pos)
        central_outer_blade.rotation = (0.0, 0.0, spec.local_rotation_deg)

        # 5. Water above/below central blades and inside the central triangular flux trap
        both_blades_radial = +neg_hub.cyl_blade_in & -neg_hub.cyl_blade_out & safe_tri
        blade_water_above = openmc.Cell(
            name=f"central_conformal_blade_{tri_idx}_water_above",
            fill=self.water_mat,
            region=both_blades_radial & +guide_top & graveyard,
        )
        blade_water_below = openmc.Cell(
            name=f"central_conformal_blade_{tri_idx}_water_below",
            fill=self.water_mat,
            region=both_blades_radial & -guide_bot & graveyard,
        )

        central_trap_water = openmc.Cell(
            name=f"central_triangular_flux_trap_water_{tri_idx}",
            fill=self.water_mat,
            region=+neg_hub.cyl_blade_out & safe_tri & graveyard,
        )

        return [
            hub_inner_water,
            pinch_fuel_cell,
            pinch_water_above,
            pinch_water_below,
            blade_gap_water,
            central_inner_blade,
            central_outer_blade,
            blade_water_above,
            blade_water_below,
            central_trap_water,
        ]

    def build_clover_cells(
        self,
        core_outer_cyl: openmc.ZCylinder,
        z_lobe_inner: float = -162.5,
        z_lobe_outer: list[float] | None = None,
        z_center_inner: float = -162.5,
        z_center_outer: list[float] | None = None,
    ) -> list[openmc.Cell]:
        """
        Builds the 18 fuel wedges, 12 outer-lobe conformal control blades (Be follower),
        6 central-pinch conformal control blades hugging the central flux trap (Al follower),
        and explicit disjoint water cells (zero global complement).
        """
        if z_lobe_outer is None:
            z_lobe_outer = [0.0] * 12
        if z_center_outer is None:
            z_center_outer = [0.0] * 6

        cells: list[openmc.Cell] = []

        # Axial bounding planes
        fuel_top = openmc.ZPlane(z0=gv.fuel.height)
        fuel_bot = openmc.ZPlane(z0=0.0)
        guide_bot = openmc.ZPlane(z0=self.lobe_blade_builder.guide_bottom)
        guide_top = openmc.ZPlane(z0=self.lobe_blade_builder.end)

        # 3 Planes through the origin at 30°, 90°, and 150° dividing space into 6 pie slices
        origin_planes: dict[int, openmc.Plane] = {}
        for ang in (30, 90, 150):
            cos_a, sin_a = _clean_trig(ang)
            origin_planes[ang] = openmc.Plane(a=-sin_a, b=cos_a, c=0.0, d=0.0)

        def get_origin_pie_slice(ang1_deg: float, ang2_deg: float) -> openmc.Region:
            cos_mid, sin_mid = _clean_trig(0.5 * (ang1_deg + ang2_deg))
            mx, my = 5.0 * cos_mid, 5.0 * sin_mid
            p1 = origin_planes[int(ang1_deg % 180)]
            p2 = origin_planes[int(ang2_deg % 180)]
            return _oriented_halfspace(p1, mx, my) & _oriented_halfspace(p2, mx, my)

        # 3 Positive Hubs (Main Lobes at 30°, 150°, 270°) & 3 Negative Hubs (Pinch Lobes at 90°, 210°, 330°)
        pos_hubs = [
            self._create_hub(ang, include_hex_planes=True) for ang in (30.0, 150.0, 270.0)
        ]
        neg_hubs = [
            self._create_hub(ang, include_hex_planes=False) for ang in (90.0, 210.0, 330.0)
        ]

        # =====================================================================
        # PART A: THE 3 MAIN LOBES (Outward-curving 240° lobes on pos_hubs)
        # =====================================================================
        blade_counter = 0
        for lobe_idx, hub in enumerate(pos_hubs):
            assert hub.hex_plane_low is not None and hub.hex_plane_high is not None

            # Circular water flux trap inside the Positive Hub (r < r_in)
            cells.append(openmc.Cell(
                name=f"lobe_{lobe_idx}_flux_trap_water",
                fill=self.water_mat,
                region=-hub.cyl_fuel_in & gv.graveyard.graveyard_region,
            ))

            # 4 outward-curving 60° wedges per Main Lobe
            for wedge_idx in range(4):
                start_deg = hub.angle_deg - 120.0 + wedge_idx * 60.0
                cos_mid, sin_mid = _clean_trig(start_deg + 30.0)
                ref_x = hub.cx + self.R0 * cos_mid
                ref_y = hub.cy + self.R0 * sin_mid

                if wedge_idx in (0, 1):
                    pie_slice = get_origin_pie_slice(hub.angle_deg - 60.0, hub.angle_deg)
                else:
                    pie_slice = get_origin_pie_slice(hub.angle_deg, hub.angle_deg + 60.0)

                sector_planes = (
                    pie_slice
                    & _oriented_halfspace(hub.hex_plane_low, ref_x, ref_y)
                    & _oriented_halfspace(hub.hex_plane_high, ref_x, ref_y)
                )

                cells.extend(self._build_lobe_wedge_sector(
                    lobe_idx=lobe_idx,
                    wedge_idx=wedge_idx,
                    hub=hub,
                    sector_planes=sector_planes,
                    start_deg=start_deg,
                    z_lobe_inner=z_lobe_inner,
                    z_lobe_outer_pos=z_lobe_outer[blade_counter],
                    fuel_top=fuel_top,
                    fuel_bot=fuel_bot,
                    guide_top=guide_top,
                    guide_bot=guide_bot,
                    core_outer_cyl=core_outer_cyl,
                ))
                blade_counter += 1

        # =====================================================================
        # PART B: THE 6 INNER EQUILATERAL TRIANGLES (Inward-curving pinch wedges)
        # =====================================================================
        triangle_specs = [
            PinchTriangleSpec(-30.0,  30.0, pos_hub_index=0, use_high_hex_plane=True,  neg_hub_index=2, local_rotation_deg=90.0),
            PinchTriangleSpec( 30.0,  90.0, pos_hub_index=0, use_high_hex_plane=False, neg_hub_index=0, local_rotation_deg=-90.0),
            PinchTriangleSpec( 90.0, 150.0, pos_hub_index=1, use_high_hex_plane=True,  neg_hub_index=0, local_rotation_deg=-150.0),
            PinchTriangleSpec(150.0, 210.0, pos_hub_index=1, use_high_hex_plane=False, neg_hub_index=1, local_rotation_deg=30.0),
            PinchTriangleSpec(210.0, 270.0, pos_hub_index=2, use_high_hex_plane=True,  neg_hub_index=1, local_rotation_deg=-30.0),
            PinchTriangleSpec(270.0, 330.0, pos_hub_index=2, use_high_hex_plane=False, neg_hub_index=2, local_rotation_deg=150.0),
        ]

        for tri_idx, spec in enumerate(triangle_specs):
            pie_slice = get_origin_pie_slice(spec.sector_start_deg, spec.sector_end_deg)
            cells.extend(self._build_pinch_triangle(
                tri_idx=tri_idx,
                spec=spec,
                pie_slice=pie_slice,
                pos_hub=pos_hubs[spec.pos_hub_index],
                neg_hub=neg_hubs[spec.neg_hub_index],
                z_center_inner=z_center_inner,
                z_center_outer_pos=z_center_outer[tri_idx],
                fuel_top=fuel_top,
                fuel_bot=fuel_bot,
                guide_top=guide_top,
                guide_bot=guide_bot,
            ))

        return cells