"""Ensure meshes do not contain ngons"""
from typing import List

import bpy
from tik_manager4.dcc.validate_core import ValidateCore


class checkPublishCollection(ValidateCore):
    """Checks if there is a 'PUBLISH' collection at top level"""

    nice_name = "Publish Collection"

    def __init__(self):
        super().__init__()
        self.autofixable = False
        self.ignorable = False
        self.checked_by_default = True
        self.optional = True

    def _getTopLevelCollections(self) -> List[bpy.types.Collection]:
        childSet = set()
        allCollections = list(bpy.context.scene.collection.children)

        for collection in allCollections:
            for child in collection.children:
                childSet.add(child)
        topLevelCollections = (collection for collection in allCollections if collection not in childSet)
        return topLevelCollections

    def validate(self):
        """Identify ngons in the scene."""
        topLevelCollections = self._getTopLevelCollections()
        for collection in topLevelCollections:
            print(f"[Validator] Validating collection: {collection.name}")
            if collection.name.startswith("PUBLISH"):
                self.passed()
                return
        self.failed(
            msg=f"There is no collection named 'PUBLISH' in this scene. Make sure it is a top level collection."
        )
