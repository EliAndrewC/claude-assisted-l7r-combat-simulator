"""
Auto-imports all school modules so they can be used as e.g.
``from l7r.schools import AkodoBushi``.

Each snake_case .py file in this directory defines a single school
class whose CamelCase name is derived from the filename.
"""

import os.path
from glob import glob

__here__ = os.path.abspath(os.path.dirname(__file__))

__all__ = []

for modname in glob(__here__ + "/*.py"):
    filename = modname.split("/")[-1]
    if not filename.startswith("__"):
        module_name = filename.split(".")[0]
        class_name = "".join(
            part.capitalize() for part in module_name.split("_")
        )
        __all__.append(class_name)
        mod = __import__(
            "l7r.schools." + module_name, fromlist=[class_name]
        )
        globals()[class_name] = getattr(mod, class_name)
