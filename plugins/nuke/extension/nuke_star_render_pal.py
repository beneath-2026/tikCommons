import json
import logging
import os
import subprocess
import sys
from pathlib import Path

import nuke

rootFolder = Path(__file__).resolve().parents[3]
targetPath = rootFolder / 'additional_config.json'

with open(targetPath) as f:
    config = json.load(f)
    if config["vendor"] not in sys.path:
        sys.path.insert(0, config["vendor"])
    if config["path"] not in sys.path:
        sys.path.insert(0, config["path"])

from PySide6 import QtWidgets
from tik_manager4.dcc.nuke import utils
from tik_manager4.dcc.extension_core import ExtensionCore

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)


class RenderPalDialog(QtWidgets.QDialog):
    """Einfaches UI für User-Input innerhalb der Extension."""

    def __init__(self, parent=None, initial_data=None):
        super().__init__(parent)
        self.setWindowTitle("RenderPal Submission")
        self.setMinimumWidth(400)

        layout = QtWidgets.QVBoxLayout(self)

        # Job Name
        layout.addWidget(QtWidgets.QLabel("Job Name:"))
        self.job_name = QtWidgets.QLineEdit(initial_data.get("job_name", "Nuke Job"))
        layout.addWidget(self.job_name)

        # Frames
        frame_layout = QtWidgets.QHBoxLayout()
        self.start_frame = QtWidgets.QSpinBox()
        self.start_frame.setRange(-999999, 999999)
        self.start_frame.setValue(initial_data.get("start", 1))

        self.end_frame = QtWidgets.QSpinBox()
        self.end_frame.setRange(-999999, 999999)
        self.end_frame.setValue(initial_data.get("end", 100))

        frame_layout.addWidget(QtWidgets.QLabel("Start:"))
        frame_layout.addWidget(self.start_frame)
        frame_layout.addWidget(QtWidgets.QLabel("End:"))
        frame_layout.addWidget(self.end_frame)
        layout.addLayout(frame_layout)

        # Batch Size
        layout.addWidget(QtWidgets.QLabel("Batch Size:"))
        self.batch_size = QtWidgets.QSpinBox()
        self.batch_size.setValue(10)
        layout.addWidget(self.batch_size)

        # Output Path
        layout.addWidget(QtWidgets.QLabel("Output Directory:"))
        path_layout = QtWidgets.QHBoxLayout()
        self.output_path = QtWidgets.QLineEdit(initial_data.get("outdir", ""))
        self.btn_browse = QtWidgets.QPushButton("...")
        self.btn_browse.setFixedWidth(30)
        self.btn_browse.clicked.connect(self.browse_folder)
        path_layout.addWidget(self.output_path)
        path_layout.addWidget(self.btn_browse)
        layout.addLayout(path_layout)

        # Buttons
        self.btn_submit = QtWidgets.QPushButton("Submit to RenderPal")
        self.btn_submit.clicked.connect(self.accept)
        layout.addWidget(self.btn_submit)

    def browse_folder(self):
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Output Directory", self.output_path.text())
        if directory:
            self.output_path.setText(directory)

    def get_values(self):
        return {
            "job_name": self.job_name.text(),
            "start": self.start_frame.value(),
            "end": self.end_frame.value(),
            "batch_size": self.batch_size.value(),
            "outdir": self.output_path.text()
        }


class RenderPalSubmission(ExtensionCore):

    def execute(self):
        """Initial execution."""
        # Projektname laden (wie im Extractor)
        self.load_config()
        self.add_function_to_main_menu(self.start, "RenderPal Submission")

    def load_config(self):
        try:
            root_folder = Path(__file__).resolve().parents[3]
            config_path = root_folder / 'additional_config.json'
            with open(config_path) as f:
                config = json.load(f)
            self.projectName = config.get('project', 'DefaultProject')
            self.config = config
        except Exception:
            self.projectName = "UnknownProject"

    def getCurrentSelection(self):
        sequenceName = self.parent.subprojects_mcv.get_active_subproject().name
        shotName = self.parent.tasks_mcv.get_active_task().name
        taskName = self.parent.categories_mcv.get_active_category().name
        return sequenceName, shotName, taskName

    def generateOutDir(self):
        basePath: Path = Path(self.config.get("renderFolder").get(self.projectName))

        sequenceName, shotName, taskName = self.getCurrentSelection()
        if not sequenceName or not shotName or not taskName:
            nuke.tprint("[RENDER ERROR] sequenceName or shotName or taskName missing")
            nuke.tprint(f"{sequenceName}, {shotName}, {taskName}")
            return None

        parentPath = basePath / sequenceName / shotName / taskName
        parentPath.mkdir(parents=True, exist_ok=True)

        maxVersion = 0

        for folder in parentPath.iterdir():
            nuke.tprint(f"[INFO] folder: {folder}")

            if not folder.is_dir():
                nuke.tprint(f"[INFO] folder: {folder} is not a directory")
                continue

            name = folder.name
            versionString = name.split("_")[-1]

            if not versionString.startswith("v"):
                nuke.tprint(f"[INFO] folder: {name} does not start with 'v'")

                continue

            numberPart = versionString[1:]
            if not numberPart.isdigit():
                nuke.tprint(f"[INFO] number: {numberPart} is not a digit")
                continue

            versionNumber = int(numberPart)
            maxVersion = max(maxVersion, versionNumber)
            nuke.tprint(f"[INFO] max Version: {maxVersion}")

        newestVersion = f"v{maxVersion + 1:03d}"
        nuke.tprint(f"[INFO] newest Version: {newestVersion}")

        folderName = f"{sequenceName}_{shotName}_{taskName}_{newestVersion}"
        return str(parentPath / folderName)

    def start(self):
        """Wird aufgerufen, wenn der Menüpunkt geklickt wird."""

        app = QtWidgets.QApplication.instance()
        if not app:
            app = QtWidgets.QApplication([])

        # 1. Daten vorbereiten
        _ranges = utils.get_ranges()
        default_out = self.generateOutDir()

        initial_data = {
            "job_name": f"Nuke {self.projectName} Render",
            "start": _ranges[0],
            "end": _ranges[3],
            "outdir": default_out
        }
        # 2. Dialog anzeigen
        parent_win = QtWidgets.QApplication.activeWindow()
        dialog = RenderPalDialog(parent=parent_win, initial_data=initial_data)

        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            settings = dialog.get_values()
            bundle_directory = settings.get("outdir")
            if not os.path.exists(bundle_directory):
                os.mkdir(bundle_directory)
            nukePath = nuke.root().name()
            folderName = Path(bundle_directory).name

            # 3. RenderPal Command zusammenbauen
            executable_path = 'C:/Program Files (x86)/RenderPal V2/CmdRC/rprccmd'
            renderer = f"Nuke/hamster"
            job_name_full = f"{settings.get('job_name')}: {os.path.basename(nukePath)}"
            frames = f"{settings.get('start')}-{settings.get('end')}"
            outfile = folderName + '_frame_####.exr'
            splitmode = f"1,{settings.get('batch_size')}"

            writeNodes = nuke.allNodes("Write")
            writeNodeOne = writeNodes[0]
            for writeNode in writeNodes:
                if writeNode.name() == "Write1":
                    writeNodeOne = writeNode

            writeNodeOne["file_type"].setValue("exr")
            writeOut = bundle_directory + "/" + outfile
            cleanedWriteOut = writeOut.replace("\\", "/")
            writeNodeOne["file"].setValue(cleanedWriteOut)
            nuke.scriptSave()

            command_list = [
                executable_path,
                '-nj_renderer', renderer,
                '-nj_name', job_name_full,
                '-frames', frames,
                # '-outdir', str(bundle_directory),
                # '-outfile', outfile,
                '-nj_splitmode', splitmode,
                '-login', f"{os.environ.get('RP_USER', '')}:{os.environ.get('RP_PASSWORD', '')}",
                '-server', os.environ.get('RP_SERVER', 'your-renderpal-server:7506'),
                nukePath,
            ]

            nuke.tprint(f"Executing command: {' '.join(command_list)}")
            LOG.info(f"Executing command: {' '.join(command_list)}")

            try:
                subprocess.Popen(
                    command_list,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                if hasattr(self, 'set_message'):
                    self.set_message("Job erfolgreich an RenderPal gesendet!")
                nuke.tprint("All went well")

            except FileNotFoundError:
                nuke.tprint(f"Executable not found: {executable_path}")
                raise
            except Exception as e:
                nuke.tprint(f"Error submitting job: {str(e)}")
                raise
