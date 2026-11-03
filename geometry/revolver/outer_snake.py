import openmc
import config.global_vars as gv
import numpy as np

from geometry.fuel_element import FuelElementGeometry

class lobe_3:
    def __init__(self) -> None:
        self.element_factory = FuelElementGeometry()
        self.base_universe = self.element_factory.create_fuel_universe()
        pass

    def build_clover_with_transforms(self, wedge_sequence, thickness=4.34, r_in=4.0):
        R0 = r_in + thickness / 2.0
        lobe_univ = openmc.Universe()

        # Starting turtle conditions
        x, y, heading = 0.0, 0.0, 0.0

        for angle_deg, sgn in wedge_sequence:
            arc_rad = np.radians(angle_deg)
            d_theta = sgn * arc_rad
            
            # 1. Calculate the center of curvature for this specific wedge
            cx = x - sgn * R0 * np.sin(heading)
            cy = y + sgn * R0 * np.cos(heading)

            # 2. Calculate the global angles for the path
            phi_start = np.arctan2(y - cy, x - cx)
            phi_end = phi_start + d_theta

            # 3. GET YOUR UNMODIFIED WEDGE UNIVERSE
            # It natively exists from 30 to 90 degrees at (0,0)
            wedge_univ = self.base_universe
            
            # 4. WRAP IN A CELL AND TRANSFORM
            segment_cell = openmc.Cell(fill=wedge_univ)
            
            # TRANSLATION: Move the (0,0) origin of your wedge to the calculated (cx, cy)
            segment_cell.translation = (cx, cy, 0.0)
            
            # ROTATION: Align the wedge's 30-degree edge with the path's starting angle
            target_start = phi_start if sgn > 0 else phi_end
            target_start_deg = np.degrees(target_start)
            
            # Subtract the 30-degree built-in offset so the true edge lands on target_start
            segment_cell.rotation = (0.0, 0.0, target_start_deg - 30.0)

            lobe_univ.add_cell(segment_cell)

            # 5. Step forward to the end of this wedge for the next iteration
            x = cx + R0 * np.cos(phi_end)
            y = cy + R0 * np.sin(phi_end)
            heading += d_theta

        return openmc.Geometry(lobe_univ)

    if __name__ == '__main__':
        # 18 wedges total of 60°: 240° wrap around 3 lobes (p=4, q=2)
        # +1 means outward curve, -1 means inward curve
        sequence = [(60, 1)] * 4 + [(60, -1)] * 2
        full_pattern = sequence * 3  # Repeat 3 times for the 3 lobes
        
        geom = self.build_clover_with_transforms(full_pattern)