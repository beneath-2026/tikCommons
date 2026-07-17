import hou
from tik_manager4.dcc.extract_core import ExtractCore


class UsdRopExporter(ExtractCore):
    nice_name = "USD Rop Export"
    optional = True

    def __init__(self):
        self.__nullNodeName = "OUT_PUBLISH"
        global_exposed_settings = {

            "File Format": {
                "type": "combo",
                "items": [
                    ".usda",
                    ".usd",
                    ".usdz",
                    ".usdb"
                ],
                "value": ".usda"
            },
        }

        super().__init__(global_exposed_settings=global_exposed_settings)

    def _extract_default(self):
        extension = self.global_settings.get("File Format")
        self.extension = extension
        filePath = self.resolve_output()

        stageNode = hou.node("/stage")
        nullNode = stageNode.node(self.__nullNodeName)
        outputNodes = nullNode.outputs()
        usdRopNode = outputNodes[0]
        usdRopNode.parm("lopoutput").set(filePath)
        usdRopNode.parm("enableoutputprocessor_simplerelativepaths").set(False)
        usdRopNode.parm("execute").pressButton()
