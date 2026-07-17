from typing import Iterable, Set, List, Optional

import bpy
from tik_manager4.dcc.ingest_core import IngestCore


class IngestAndLibOverrides(IngestCore):
    """
    Blender ingestor that supports both:
    - `_bring_in_default`: Appends (imports locally) objects from a .blend into the current scene.
    - `_reference_default`: Links top-level collections from a .blend and creates fully editable
      hierarchical library overrides (equivalent to "Selected & Content").
    """
    nice_name = "Ingest via Blender"
    valid_extensions = [".blend"]
    referencable = True

    def _isChildLinked(self, sceneChildren: Iterable[bpy.types.Collection], collectionName: str) -> bool:
        """
        Check whether a collection with the given name is already linked as a child
        of the scene's root collection.

        Args:
            sceneChildren: Iterable of child collections under the scene root.
            collectionName: Name of the collection to look for.

        Returns:
            True if a child collection with the given name exists, otherwise False.
        """
        return collectionName in {c.name for c in sceneChildren}

    def _unlinkChildByName(self, sceneChildren: Iterable[bpy.types.Collection], collectionName: str) -> None:
        """
        Unlink (remove) the first child collection with the specified name from the
        scene's root collection.

        Args:
            sceneChildren: Iterable of child collections under the scene root.
            collectionName: Name of the child collection to unlink.

        Note:
            This only unlinks the collection from the scene; it does not delete the data-block.
        """
        for child in sceneChildren:
            if child.name == collectionName:
                sceneChildren.unlink(child)
                break

    def _bring_in_default(self) -> None:
        """
        Append mode:
        Imports objects from the source .blend locally (no linking, no overrides) and links them
        into the current scene if not already present.

        Behavior:
            - No library overrides are created (not applicable for local appends).
            - Deduplicates by object name against existing objects in the scene root collection.
        """
        with bpy.data.libraries.load(self.ingest_path) as (dataFrom, dataTo):
            dataTo.objects = dataFrom.objects

        targetObjects = bpy.context.scene.collection.objects
        existingObjectNames: Set[str] = {obj.name for obj in targetObjects}

        for obj in filter(None, dataTo.objects):
            if obj.name not in existingObjectNames:
                bpy.context.scene.collection.objects.link(obj)

    def _reference_default(self) -> None:
        """
        Reference mode:
        Links collections from the source .blend, determines top-level collections (those not
        present as a child of any other linked collection), and creates fully editable
        hierarchical library overrides for those top-level collections.

        Steps:
            1) Link collections from the .blend (link=True).
            2) Identify top-level collections (not present in the child sets of other linked collections).
            3) Link top-level collections into the scene (if not already linked).
            4) For each top-level collection, call `override_hierarchy_create(...)` to build a
               fully editable override (≈ "Selected & Content").
            5) Ensure the override collections are linked to the scene and unlink the original
               linked top-level collections to avoid duplicates in the Outliner.
        """
        # 1) Link collections from the source .blend
        with bpy.data.libraries.load(self.ingest_path, link=True) as (dataFromNames, dataToBlocks):
            dataToBlocks.collections = dataFromNames.collections

        linkedCollections: List[bpy.types.Collection] = [c for c in dataToBlocks.collections if c is not None]
        if not linkedCollections:
            print("[Ingestor - Error] No collections linked from source file.")
            return

        # 2) Determine top-level collections (not contained as a child of any other linked collection)
        childSet: Set[bpy.types.Collection] = set()
        for parent in linkedCollections:
            for child in parent.children:
                childSet.add(child)
        topLevelCollections: List[bpy.types.Collection] = [c for c in linkedCollections if c not in childSet]

        if not topLevelCollections:
            raise Exception("[Ingestor - Error] No top-level collections identified from source file.")

        # 3) Link top-level collections into the scene if missing
        sceneChildren = bpy.context.scene.collection.children
        for collection in topLevelCollections:
            if not self._isChildLinked(sceneChildren, collection.name):
                sceneChildren.link(collection)

        # Make sure the depsgraph/view layer is up to date before creating overrides
        if bpy.context.view_layer:
            bpy.context.view_layer.update()

        # 4) Create overrides (≈ "Selected & Content") for top-level collections
        createdOverrides: List[Optional[bpy.types.Collection]] = []
        for collection in topLevelCollections:
            overrideCollection = collection.override_hierarchy_create(
                bpy.context.scene,
                bpy.context.view_layer,
                do_fully_editable=True
            )
            if overrideCollection is not None:
                createdOverrides.append(overrideCollection)

        # 5) Link overrides to the scene, then unlink original linked top-level collections
        for overrideCollection in createdOverrides:
            if overrideCollection and not self._isChildLinked(sceneChildren, overrideCollection.name):
                sceneChildren.link(overrideCollection)

        for collection in topLevelCollections:
            if self._isChildLinked(sceneChildren, collection.name):
                self._unlinkChildByName(sceneChildren, collection.name)

        print(
            f"[Ingestor - Info] Library Overrides created for {len([ov for ov in createdOverrides if ov is not None])} "
            f"top-level collection(s).")