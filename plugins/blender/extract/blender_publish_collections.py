import bpy
import os
import shutil
from typing import List
from tik_manager4.dcc.extract_core import ExtractCore


class Source(ExtractCore):
    """Extract a new .blend by copying the entire file, then keeping only collections
    starting with 'PUBLISH' (and their children). All physics, gravity, and world data remain intact.
    """

    nice_name = "Publish via full copy and PUBLISH filtering"
    optional = True

    def __init__(self):
        super(Source, self).__init__()
        self.extension = ".blend"

    def _extract_default(self) -> None:
        """Copy the current .blend, open it, remove non-PUBLISH collections, save."""
        # Quelle und Ziel festlegen
        source_path = bpy.data.filepath
        if not source_path:
            raise RuntimeError("Please save the current file before publishing.")

        target_path = self.resolve_output()
        print(f"[Extractor] Copying from: {source_path}\n→ to: {target_path}")

        # Originaldatei komplett kopieren
        shutil.copy2(source_path, target_path)

        # Das kopierte File öffnen
        bpy.ops.wm.open_mainfile(filepath=target_path)
        scene = bpy.context.scene

        # Hilfsfunktion: prüfen, ob eine Collection unter einer 'PUBLISH'-Collection liegt
        def is_under_publish(col, visited=None):
            if visited is None:
                visited = set()
            if col in visited:
                return False
            visited.add(col)
            if col.name.startswith("PUBLISH"):
                return True
            # Prüfe, ob eines der Parent-Collections 'PUBLISH' ist
            for parent in bpy.data.collections:
                if col.name in [c.name for c in parent.children]:
                    if is_under_publish(parent, visited):
                        return True
            return False

        # Alle Collections durchgehen und Nicht-PUBLISH löschen
        rbw_col = scene.rigidbody_world.collection if scene.rigidbody_world else None
        rbw_con = scene.rigidbody_world.constraints if scene.rigidbody_world else None
        rigid_body_collections = {rbw_col, rbw_con} - {None}

        all_cols: List[bpy.types.Collection] = list(bpy.data.collections)
        removed_count = 0
        for col in all_cols:
            if col in rigid_body_collections:
                print(f"[Extractor] Keeping rigid body collection: {col.name}")
                continue
            if not is_under_publish(col):
                try:
                    bpy.data.collections.remove(col)
                    print(f"[Extractor] Removed collection: {col}")
                    removed_count += 1
                except Exception as e:
                    print(f"[Extractor] Could not remove {col}: {e}")

        print(f"[Extractor] Removed {removed_count} non-PUBLISH collections")

        bpy.ops.wm.save_mainfile(filepath=target_path)
        print(f"[Extractor] ✅ Publish complete: {target_path}")
