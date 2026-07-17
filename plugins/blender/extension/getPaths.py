import json
import sys
from pathlib import Path

from tik_manager4.dcc.extension_core import ExtensionCore


class GetPaths(ExtensionCore):
    config = None
    pathToolWindow = None

    def execute(self):
        """Initial execution."""
        self.add_function_to_main_menu(self.start, "Get Paths")

    def start(self):
        """This method will be called when the menu item is clicked."""
        rootFolder = Path(__file__).resolve().parents[3]
        targetPath = rootFolder / 'additional_config.json'

        with open(targetPath) as f:
            self.config = json.load(f)
            if self.config["vendor"] not in sys.path:
                sys.path.insert(0, self.config["vendor"])
            if self.config["path"] not in sys.path:
                sys.path.insert(0, self.config["path"])

        from pathTool import main as pathToolMain
        from shiboken6 import isValid

        if self.pathToolWindow and isValid(self.pathToolWindow):
            self.pathToolWindow.show()
            self.pathToolWindow.raise_()
            self.pathToolWindow.activateWindow()
        else:
            self.pathToolWindow = pathToolMain.startPathTool()
