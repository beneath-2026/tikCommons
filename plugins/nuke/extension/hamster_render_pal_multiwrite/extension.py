import logging
import os
import time
from datetime import datetime
from pathlib import Path

import nuke
from tik_manager4.dcc.extension_core import ExtensionCore

from . import core as renderCore
from .ui import showRenderSettingsDialog, createProgressWindow, ProgressReporter

LOG = logging.getLogger(__name__)


class RenderPalSubmissionMultiWrite(ExtensionCore):
    injectedConfig = {}

    tempFolderPath = r"X:\path\to\your\render\temp"
    renderPalExecutablePath = r"C:/Program Files (x86)/RenderPal V2/CmdRC/rprccmd"
    defaultBatchSize = 10
    frameFileName = "frame_%04d.png"
    progressWindowTitle = "RenderPal MultiWrite Progress"
    finishHoldSeconds = 2

    renderPalLogin = f"{os.environ.get('RP_USER', '')}:{os.environ.get('RP_PASSWORD', '')}"
    renderPalServer = os.environ.get('RP_SERVER', 'your-renderpal-server:7506')

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = dict(self.injectedConfig or {})
        self.projectName = self.config.get("project", "UnknownProject")

    def execute(self):
        # kein load_config mehr nötig
        self.add_function_to_main_menu(self.start, "RenderPal Submission MultiWrite")

    def generateOutDirForShot(self, shotName):
        """
        Keep your existing implementation here.
        Must return a string path or None.
        """
        basePath = Path(self.config.get("renderFolder").get(self.projectName))

        sequenceName = self.parent.subprojects_mcv.get_active_subproject().name
        taskName = self.parent.categories_mcv.get_active_category().name

        if not sequenceName or not taskName or not shotName:
            nuke.tprint("[RENDER ERROR] sequenceName / taskName / shotName missing")
            return None

        parentPath = basePath / sequenceName / shotName / taskName
        parentPath.mkdir(parents=True, exist_ok=True)

        maxVersion = 0
        for folder in parentPath.iterdir():
            if not folder.is_dir():
                continue
            name = folder.name
            versionString = name.split("_")[-1]
            if not versionString.startswith("v"):
                continue
            numberPart = versionString[1:]
            if not numberPart.isdigit():
                continue
            versionNumber = int(numberPart)
            maxVersion = max(maxVersion, versionNumber)

        newestVersion = f"v{maxVersion + 1:03d}"
        folderName = f"{sequenceName}_{shotName}_{taskName}_{newestVersion}"
        return str(parentPath / folderName)

    def collectShotRows(self):
        writeNodes = nuke.allNodes("Write")

        shotRowsByName = {}
        errors = []

        for writeNode in writeNodes:
            shotName, err = renderCore.getShotFromWriteNode(writeNode)
            if err or not shotName:
                errors.append(f"{writeNode.name()}: {err}")
                continue

            if shotName in shotRowsByName:
                errors.append(f"Mehrere Writes für denselben Shot gefunden: {shotName}")
                continue

            startFrame, endFrame = renderCore.getFrameRangeFromWriteNode(writeNode)

            defaultOutDir = self.generateOutDirForShot(shotName)
            if not defaultOutDir:
                errors.append(f"Konnte Default-OutDir nicht generieren für {shotName}")
                continue

            shotRowsByName[shotName] = {
                "shot": shotName,
                "outDir": defaultOutDir,
                "start": startFrame,
                "end": endFrame
            }

        return list(shotRowsByName.values()), errors

    def createTempScriptsStage(self, perShotOutDirs, progress):
        if not progress.step("Creating temp scripts...", "Creating temp NK files per shot..."):
            return None

        runStamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        tempScripts, tempErrors = renderCore.createTempScriptsPerWrite(
            tempFolderPath=self.tempFolderPath,
            runStamp=runStamp,
            perShotOutDirs=perShotOutDirs,
            frameFileName=self.frameFileName
        )

        if tempErrors:
            for line in tempErrors[:80]:
                progress.log(f"[TEMP ERROR] {line}")

        if not tempScripts:
            progress.log("No temp scripts created. Aborting submission.")
            return None

        progress.log(f"Temp scripts created: {len(tempScripts)}")
        return tempScripts

    def submitStage(self, tempScripts, perShotRanges, settings, progress):
        def logFn(text):
            nuke.tprint(text)
            LOG.info(text)

        submittedCount, submitErrors = renderCore.submitAllTempScripts(
            tempScripts=tempScripts,
            perShotRanges=perShotRanges,
            settings=settings,
            projectName=self.projectName,
            progress=progress,
            log=logFn,
            executablePath=self.renderPalExecutablePath,
            renderPalLogin=self.renderPalLogin,
            renderPalServer=self.renderPalServer,
        )

        if submitErrors:
            for line in submitErrors[:80]:
                progress.log(f"[SUBMIT ERROR] {line}")

        return submittedCount

    def start(self):
        """
            Main entry point called by the Tik Manager menu action.

            Workflow:
            1) Collect shot rows from Write nodes (shot id, default output dir, frame range).
            2) Ask the user to confirm/edit per-shot output directories and frame ranges.
            3) Create per-shot temporary Nuke scripts (one active Write each).
            4) Submit each temp script to RenderPal with the per-shot frame range.

            Any UI interaction happens in the UI module; core functions return errors
            that are displayed/logged here.
            """

        shotRows, errors = self.collectShotRows()
        if errors:
            nuke.message("Setup Fehler:\n\n" + "\n".join(errors[:30]))
            return

        initialData = {
            "jobName": f"Nuke {self.projectName} Render",
            "batchSize": self.defaultBatchSize,
            "shotRows": shotRows
        }

        settings = showRenderSettingsDialog(initialData)
        if not settings:
            return

        perShotOutDirs = settings["perShotOutDirs"]
        perShotRanges = settings["perShotRanges"]

        totalShots = len(shotRows)
        totalSteps = 1 + totalShots + 1

        progressUi = createProgressWindow(self.progressWindowTitle)
        progress = ProgressReporter(progressUi, totalSteps)
        progress.log(f"Shots detected: {totalShots}")

        tempScripts = self.createTempScriptsStage(perShotOutDirs, progress)

        if not tempScripts:
            progress.close()
            return

        submittedCount = self.submitStage(tempScripts, perShotRanges, settings, progress)

        progress.finish(submittedCount)
        time.sleep(self.finishHoldSeconds)
        progress.close()

        if hasattr(self, "set_message"):
            self.set_message(f"{submittedCount} Jobs erfolgreich an RenderPal gesendet!")
