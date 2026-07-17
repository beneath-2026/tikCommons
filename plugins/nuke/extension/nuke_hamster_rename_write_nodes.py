import re

import nuke
from tik_manager4.dcc.extension_core import ExtensionCore
from tik_manager4.dcc.nuke import utils


class RenderPalSubmission(ExtensionCore):

    def execute(self):
        """Initial execution."""
        # Projektname laden (wie im Extractor)
        self.add_function_to_main_menu(self.start, "Rename Write Nodes")

    def start(self):
        self.renameWriteNodes()

    def findUpstreamCombineGroup(self, startNode):
        visited = set()
        stack = [startNode]

        while stack:
            node = stack.pop()
            if node is None:
                continue

            nodeName = node.name()
            if nodeName in visited:
                continue
            visited.add(nodeName)

            if node.Class() == "Group" and nodeName.startswith("COMBINE_"):
                return node

            for i in range(node.inputs()):
                stack.append(node.input(i))

        return None

    def getGroupInputIndexByInternalInputName(self, groupNode, internalInputName):
        groupNode.begin()
        try:
            internalInputNode = None

            for node in nuke.allNodes(recurseGroups=False):
                if node.Class() == "Input" and node.name() == internalInputName:
                    internalInputNode = node
                    break

            if internalInputNode is None:
                return None

            if "number" in internalInputNode.knobs():
                return int(internalInputNode["number"].value())

            return None
        finally:
            groupNode.end()

    def findFirstUpstreamRead(self, startNode):
        visited = set()
        stack = [startNode]

        while stack:
            node = stack.pop()
            if node is None:
                continue

            nodeName = node.name()
            if nodeName in visited:
                continue
            visited.add(nodeName)

            if node.Class() in ("Read", "DeepRead"):
                return node

            for i in range(node.inputs()):
                stack.append(node.input(i))

        return None

    def extractShotFromRead(self, readNode):
        filePath = readNode["file"].value() if "file" in readNode.knobs() else ""
        match = re.search(r"sh(\d{3})", filePath, flags=re.IGNORECASE)
        return match.group(1) if match else None

    def getShotFromWriteNode(self, writeNode):
        combineGroup = self.findUpstreamCombineGroup(writeNode)
        if combineGroup is None:
            return None, "Keine COMBINE_-Group upstream gefunden."

        clipInputIndex = self.getGroupInputIndexByInternalInputName(combineGroup, "CLIP")
        if clipInputIndex is None:
            return None, f'In {combineGroup.name()} keinen internen Input "CLIP" (oder keinen "number"-Knob) gefunden.'

        clipUpstreamNode = combineGroup.input(clipInputIndex)
        if clipUpstreamNode is None:
            return None, f'Group-Input {clipInputIndex} ("CLIP") ist nicht verbunden.'

        readNode = self.findFirstUpstreamRead(clipUpstreamNode)
        if readNode is None:
            return None, 'Upstream von "CLIP" keinen Read gefunden.'

        shotNumber = self.extractShotFromRead(readNode)
        if shotNumber is None:
            return None, f'Konnte keine Shot-ID aus Read-File extrahieren: {readNode["file"].value()}'

        return shotNumber, None

    def makeUniqueName(self, baseName):
        """
        Gibt baseName zurück, wenn frei. Sonst baseName_2, baseName_3, ...
        """
        if nuke.exists(baseName) is False:
            return baseName

        index = 2
        while True:
            candidate = f"{baseName}_{index}"
            if nuke.exists(candidate) is False:
                return candidate
            index += 1

    def renameWriteNodes(self):
        usedShots = set()
        errors = []
        renamed = []

        for writeNode in nuke.allNodes("Write"):
            shot, error = self.getShotFromWriteNode(writeNode)

            if error:
                errors.append(f"{writeNode.name()}: {error}")
                continue

            if shot is None:
                errors.append(f"{writeNode.name()}: Shot ist None (unerwartet).")
                continue

            if shot in usedShots:
                errors.append(f"{writeNode.name()}: Zwei Write-Nodes für denselben Shot sh{shot}.")
                continue

            usedShots.add(shot)

            targetBaseName = f"sh{shot}"
            targetName = self.makeUniqueName(targetBaseName)

            try:
                oldName = writeNode.name()
                writeNode.setName(targetName)
                renamed.append(f"{oldName} -> {targetName}")
            except Exception as exc:
                errors.append(f"{writeNode.name()}: Konnte nicht umbenennen ({exc}).")

        messageLines = []
        messageLines.append(f"Renamed: {len(renamed)}")
        if renamed:
            messageLines.append("")
            messageLines.extend(renamed[:30])
            if len(renamed) > 30:
                messageLines.append("...")

        if errors:
            messageLines.append("")
            messageLines.append(f"Errors: {len(errors)}")
            messageLines.extend(errors[:30])
            if len(errors) > 30:
                messageLines.append("...")

        nuke.message("\n".join(messageLines))


