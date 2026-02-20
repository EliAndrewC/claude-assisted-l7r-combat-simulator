"""
Auto-imports all school modules so they can be used as e.g.
``from l7r.schools import AkodoBushi``.

Each .py file in this directory (other than __init__.py) defines a single
school class whose name matches the filename.
"""

import os.path
from glob import glob

__here__ = os.path.abspath(os.path.dirname(__file__))

__all__ = []

for modname in glob(__here__ + "/*.py"):
    filename = modname.split("/")[-1]
    if not filename.startswith("__"):
        school = filename.split(".")[0]
        __all__.append(school)
        mod = __import__("l7r.schools." + school, fromlist=[school])
        globals()[school] = getattr(mod, school)
