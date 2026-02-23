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

for _modname in glob(__here__ + "/*.py"):
    _filename = _modname.split("/")[-1]
    if not _filename.startswith("__"):
        _module_name = _filename.split(".")[0]
        _class_name = "".join(
            part.capitalize() for part in _module_name.split("_")
        )
        __all__.append(_class_name)
        _mod = __import__(
            "l7r.schools." + _module_name, fromlist=[_class_name]
        )
        globals()[_class_name] = getattr(_mod, _class_name)
