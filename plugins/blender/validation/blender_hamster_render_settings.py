from typing import List, Tuple

import bpy
from tik_manager4.dcc.validate_core import ValidateCore


class CheckRenderSettings(ValidateCore):
    """Checks if the render settings are set correctly"""

    nice_name = "Checking render settings"

    def __init__(self):
        super().__init__()
        self.autofixable = True
        self.ignorable = False
        self.checked_by_default = True
        self.optional = True

        self.viewLayerRequiredPasses = {
            "use_pass_combined": "Combined",
            "use_pass_z": "Z",
            "use_pass_vector": "Vector",
            "use_pass_diffuse_direct": "Diffuse Direct",
            "use_pass_diffuse_color": "Diffuse Color",
            "use_pass_glossy_direct": "Specular Light",
            "use_pass_glossy_color": "Specular Color",
            "use_pass_environment": "Specular Environment",
            "use_pass_cryptomatte_object": "Cryptomatte Object",
            "use_pass_cryptomatte_material": "Cryptomatte Material",
            "use_pass_cryptomatte_asset": "Cryptomatte Asset",
        }

        self.viewLayerForbiddenPasses = {
            "use_pass_grease_pencil": "Grease Pencil",

        }

    def validate(self):
        """main validation function"""
        messages = []

        for check in (
                self.__validateFileFormat,
                self.__validateViewLayers,
                self.__validateImageNodes,
                self.__validateMiscellaneous,
        ):
            result, message = check()
            if not result:
                messages.append(message)

        if messages:
            self.failed(msg="\n\n".join(messages))
            return

        self.passed()

    def __validateMiscellaneous(self):
        scene = bpy.context.scene
        useShadows = scene.eevee.use_shadows
        if useShadows:
            return False, "Use Shadows needs to be False"

        if scene.render.filter_size != 0.0:
            return False, "Filter size needs to be 0.0"

        if not scene.render.film_transparent:
            return False, "Film transparent needs to be True"

        return True, ""

    def __validateImageNodes(self):
        materials = bpy.data.materials
        invalidNodes = []

        for material in materials:
            if not material.use_nodes:
                continue

            if not material.node_tree:
                continue

            for node in material.node_tree.nodes:
                if node.type != "TEX_IMAGE" or not node.image:
                    continue

                if not node.image.filepath.lower().endswith(".png"):
                    continue

                if node.interpolation != "Closest":
                    invalidNodes.append({
                        "material": material.name,
                        "node": node.name,
                        "image": node.image.name,
                        "interpolation": node.interpolation
                    })

        if invalidNodes:
            messageLines = ["PNG textures NOT set to Closest:"]
            for entry in invalidNodes:
                messageLines.append(
                    f"{entry['material']} → {entry['node']} "
                    f"({entry['image']}): {entry['interpolation']}"
                )

            return False, "\n".join(messageLines)

        return True, ""

    def __validateFileFormat(self) -> Tuple[bool, str]:
        scene = bpy.context.scene
        resolutionFailMessage = (
            "Resolution must be 1920x1080 and frame rate must be 24fps"
        )

        if (
                scene.render.resolution_x != 1920
                or scene.render.resolution_y != 1080
                or scene.render.fps != 24
                or scene.render.fps_base != 1
        ):
            return False, resolutionFailMessage

        fileFormat = scene.render.image_settings.file_format
        if fileFormat in {"OPEN_EXR", "OPEN_EXR_MULTILAYER"}:
            return True, ""

        return False, "Wrong file format. Please select OpenEXR Multilayer format."

    def __validateViewLayers(self) -> Tuple[bool, str]:
        allViewLayers = bpy.context.scene.view_layers
        messages = []
        result = True

        for viewLayer in allViewLayers:
            for attr, label in self.viewLayerRequiredPasses.items():
                if not hasattr(viewLayer, attr):
                    raise AttributeError(
                        f"ViewLayer '{viewLayer.name}' has no attribute '{attr}'. "
                        "Validation rule is invalid or Blender version mismatch."
                    )

                if not getattr(viewLayer, attr):
                    result = False
                    messages.append(
                        f"View layer '{viewLayer.name}' is missing required pass: {label}"
                    )
            for attr, label in self.viewLayerForbiddenPasses.items():
                if not hasattr(viewLayer, attr):
                    raise AttributeError(
                        f"ViewLayer '{viewLayer.name}' has no attribute '{attr}'. "
                        "Validation rule is invalid or Blender version mismatch."
                    )

                if getattr(viewLayer, attr):
                    result = False
                    messages.append(
                        f"View layer '{viewLayer.name}' has forbidden pass enabled: {label}"
                    )

        return result, "\n".join(messages)

    def fix(self):

        scene = bpy.context.scene
        scene.render.resolution_x = 1920
        scene.render.resolution_y = 1080
        scene.render.fps = 24
        scene.render.fps_base = 1
        scene.render.image_settings.media_type = "MULTI_LAYER_IMAGE"

        allViewLayers = bpy.context.scene.view_layers
        for viewLayer in allViewLayers:
            for attr, label in self.viewLayerRequiredPasses.items():
                setattr(viewLayer, attr, True)
            for attr, label in self.viewLayerForbiddenPasses.items():
                setattr(viewLayer, attr, False)

        scene.eevee.use_shadows = False
        scene.render.filter_size = 0.0
        scene.render.film_transparent = True

        materials = bpy.data.materials
        for material in materials:
            if not material.use_nodes:
                continue

            if not material.node_tree:
                continue

            for node in material.node_tree.nodes:
                if node.type != "TEX_IMAGE" or not node.image:
                    continue

                if not node.image.filepath.lower().endswith(".png"):
                    continue

                if node.interpolation != "Closest":
                    node.interpolation = "Closest"



