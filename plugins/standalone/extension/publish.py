import json
import re
import sys
import traceback
import urllib

# EDIT: folder holding the python dependencies (PySide6, gazu, ...)
sys.path.insert(0, r"X:\path\to\your\python\site-packages")

import types

from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QLineEdit,
    QFileDialog,
    QMessageBox,
    QTextEdit
)
from PySide6.QtCore import Qt
from tik_manager4.dcc.extension_core import ExtensionCore
import tik_manager4

from tik_manager4.objects.publisher import Publisher
from pathlib import Path
import datetime

import gazu

DEBUG_FILE = Path.home() / "TIK_REAL_PUBLISH_LOG.txt"

class PublisherConfirmationDialog(QWidget):

    _extension = None
    _selectedStatus = None

    def __init__(self, extensionInstance: 'FinalKitsuPublisher', shotDictionary: dict[int, str]):
        super().__init__()

        self._extension = extensionInstance
        self.setWindowTitle('Publish')
        self.setGeometry(100, 100, 550, 250)
        self.__shotDictionary = shotDictionary

        self.project = extensionInstance.getKitsuProject()
        self.allStatuses: list = gazu.task.all_task_statuses_for_project(self.project)

        self.statusBox = QComboBox()

        mainLayout = QVBoxLayout(self)
        buttonLayout = QHBoxLayout()

        mainLayout.addWidget(QLabel("Choose which version to publish:"))
        self.versionBox = QComboBox()
        for versionNumber, _ in shotDictionary.items():
            self.versionBox.addItem(str(versionNumber))
        mainLayout.addWidget(self.versionBox)
        if self.versionBox.count() > 0:
            last_index = self.versionBox.count() - 1
            self.versionBox.setCurrentIndex(last_index)

        mainLayout.addWidget(QLabel("Choose the task status:"))
        for status in self.allStatuses:
            self.statusBox.addItem(status['name'])

        mainLayout.addWidget(self.statusBox)
        if self.statusBox.count() > 0:
            self.statusBox.setCurrentIndex(0)

        mainLayout.addWidget(QLabel("Add a Comment for Kitsu:"))
        self.notesInput = QTextEdit()
        self.notesInput.setFixedHeight(100)
        mainLayout.addWidget(self.notesInput)

        mainLayout.addSpacing(15)

        self.publishButton = QPushButton('Publish')
        self.publishButton.setStyleSheet("font-weight: bold;")
        self.cancelButton = QPushButton('Cancel')

        # Verbindungen und Layout
        self.cancelButton.clicked.connect(self.close)
        self.publishButton.clicked.connect(self.onPublishConfirmed)

        mainLayout.addSpacing(10)
        buttonLayout.addWidget(self.cancelButton)
        buttonLayout.addWidget(self.publishButton)
        mainLayout.addLayout(buttonLayout)

        self.setWindowFlags(
            Qt.Window |
            Qt.CustomizeWindowHint |
            Qt.WindowTitleHint |
            Qt.WindowStaysOnTopHint
        )
        self.show()

    # setContextData bleibt unverändert

    def onPublishConfirmed(self):
        """Sammelt die Daten und startet den Publish-Flow (KEINE Kitsu ID mehr erforderlich)."""

        version = self.versionBox.currentText()
        file = self.__shotDictionary[int(version)]
        notes = self.notesInput.toPlainText().strip()
        statusName = self.statusBox.currentText()
        statusId = [s for s in self.allStatuses if s["name"] == statusName][0]['id']

        if not file:
            QMessageBox.warning(
                self,
                "Something went wrong",
                "There is no file for your version.",
                QMessageBox.StandardButton.Ok
            )
            return

        if not notes or notes == "":
            QMessageBox.warning(
                self,
                "No Comment",
                "You need to add a Comment.",
                QMessageBox.StandardButton.Ok
            )
            return

        self._extension.log("Publish-Process accepted! Start processing...")
        self._extension.runPublishFlow(notes=notes.strip(), previewPath=file, statusId=statusId)
        self.close()

class FinalKitsuPublisher(ExtensionCore):
    nice_name = "Final Kitsu Publish"
    _dialogWindow = None
    workObject = None

    def execute(self):
        self.add_function_to_main_menu(self.prepareAndRunPublish, "Publish")

    def log(self, text):
        try:
            with open(DEBUG_FILE, 'a', encoding='utf-8') as f:
                f.write(f"{datetime.datetime.now()}: {str(text)}\n")
        except Exception:
            pass

    def getKitsuProject(self) -> dict:
        projectName = self.parent.subprojects_mcv.get_active_subproject().get_project().name
        allProjects = gazu.client.get("/data/projects/all")
        project = [project for project in allProjects if project["name"] == projectName][0]
        return project

    def _getKitsuSequence(self) -> dict:
        project = self.getKitsuProject()
        sequenceName = self.parent.subprojects_mcv.get_active_subproject().name
        kitsuFilter = {"project_id": self.getKitsuProject()["id"]}
        allSequences = gazu.client.get("/data/sequences", params=kitsuFilter)
        sequence = [sequence for sequence in allSequences if sequence["name"] == sequenceName][0]
        return sequence

    def _getKitsuShot(self):
        sequenceName = self.parent.subprojects_mcv.get_active_subproject().name
        shotName = self.parent.tasks_mcv.get_active_task().name

        kitsuFilter = {
            "project_id": self.getKitsuProject()["id"],
            "sequence_id": self._getKitsuSequence()["id"]
        }
        allShots = gazu.client.get("/data/shots", params=kitsuFilter)
        shot = [shot for shot in allShots if shot["name"] == shotName][0]
        return shot

    def _getKitsuShotId(self):
        return self._getKitsuShot()["id"]

    def updateShotInKitsu(self, previewPath):
        shot = self._getKitsuShot()
        pathString = str(previewPath).replace("\\", "/")
        shot["data"]["absolutepath"] = str(pathString)
        gazu.shot.update_shot(shot)


    def setupRemoteDebug(self):
        vendorPath = r"X:\path\to\your\python\site-packages"
        if vendorPath not in sys.path:
            sys.path.insert(0, vendorPath)

        eggPath = r"X:\path\to\your\python\site-packages\pydevd-pycharm.egg"
        if eggPath not in sys.path:
            sys.path.insert(0, eggPath)

        # Dummy-Streams, falls Tik sys.stdout/sys.stderr auf None setzt
        class dummyStream:
            def write(self, msg):
                # optional ins Log schreiben:
                # self.log(f"[dummyStream] {msg}")
                pass

            def flush(self):
                pass

        if sys.stderr is None:
            sys.stderr = dummyStream()
        if sys.stdout is None:
            sys.stdout = dummyStream()

        # xmlrpc.server stubben, falls in der Umgebung fehlt
        try:
            import xmlrpc.server  # noqa
        except ImportError:
            xmlrpcModule = types.ModuleType("xmlrpc")
            xmlrpcServerModule = types.ModuleType("xmlrpc.server")

            class dummySimpleXmlrpcServer:
                def __init__(self, *args, **kwargs):
                    pass

                def registerFunction(self, *args, **kwargs):
                    pass

                def serveForever(self):
                    pass

                def shutdown(self):
                    pass

            xmlrpcServerModule.SimpleXMLRPCServer = dummySimpleXmlrpcServer
            xmlrpcModule.server = xmlrpcServerModule
            sys.modules["xmlrpc"] = xmlrpcModule
            sys.modules["xmlrpc.server"] = xmlrpcServerModule

        try:
            self.log("settrace() called successfully")
        except Exception as e:
            self.log("Error in setupRemoteDebug")
            self.log(repr(e))
            self.log(traceback.format_exc())

    def prepareAndRunPublish(self):
        """Öffnet den Bestätigungsdialog."""
        self.log("--- START VORBEREITUNGS-FLOW (DIALOG-ÖFFNUNG) ---")

        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        shotDictionary = self.getFiles()
        self._dialogWindow = PublisherConfirmationDialog(self, shotDictionary)
        # self._dialogWindow.show()
        self.log("Bestätigungsfenster angezeigt. Warte auf Benutzer-Daten.")

    def runPublishFlow(self, notes: str, previewPath: str, statusId: str):
        """Führt den eigentlichen Publish-Vorgang aus."""
        self.log("--- START KITSU PUBLISH ---")

        try:
            shot = self._getKitsuShot()
            allTasksOfShot = gazu.task.all_tasks_for_shot(shot)
            taskName = self.parent.categories_mcv.get_active_category().name

            task = [task for task in allTasksOfShot if task["task_type_name"] == taskName][0]["id"]
            project = self.getKitsuProject()

            user = gazu.client.get_current_user()

            gazu.task.publish_preview(task=task, task_status=statusId, comment=notes, person=user,
                                      preview_file_path=previewPath)
            parentFolder = Path(previewPath).parent
            self.updateShotInKitsu(parentFolder)

            self.__triggerDiscordMessage()
        except Exception as e:
            self.log("Error in runPublishFlow")
            self.log(repr(e))
        return

    def __getFolder(self):
        sequenceName = self.parent.subprojects_mcv.get_active_subproject().name
        taskName = self.parent.categories_mcv.get_active_category().name
        shotName = self.parent.tasks_mcv.get_active_task().name
        project = self.parent.tik.project

        projectRoot = project.folder + project.name

        basePath = Path(projectRoot) / "Shots" / sequenceName / shotName / taskName / "standalone" / "publish" / "previews"

        return basePath

    def getFiles(self) -> dict[int, str]:
            folder = self.__getFolder()
            outDict = {}
            if folder.exists():
                for filePath in folder.iterdir():
                    if filePath.is_file():
                        currentVersion = self.__getVersionFromFilename(filePath)
                        outDict[currentVersion] = str(filePath)
            else:
                raise ValueError("Folder doesn't exist")
            return outDict

    def __getVersionFromFilename(self, filePath: Path) -> int | None:
        fileName = filePath.name  # z.B. "myShot_v012.exr"
        match = re.search(r"_v(\d+)\.", fileName)
        if match:
            return int(match.group(1))
        return None

    def __triggerDiscordMessage(self):

        userData = gazu.client.get_current_user()

        artistFirstName = userData.get("first_name", "UNKNOWN")
        sequenceName = self.parent.subprojects_mcv.get_active_subproject().name
        shotName = self.parent.tasks_mcv.get_active_task().name
        kitsuShotUrl = "http://your-kitsu-server/open-productions"  # EDIT: your Kitsu URL

        discordMessage = (
            "🎬 Neuer Shot veröffentlicht!\n\n"
            f"👤 Artist: {artistFirstName}\n"
            f"🎞️ Shot: {sequenceName} / {shotName}\n\n"
            "🔗 Shot in Kitsu:\n"
            f"{kitsuShotUrl}\n\n"
            "👉 Bitte gebt Feedback direkt hier oder auf Kitsu 🙏"
        )

        MAX_LENGTH = 1900

        if len(discordMessage) > MAX_LENGTH:
            discordMessage = discordMessage[:MAX_LENGTH] + "…"

        discordMessage = discordMessage.encode("utf-8", "ignore").decode("utf-8")

        data = {'content': discordMessage}
        self._sendMessage(data)

    def _getWebHook(self) -> str:
        """Receive Web Hook"""

        rootFolder = Path(__file__).resolve().parents[3]
        targetPath = rootFolder / 'additional_config.json'

        with open(targetPath) as f:
            self._config = json.load(f)

        webhook = self._config.get('discordWebhook')
        return webhook

    def _sendMessage(self, data: dict):
        webhookUrl = self._getWebHook()
        if not webhookUrl:
            print('No webhook configured')
            return

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "TikManager-Blender/1.0"
        }
        request = urllib.request.Request(
            webhookUrl,
            data=json.dumps(data).encode("utf-8"),
            headers=headers
        )
        try:
            urllib.request.urlopen(request)
        except urllib.error.HTTPError as e:
            errorBody = e.read().decode("utf-8")
            print("Discord HTTPError:", e.code, errorBody)
        except Exception as e:
            print("Discord error:", e)