import json
import sys
from pathlib import Path

import nuke


def setupEnvironment(extensionFilePath):
    """
    Makes sure:
    - the 'extensions/' folder (parent of the entry .py) is on sys.path so the package can be imported
    - vendor + project paths from additional_config.json are on sys.path

    Returns:
        dict: loaded config (or empty dict if not found)
    """
    entryFilePath = Path(extensionFilePath).resolve()
    extensionsDir = entryFilePath.parent
    if str(extensionsDir) not in sys.path:
        sys.path.insert(0, str(extensionsDir))

    rootFolder = entryFilePath.parents[3]
    configPath = rootFolder / "additional_config.json"

    if not configPath.exists():
        return {}

    try:
        with configPath.open("r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception:
        # If config is broken, don't block plugin load
        return {}

    vendorPath = config.get("vendor")
    projectPath = config.get("path")

    if vendorPath and vendorPath not in sys.path:
        sys.path.insert(0, vendorPath)

    if projectPath and projectPath not in sys.path:
        sys.path.insert(0, projectPath)

    return config
