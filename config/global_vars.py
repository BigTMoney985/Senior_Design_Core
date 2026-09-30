"""
config/global_vars.py
Central registry for global dimensions, material conditions, 
and shared surface primitives.
"""

def in_to_cm(inches: float) -> float:
    """Convert inches to centimeters."""
    return inches * 2.54

from dataclasses import dataclass

@dataclass
class fluxtrap:
    r_in: float = 4.0 # Inner radius of the flux trap
    # NOTE, this may need to be adjusted based on the specific flux trap design

@dataclass
class fuel:
    temp_var: float = 1.0
    meat_thickness: float = 0.13
    clad_thickness: float = in_to_cm(0.015)
    nominal_dist: float = 0.15



@dataclass
class vessel:
    temp_var: float = 1.0