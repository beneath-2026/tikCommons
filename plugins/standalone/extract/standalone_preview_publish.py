import logging
import os
from tik_manager4.dcc.extract_core import ExtractCore

# Definiere den Pfad zur Log-Datei. Wähle einen Ort, wo dein Skript schreiben darf.
# Zum Beispiel im temporären Ordner des Benutzers oder direkt neben dem Skript/Projekt-Ordner.
LOG_FILE = os.path.join(os.path.expanduser('~'), 'tik_publish_test.log')


class PreviewPublish(ExtractCore):
    nice_name = "Preview Publish"


    def __init__(self):
        super(PreviewPublish, self).__init__()
        # Richte das Logging ein (nur einmal beim Initialisieren)
        logging.basicConfig(
            filename=LOG_FILE,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        logging.info("PreviewPublish Extractor initialisiert.")
        self.extension = ".clip"
        
    @property
    def source_path(self):
        return self._source_path

    @source_path.setter
    def source_path(self, val):
        self._source_path = val

    def _extract_default(self):
        """Extract for any non-specified category."""

        # 🚨 DIESER CODE WIRD GETRIGGERT 🚨
        logging.info("************************************************")
        logging.info(">>> _extract_default METHODE WURDE AUFGERUFEN <<<")
        logging.info("************************************************")

        # Hier sollte die eigentliche Logik stehen, z.B. das Kopieren der Datei.

        # Die Methode muss einen Rückgabewert liefern. 
        # Wenn du keinen echten Publish machst, könntest du ein Dummy-Ergebnis zurückgeben.
        # Aber da du einen Publish bauen willst, musst du die erwarteten Publish-Daten liefern.
        print("___________________________________________________________________________")
        print("___________________________________________________________________________")
        print("___________________________________________________________________________")
        print("___________________________________________________________________________")


        return {
            "extract_name": self.nice_name,
            "success": True,  # Wichtig: Muss True sein, damit Tik Manager fortfährt.
            "message": "Extractor erfolgreich getestet."
            # Hier kämen die Pfade zu den extrahierten Dateien rein
            # "files": ["/path/to/extracted/render.png"] 
        }