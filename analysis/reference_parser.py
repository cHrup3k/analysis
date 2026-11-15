import re
import numpy as np

def parse_reference(name):
    match=re.search(r'(?:^|_)([+-]?\d+(?:\.\d+)?)st_([+]?(?:\d+(?:\.\d+)?))m(?:_|$)',name)
    return tuple(map(float,match.groups())) if match else (np.nan,np.nan)
