import bpy
from tik_manager4.dcc.extract_core import ExtractCore


class AlembicExport(ExtractCore):
    """Export all objects inside PUBLISH_* collection(s) to an Alembic file,
    including full animation data for the current scene frame range.
    """

    nice_name = "Alembic Export"
    optional = True

    def __init__(self):
        super(AlembicExport, self).__init__()
        self.extension = ".abc"

    @staticmethod
    def _collect_objects(collection):
        """Recursively collect all objects from a collection and its children."""
        objects = set(collection.objects)
        for child_col in collection.children:
            objects |= AlembicExport._collect_objects(child_col)
        return objects

    def _extract_default(self):
        """Export PUBLISH_* collection contents to Alembic with animation."""
        scene = bpy.context.scene

        # Find all top-level PUBLISH collections
        publish_collections = [
            col for col in bpy.data.collections
            if col.name.upper().startswith("PUBLISH")
        ]
        if not publish_collections:
            raise RuntimeError(
                "No collection starting with 'PUBLISH' found. "
                "Please create a PUBLISH collection before exporting."
            )

        # Recursively gather all objects from every PUBLISH collection
        export_objects = set()
        for col in publish_collections:
            export_objects |= self._collect_objects(col)

        if not export_objects:
            raise RuntimeError("PUBLISH collection(s) contain no objects to export.")

        # Only keep objects that are present in the current view layer
        view_layer_objects = bpy.context.view_layer.objects
        exportable = [obj for obj in export_objects if obj.name in view_layer_objects]

        if not exportable:
            raise RuntimeError(
                "None of the objects in PUBLISH collection(s) are visible "
                "in the current view layer."
            )

        # Save current selection state to restore afterwards
        previously_selected = [obj for obj in bpy.data.objects if obj.select_get()]
        previously_active = bpy.context.view_layer.objects.active

        try:
            for obj in bpy.data.objects:
                obj.select_set(False)
            for obj in exportable:
                obj.select_set(True)
            bpy.context.view_layer.objects.active = exportable[0]

            output_path = self.resolve_output()
            start = scene.frame_start
            end = scene.frame_end

            self.set_message(
                f"Exporting {len(exportable)} objects to Alembic "
                f"(frames {start}–{end})…"
            )

            # --- FIX: Provide a valid window context for the operator ---
            window = bpy.context.window_manager.windows[0]
            with bpy.context.temp_override(window=window):
                bpy.ops.wm.alembic_export(
                    filepath=output_path,
                    start=start,
                    end=end,
                    xsamples=1,
                    gsamples=1,
                    sh_open=0.0,
                    sh_close=1.0,
                    selected=True,
                    visible_objects_only=False,
                    flatten=False,
                    uvs=True,
                    packuv=True,
                    normals=True,
                    vcolors=False,
                    apply_subdiv=False,
                    curves_as_mesh=False,
                    use_instancing=True,
                    global_scale=1.0,
                    triangulate=False,
                    quad_method="SHORTEST_DIAGONAL",
                    ngon_method="BEAUTY",
                    export_hair=True,
                    export_particles=True,
                    export_custom_properties=True,
                    as_background_job=False,
                )

            self.set_message(f"Alembic export complete → {output_path}")

        finally:
            for obj in bpy.data.objects:
                obj.select_set(False)
            for obj in previously_selected:
                try:
                    obj.select_set(True)
                except ReferenceError:
                    pass
            bpy.context.view_layer.objects.active = previously_active