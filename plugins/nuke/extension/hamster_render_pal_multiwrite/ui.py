import nuke
from PySide6 import QtCore, QtWidgets

"""
UI components for the RenderPal MultiWrite submission workflow.

This module contains only PySide dialogs/helpers:
- Render settings dialog (per-shot outdir + frame range)
- Progress dialog (always-on-top, cancelable)
- Optional submit debug dialog (manual breakpoint before farm submission)

No Nuke graph manipulation or RenderPal submission logic should live here.
"""


class SubmitDebugDialog(QtWidgets.QDialog):
    """
        Modal dialog used as a manual breakpoint while debugging submissions.

        Shows a read-only text block (e.g. script path, shot name, command line)
        and lets the user either continue or cancel the current job.
        """
    def __init__(self, parent=None, title="Submit Debug", text=""):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(900)
        self.setMinimumHeight(500)

        layout = QtWidgets.QVBoxLayout(self)

        self.textEdit = QtWidgets.QPlainTextEdit()
        self.textEdit.setReadOnly(True)
        self.textEdit.setPlainText(text)
        layout.addWidget(self.textEdit)

        buttonRow = QtWidgets.QHBoxLayout()
        buttonRow.addStretch()

        self.cancelBtn = QtWidgets.QPushButton("Cancel This Job")
        self.cancelBtn.clicked.connect(self.reject)
        buttonRow.addWidget(self.cancelBtn)

        self.okBtn = QtWidgets.QPushButton("Continue Submit")
        self.okBtn.clicked.connect(self.accept)
        buttonRow.addWidget(self.okBtn)

        layout.addLayout(buttonRow)


class ProcessProgressDialog(QtWidgets.QDialog):
    """
        Non-modal progress window that stays on top.

        Provides:
        - status label
        - progress bar (0..100)
        - log text area
        - cancel button (sets cancelRequested flag)

        The dialog processes Qt events in setProgress/logLine so long-running
        loops remain responsive.
        """
    def __init__(self, parent=None, title="RenderPal MultiWrite"):
        super().__init__(parent)

        self.setWindowTitle(title)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)
        self.setWindowModality(QtCore.Qt.NonModal)
        self.setMinimumWidth(650)

        layout = QtWidgets.QVBoxLayout(self)

        self.statusLabel = QtWidgets.QLabel("Starting...")
        layout.addWidget(self.statusLabel)

        self.progressBar = QtWidgets.QProgressBar()
        self.progressBar.setRange(0, 100)
        self.progressBar.setValue(0)
        layout.addWidget(self.progressBar)

        self.detailText = QtWidgets.QPlainTextEdit()
        self.detailText.setReadOnly(True)
        self.detailText.setMinimumHeight(220)
        layout.addWidget(self.detailText)

        self.cancelRequested = False
        self.cancelBtn = QtWidgets.QPushButton("Cancel")
        self.cancelBtn.clicked.connect(self._onCancel)
        layout.addWidget(self.cancelBtn)

    def _onCancel(self):
        self.cancelRequested = True
        self.statusLabel.setText("Cancel requested...")

    def setProgress(self, percent, statusText=None):
        percent = max(0, min(100, int(percent)))
        self.progressBar.setValue(percent)
        if statusText:
            self.statusLabel.setText(statusText)

        self.raise_()
        self.activateWindow()

        appInstance = QtWidgets.QApplication.instance()
        if appInstance:
            appInstance.processEvents()

    def logLine(self, text):
        self.detailText.appendPlainText(str(text))
        appInstance = QtWidgets.QApplication.instance()
        if appInstance:
            appInstance.processEvents()


class RenderPalDialog(QtWidgets.QDialog):
    """
        RenderPal settings dialog for MultiWrite submissions.

        Displays one row per shot with:
        - Shot name (read-only)
        - Start / End frames (editable)
        - Output directory (editable + folder picker)

        Use getValues() to read the final settings.
        """

    def __init__(self, parent=None, initialData=None):
        super().__init__(parent)
        initialData = initialData or {}

        self.setWindowTitle("RenderPal Submission (MultiWrite)")
        self.setMinimumWidth(950)

        layout = QtWidgets.QVBoxLayout(self)

        layout.addWidget(QtWidgets.QLabel("Job Name:"))
        self.jobNameEdit = QtWidgets.QLineEdit(initialData.get("jobName", "Nuke Job"))
        layout.addWidget(self.jobNameEdit)

        layout.addWidget(QtWidgets.QLabel("Batch Size:"))
        self.batchSizeSpin = QtWidgets.QSpinBox()
        self.batchSizeSpin.setValue(initialData.get("batchSize", 10))
        layout.addWidget(self.batchSizeSpin)

        layout.addWidget(QtWidgets.QLabel("Per-Shot Settings:"))
        self.shotTable = QtWidgets.QTableWidget()
        self.shotTable.setColumnCount(5)
        self.shotTable.setHorizontalHeaderLabels(["Shot", "Start", "End", "Output Directory", ""])
        self.shotTable.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        self.shotTable.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.shotTable.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        self.shotTable.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.Stretch)
        self.shotTable.setColumnWidth(4, 40)
        layout.addWidget(self.shotTable)

        self.shotRows = initialData.get("shotRows", [])
        self._populateRows()

        self.submitBtn = QtWidgets.QPushButton("Submit to RenderPal")
        self.submitBtn.clicked.connect(self.accept)
        layout.addWidget(self.submitBtn)

    def _populateRows(self):
        self.shotTable.setRowCount(len(self.shotRows))

        for rowIndex, rowData in enumerate(self.shotRows):
            shotName = rowData["shot"]
            outDir = rowData["outDir"]
            startFrame = int(rowData["start"])
            endFrame = int(rowData["end"])

            shotItem = QtWidgets.QTableWidgetItem(shotName)
            shotItem.setFlags(shotItem.flags() & ~QtCore.Qt.ItemIsEditable)
            self.shotTable.setItem(rowIndex, 0, shotItem)

            startSpin = QtWidgets.QSpinBox()
            startSpin.setRange(-999999, 999999)
            startSpin.setValue(startFrame)
            self.shotTable.setCellWidget(rowIndex, 1, startSpin)

            endSpin = QtWidgets.QSpinBox()
            endSpin.setRange(-999999, 999999)
            endSpin.setValue(endFrame)
            self.shotTable.setCellWidget(rowIndex, 2, endSpin)

            outItem = QtWidgets.QTableWidgetItem(outDir)
            self.shotTable.setItem(rowIndex, 3, outItem)

            browseBtn = QtWidgets.QPushButton("...")
            browseBtn.setFixedWidth(30)
            browseBtn.clicked.connect(lambda _=False, r=rowIndex: self._browseRowFolder(r))
            self.shotTable.setCellWidget(rowIndex, 4, browseBtn)

    def _browseRowFolder(self, rowIndex):
        currentText = self.shotTable.item(rowIndex, 3).text() if self.shotTable.item(rowIndex, 3) else ""
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Output Directory", currentText)
        if directory:
            self.shotTable.item(rowIndex, 3).setText(directory)

    def getValues(self):
        perShotOutDirs = {}
        perShotRanges = {}

        for rowIndex in range(self.shotTable.rowCount()):
            shotName = self.shotTable.item(rowIndex, 0).text().strip()
            outDir = self.shotTable.item(rowIndex, 3).text().strip()

            startSpin = self.shotTable.cellWidget(rowIndex, 1)
            endSpin = self.shotTable.cellWidget(rowIndex, 2)

            startFrame = int(startSpin.value())
            endFrame = int(endSpin.value())

            if startFrame > endFrame:
                nuke.message(f"{shotName}: Start > End ({startFrame} > {endFrame})")
                continue

            perShotOutDirs[shotName] = outDir
            perShotRanges[shotName] = (startFrame, endFrame)

        return {
            "jobName": self.jobNameEdit.text(),
            "batchSize": self.batchSizeSpin.value(),
            "perShotOutDirs": perShotOutDirs,
            "perShotRanges": perShotRanges
        }


class ProgressReporter:
    """
        Small helper to drive a progress window with step-based progress.

        The reporter assumes the UI exposes:
        - setProgress(percent:int, statusText:str|None)
        - logLine(text:str)
        - cancelRequested: bool
        - close()

        Progress is computed as: currentStep / totalSteps * 100.

        Args:
            progressUi: A progress dialog instance (Qt).
            totalSteps (int): Total number of steps in the workflow.
        """
    def __init__(self, progressUi, totalSteps):
        self.progressUi = progressUi
        self.totalSteps = max(1, int(totalSteps))
        self.currentStep = 0

    def log(self, text):
        self.progressUi.logLine(text)

    def step(self, statusText, logText=None):
        self.currentStep += 1
        percent = int(round((self.currentStep / float(self.totalSteps)) * 100.0))
        self.progressUi.setProgress(percent, statusText=statusText)
        if logText:
            self.progressUi.logLine(logText)
        return not self.progressUi.cancelRequested

    def isCancelled(self):
        return bool(self.progressUi.cancelRequested)

    def finish(self, submittedCount):
        self.progressUi.setProgress(100, "Done.")
        self.progressUi.logLine(f"Submitted jobs: {submittedCount}")

    def close(self):
        self.progressUi.close()


def showSubmitDebugDialog(debugText, title="RenderPal Submit Debug"):
    appInstance = QtWidgets.QApplication.instance()
    if not appInstance:
        appInstance = QtWidgets.QApplication([])

    parentWin = QtWidgets.QApplication.activeWindow()
    dialog = SubmitDebugDialog(parent=parentWin, title=title, text=debugText)
    return dialog.exec_() == QtWidgets.QDialog.Accepted


def getActiveParentWindow():
    appInstance = QtWidgets.QApplication.instance()
    if not appInstance:
        return None
    return QtWidgets.QApplication.activeWindow()


def showRenderSettingsDialog(initialData):
    parentWin = getActiveParentWindow()
    if not parentWin:
        return None
    dialog = RenderPalDialog(parent=parentWin, initialData=initialData)
    if dialog.exec_() != QtWidgets.QDialog.Accepted:
        return None
    return dialog.getValues()


def createProgressWindow(title):
    parentWin = getActiveParentWindow()
    dialog = ProcessProgressDialog(parent=parentWin, title=title)
    dialog.show()
    dialog.setProgress(0, "Starting...")
    return dialog
