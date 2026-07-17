from typing import List

import bpy
from tik_manager4.dcc.extract_core import ExtractCore


class Source(ExtractCore):
    """Extract Source Blender scene"""

    nice_name = "Source Scene"
    optional = True

    def __init__(self):
        super(Source, self).__init__()

        self.extension = ".blend"

    def _extract_default(self):
        """Extract for any non-specified category."""
        file_path = self.resolve_output()
        bpy.ops.wm.save_as_mainfile(filepath=file_path, copy=True)
