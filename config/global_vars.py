"""
config/global_vars.py
Central registry for global dimensions, material conditions, 
and shared surface primitives.
"""
from dataclasses import dataclass

@dataclass
class fluxtrap:
    r_in: float = 4.0 # Inner radius of the flux trap
    # NOTE, this may need to be adjusted based on the specific flux trap design

@dataclass
class fuel:
    temp_var: float = 1.0

@dataclass
class vessel:
    temp_var: float = 1.0