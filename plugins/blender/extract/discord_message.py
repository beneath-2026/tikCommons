import json
import re
import urllib.request
from pathlib import Path

import gazu
from tik_manager4.dcc.extract_core import ExtractCore


class DiscordMessage(ExtractCore):
    nice_name = "Discord Message"
    optional = True

    def __init__(self):
        super(DiscordMessage, self).__init__()
        self._config = None

    def _extract_default(self):

        metaData = self.getMetaData()
        userData = gazu.client.get_current_user()

        artistFirstName = userData.get("first_name", "UNKNOWN")
        sequenceName = metaData.get("sequence", "-")
        shotName = metaData.get("shot", "-")
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

    def getMetaData(self):
        path = self.resolve_output()  # 'M:/star/Shots/SE102/050/Layout/blender/publish/050_Layout_001/BLENDER_VIDEO_EXPORTER_050_Layout_001_v002'
        norm = path.replace("\\", "/")
        # Regex:
        # - optionales Laufwerk/Prefix (z.B. "M:" oder "//server/share") wird toleriert
        # - fange 'project' direkt nach dem Root/Drive ab
        # - dann /Shots/ (case-insensitive)
        # - dann 'sequence' und 'shot' als je ein Pfadsegment
        pattern = re.compile(
            r"""
            /(?P<project>[^/]+)
            /Shots/
            (?P<sequence>[^/]+)
            /(?P<shot>[^/]+)
            (?:/|$)
            """,
            re.IGNORECASE | re.VERBOSE,
        )

        m = pattern.search(norm)
        if not m:
            raise ValueError(
                f"Pfad konnte nicht geparst werden (erwartet .../<project>/Shots/<sequence>/<shot>/...): {path}"
            )

        project = m.group("project")
        sequence = m.group("sequence")
        shot = m.group("shot")

        return {"project": project, "sequence": sequence, "shot": shot}
