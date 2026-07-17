from typing import List, Tuple

import hou
from pyexpat.errors import messages
from tik_manager4.dcc.validate_core import ValidateCore


class CheckUsdRop(ValidateCore):
    """Usd Rop node will be created under null node called OUT_PUBLISH"""

    nice_name = "Checking Usd Rop Settings"


    def __init__(self):
        super().__init__()
        self.autofixable = True
        self.ignorable = False
        self.checked_by_default = True
        self.optional = True
        self.__nullNodeName = "OUT_PUBLISH"


    def validate(self):
        """main validation function"""
        result, message = self.__validateNodes()
        if not result:
            self.failed(msg=message)
            return

        self.passed()

    def __validateNodes(self):
        stageNode = hou.node("/stage")
        nullNode = stageNode.node(self.__nullNodeName)
        if not nullNode:
            return False, "null node name does not exist. Create a null node called OUT_PUBLISH"
        outputNodes = nullNode.outputs()
        usdRopNode = None
        if outputNodes and len(outputNodes) == 1:
                usdRopNode = outputNodes[0]
        if not usdRopNode:
            if len(outputNodes) > 1:
                return False, "too many nodes are connected to OUT_PUBLISH"
            return False, "no usd rop node found under null node called OUT_PUBLISH"

        return True, "OK"


    def fix(self):
        stageNode = hou.node("/stage")
        nullNode = stageNode.node(self.__nullNodeName)
        if not nullNode:
            return

        outputNodes = nullNode.outputs()
        usdRopNode = None
        if outputNodes and outputNodes[0]:
            if outputNodes[0].name() == "OUT_PUBLISH":
                usdRopNode = outputNodes[0]
        if not usdRopNode:
            usdRopNode = stageNode.createNode("usd_rop", node_name = "usd_rop_out")

        usdRopNode.setInput(0, nullNode)