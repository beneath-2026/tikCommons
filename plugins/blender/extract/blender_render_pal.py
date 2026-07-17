import json
import os
import subprocess
import logging
import sys
import traceback
import types
from pathlib import Path
import bpy

from tik_manager4.dcc.extract_core import ExtractCore
from tik_manager4.dcc.blender import utils

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)


class RenderPal(ExtractCore):
    """Submit a simple hardcoded render job to RenderPal V2 via CLI."""

    nice_name = "Render Scene (Simple Job)"
    optional = True
    renderPalExecutionPath = "C:/Program Files (x86)/RenderPal V2/CmdRC/rprccmd"
    bundled = True
    bundle_match_id = 1

    def __init__(self):
        _ranges = utils.get_ranges()
        print(_ranges)
        exposed_settings = {
            "Animation": {
                "job_name": {
                    "display_name": "Job Name",
                    "type": "string",
                    "value": "Blender Star Renderboiyugo",
                },
                "start": {
                    "display_name": "Start Frame",
                    "type": "integer",
                    "value": _ranges[0],
                },
                "end": {
                    "display_name": "End Frame",
                    "type": "integer",
                    "value": _ranges[3],
                },
                "batch_size": {
                    "display_name": "Batch Size",
                    "type": "integer",
                    "value": 10,
                },

            },
            "Layout": {
                "job_name": {
                    "display_name": "Job Name",
                    "type": "string",
                    "value": "Blender Star Renderboiyugo",
                },
                "start": {
                    "display_name": "Start Frame",
                    "type": "integer",
                    "value": _ranges[0],
                },
                "end": {
                    "display_name": "End Frame",
                    "type": "integer",
                    "value": _ranges[3],
                },
                "batch_size": {
                    "display_name": "Batch Size",
                    "type": "integer",
                    "value": 10,
                },

            },
            "Lighting": {
                "job_name": {
                    "display_name": "Job Name",
                    "type": "string",
                    "value": "Blender Star Renderboiyugo",
                },
                "start": {
                    "display_name": "Start Frame",
                    "type": "integer",
                    "value": _ranges[0],
                },
                "end": {
                    "display_name": "End Frame",
                    "type": "integer",
                    "value": _ranges[3],
                },
                "batch_size": {
                    "display_name": "Batch Size",
                    "type": "integer",
                    "value": 10,
                },

            },
        }
        super().__init__(exposed_settings=exposed_settings)

        rootFolder = Path(__file__).resolve().parents[3]
        configPath = rootFolder / 'additional_config.json'

        with open(configPath) as f:
            config = json.load(f)
        self.projectName = config['project']

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

    def _extract_default(self):
        """
        Extract method, called by TikManager.
        We use this to run our render submission command.
        """

        settings = self.settings.get(self.category)
        bundle_directory = Path(self.resolve_output())
        bundle_directory.mkdir(parents=True, exist_ok=True)
        infoFilePath = Path(bundle_directory / "info.txt")
        with open(infoFilePath, "w") as infoFile:
            infoFile.write(f"bundle_directory: {bundle_directory}")

        executablePath = 'C:/Program Files (x86)/RenderPal V2/CmdRC/rprccmd'
        blendPath = bpy.data.filepath
        renderer = f"Blender/{self.projectName}"
        jobName = f"{settings.get('job_name')}: {os.path.basename(blendPath)}"
        frames = f"{settings.get('start')}-{settings.get('end')}"
        outfile = 'frame_####'
        splitmode = f"1,{settings.get('batch_size')}"
        


        command_list = [
            executablePath,
            '-nj_renderer', renderer,
            '-nj_name', jobName,
            '-frames', frames,
            '-outdir', str(bundle_directory),
            '-outfile', outfile,
            '-nj_splitmode', splitmode,
            '-login', f"{os.environ.get('RP_USER', '')}:{os.environ.get('RP_PASSWORD', '')}",
            '-server', os.environ.get('RP_SERVER', 'your-renderpal-server:7506'),
            blendPath,
        ]
        print(f"Executing command: {' '.join(command_list)}")
        LOG.info(f"Executing command: {' '.join(command_list)}")

        try:
            subprocess.Popen(
                command_list,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            print("All went well")

        except FileNotFoundError:
            LOG.error(f"Executable not found: {executablePath}")
            self.set_message(f"FEHLER: rprccmd Executable nicht gefunden.")
            raise

        except subprocess.CalledProcessError as e:
            LOG.error(f"Command failed. STDOUT: {e.stdout} STDERR: {e.stderr}")
            self.set_message(f"FEHLER RenderPal CLI: {e.stderr or e.stdout}")
            raise

        except subprocess.TimeoutExpired:
            LOG.error(f"Command timed out.")
            self.set_message(f"FEHLER: RenderPal hat das Timeout überschritten.")
            raise



