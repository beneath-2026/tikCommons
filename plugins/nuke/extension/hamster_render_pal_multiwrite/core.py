import os
import re
import subprocess
import time
from pathlib import Path

import nuke

"""
Core logic for the RenderPal MultiWrite submission workflow in Nuke.

Responsibilities:
- Analyze Write nodes to derive shot identifiers and frame ranges.
- Create per-shot temporary .nk scripts where only a single Write is enabled and
  its output path is set to the per-shot output directory.
- Build and submit RenderPal command lines for those temporary scripts.

This module should not show UI dialogs (no nuke.message / Qt widgets). It returns
errors to the caller so the extension/UI layer can decide how to present them.
"""


def __findUpstreamCombineGroup(startNode):
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


def __getGroupInputIndexByInternalInputName(groupNode, internalInputName):
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


def __findFirstUpstreamRead(startNode):
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


def __extractShotFromRead(readNode):
    filePath = readNode["file"].value() if "file" in readNode.knobs() else ""
    match = re.search(r"sh(\d{3})", filePath, flags=re.IGNORECASE)
    return match.group(1) if match else None


def __sanitizeFileNamePart(text):
    return re.sub(r"[^A-Za-z0-9_\-\.]+", "_", text)


def __getUniquePath(targetPath):
    if not os.path.exists(targetPath):
        return targetPath

    base, ext = os.path.splitext(targetPath)
    index = 2
    while True:
        candidate = f"{base}_{index}{ext}"
        if not os.path.exists(candidate):
            return candidate
        index += 1


def __setOnlyThisWriteEnabled(writeNodes, targetWriteNode):
    for node in writeNodes:
        if "disable" not in node.knobs():
            continue
        node["disable"].setValue(0 if node is targetWriteNode else 1)


def __renameTargetWriteToWrite1(writeNodes, targetWriteNode):
    originalNameByNodeId = {id(n): n.name() for n in writeNodes}

    currentWrite1 = None
    for node in writeNodes:
        if node.name() == "Write1":
            currentWrite1 = node
            break

    if currentWrite1 is not None and currentWrite1 is not targetWriteNode:
        tempName = "Write1__disabled"
        tempName = __sanitizeFileNamePart(tempName)

        counter = 2
        candidate = tempName
        while nuke.exists(candidate):
            candidate = f"{tempName}_{counter}"
            counter += 1

        currentWrite1.setName(candidate)
        if "disable" in currentWrite1.knobs():
            currentWrite1["disable"].setValue(1)

    if targetWriteNode.name() != "Write1":
        targetWriteNode.setName("Write1")

    return originalNameByNodeId


def getFrameRangeFromWriteNode(writeNode):
    """
        Resolve the frame range for a Write node.

        If the Write node uses limits (use_limit=1), the range is taken from
        its 'first'/'last' knobs. Otherwise it falls back to the Root frame range.

        Args:
            writeNode (nuke.Node): A Write node.

        Returns:
            tuple[int, int]: (startFrame, endFrame)
        """
    try:
        useLimit = int(writeNode["use_limit"].value()) if "use_limit" in writeNode.knobs() else 0

        if useLimit:
            startFrame = int(writeNode["first"].value()) if "first" in writeNode.knobs() else int(
                nuke.root()["first_frame"].value())
            endFrame = int(writeNode["last"].value()) if "last" in writeNode.knobs() else int(
                nuke.root()["last_frame"].value())
            return startFrame, endFrame

        startFrame = int(nuke.root()["first_frame"].value())
        endFrame = int(nuke.root()["last_frame"].value())
        return startFrame, endFrame

    except Exception:
        return 1, 100


def createTempScriptsPerWrite(tempFolderPath, runStamp, perShotOutDirs, frameFileName="frame_%04d.png"):
    """
        Create one temporary Nuke script per Write node / shot.

        For each Write node found in the currently opened script:
        - Re-open the original script to avoid state leaks between iterations.
        - Find the target Write node by its original name.
        - Resolve the shot name for that Write node.
        - Disable all other Write nodes and rename the active one to 'Write1'.
        - Set Write1 output to '<perShotOutDirs[shot]>/<frameFileName>'.
        - Save the modified script into tempFolderPath with a unique name.

        This function does not show UI messages. It returns a list of created scripts
        and a list of error strings for reporting.

        Args:
            tempFolderPath (str): Directory where temp .nk files will be created.
            runStamp (str): Timestamp string used in generated temp script names.
            perShotOutDirs (dict[str, str]): Mapping shotName -> output directory.
            frameFileName (str): Filename pattern for frame outputs (e.g. frame_%04d.png).

        Returns:
            tuple[list[dict], list[str]]:
                (createdScripts, errors)
                createdScripts entries:
                    {
                        "scriptPath": str,
                        "shotName": str,
                        "outDir": str
                    }
                errors are human-readable strings.
        """
    created = []
    errors = []

    originalScriptPath = nuke.root().name()
    if not originalScriptPath or originalScriptPath.lower() == "root":
        errors.append("Bitte speichere das Nuke-Script zuerst.")
        return created, errors

    try:
        os.makedirs(tempFolderPath, exist_ok=True)
    except Exception as exc:
        errors.append(f"Temp folder could not be created: {tempFolderPath} ({exc})")
        return created, errors

    originalWriteNodes = nuke.allNodes("Write")
    originalWriteNames = [w.name() for w in originalWriteNodes]
    if not originalWriteNames:
        errors.append("Keine Write-Nodes gefunden.")
        return created, errors

    baseNameHint = os.path.splitext(os.path.basename(originalScriptPath))[0]
    baseNameHint = __sanitizeFileNamePart(baseNameHint)

    for writeName in originalWriteNames:
        try:
            nuke.scriptOpen(originalScriptPath)
            time.sleep(2)

            writeNodes = nuke.allNodes("Write")
            targetWriteNode = None
            for w in writeNodes:
                if w.name() == writeName:
                    targetWriteNode = w
                    break

            if targetWriteNode is None:
                errors.append(f"{writeName}: nicht gefunden nach scriptOpen.")
                continue

            shotName, shotError = getShotFromWriteNode(targetWriteNode)
            if shotError or not shotName:
                errors.append(f"{writeName}: Shot nicht bestimmbar ({shotError}).")
                continue

            shotName = __sanitizeFileNamePart(shotName)

            outDir = perShotOutDirs.get(shotName)
            if not outDir:
                errors.append(f"{writeName}: Kein Output-Dir im UI für {shotName}.")
                continue

            try:
                os.makedirs(outDir, exist_ok=True)
            except Exception as exc:
                errors.append(f"{writeName}: Output folder could not be created: {outDir} ({exc})")
                continue

            __setOnlyThisWriteEnabled(writeNodes, targetWriteNode)
            __renameTargetWriteToWrite1(writeNodes, targetWriteNode)

            write1Node = None
            for w in nuke.allNodes("Write"):
                if w.name() == "Write1":
                    write1Node = w
                    break

            if write1Node is None:
                errors.append(f"{writeName}: Write1 nicht gefunden in Temp-State.")
                continue

            write1Node["file_type"].setValue("png")
            writePath = (Path(outDir) / frameFileName).as_posix()
            write1Node["file"].setValue(writePath)

            tempName = f"{baseNameHint}__{runStamp}__{shotName}.nk"
            tempPath = __getUniquePath(os.path.join(tempFolderPath, tempName)).replace("\\", "/")
            nuke.scriptSaveAs(tempPath, overwrite=1)

            created.append({
                "scriptPath": tempPath,
                "shotName": shotName,
                "outDir": outDir
            })

        except Exception as exc:
            errors.append(f"{writeName}: {exc}")

    try:
        nuke.scriptOpen(originalScriptPath)
    except Exception:
        pass

    return created, errors


def getShotFromWriteNode(writeNode):
    """
    Resolve a shot name for a given Nuke Write node.

    The method walks upstream from the Write node to find a COMBINE_ group,
    then follows the group's internal input named "CLIP" to a Read/DeepRead node.
    The shot is extracted from the Read's file path via the pattern 'sh###'.

    Args:
        writeNode (nuke.Node): The Write node to analyze.

    Returns:
        tuple[str | None, str | None]:
            (shotName, errorMessage)
            - shotName is e.g. "sh010" if resolved
            - errorMessage is a human-readable error if resolving failed
    """
    combineGroup = __findUpstreamCombineGroup(writeNode)
    if combineGroup is None:
        return None, "Keine COMBINE_-Group upstream gefunden."

    clipInputIndex = __getGroupInputIndexByInternalInputName(combineGroup, "CLIP")
    if clipInputIndex is None:
        return writeNode.name(), None

    clipUpstreamNode = combineGroup.input(clipInputIndex)
    if clipUpstreamNode is None:
        return None, f'Group-Input {clipInputIndex} ("CLIP") ist nicht verbunden.'

    readNode = __findFirstUpstreamRead(clipUpstreamNode)
    if readNode is None:
        return None, 'Upstream von "CLIP" keinen Read gefunden.'

    shotNumber = __extractShotFromRead(readNode)
    if shotNumber is None:
        return None, f'Konnte keine Shot-ID aus Read-File extrahieren: {readNode["file"].value()}'

    return "sh" + shotNumber, None


def submitAllTempScripts(
        tempScripts,
        perShotRanges,
        settings,
        projectName,
        progress,
        log,
        executablePath,
        renderPalLogin,
        renderPalServer):
    """
        Submit all prepared temporary Nuke scripts to RenderPal.

        Each temp script is submitted as its own RenderPal job using the shot-specific
        frame range from perShotRanges. The function advances progress via the provided
        ProgressReporter-compatible object.

        Args:
            tempScripts (list[dict]): Entries like {"scriptPath": str, "shotName": str, ...}.
            perShotRanges (dict[str, tuple[int,int]]): Mapping shotName -> (start,end).
            settings (dict): UI settings dict (expects "jobName" and "batchSize").
            projectName (str): Used to build the renderer string "Nuke/<projectName>".
            progress: Object providing step(statusText, logText) and cancelRequested behavior.
            log (callable): Function that receives log strings.
            executablePath (str): Path to RenderPal command line tool.
            renderPalLogin (str): RenderPal login string.
            renderPalServer (str): RenderPal server string.

        Returns:
            tuple[int, list[str]]:
                (submittedCount, submitErrors)
        """
    submittedCount = 0
    submitErrors = []

    renderer = f"Nuke/{projectName}"
    splitmode = f"1,{settings['batchSize']}"

    for entry in tempScripts:
        tempScriptPath = entry["scriptPath"]
        shotName = entry["shotName"]

        if shotName not in perShotRanges:
            submitErrors.append(f"{shotName}: No frame range found in UI settings.")
            continue

        startFrame, endFrame = perShotRanges[shotName]
        frames = f"{startFrame}-{endFrame}"

        if not progress.step(
                f"Submitting {shotName}...",
                f"Submitting: {shotName} | Frames: {frames} | Script: {tempScriptPath}"
        ):
            submitErrors.append("Cancelled by user.")
            break

        nukePathForSubmit = tempScriptPath.replace("\\", "/")
        jobNameFull = f"{settings['jobName']} [{shotName}]: {os.path.basename(nukePathForSubmit)}"

        commandList = [
            executablePath,
            "-nj_renderer", renderer,
            "-nj_name", jobNameFull,
            "-frames", frames,
            "-nj_splitmode", splitmode,
            "-login", renderPalLogin,
            "-server", renderPalServer,
            nukePathForSubmit
        ]

        log(f"Executing command: {' '.join(commandList)}")

        try:
            subprocess.Popen(commandList, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            submittedCount += 1
            log(f"[INFO] Submitted: {shotName}")
        except Exception as exc:
            submitErrors.append(f"{shotName}: submit failed ({exc})")

    return submittedCount, submitErrors
