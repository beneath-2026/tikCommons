import re

import gazu
import bpy
from tik_manager4.dcc.extract_core import ExtractCore


class UploadPreviewPath(ExtractCore):
    nice_name = "Update Kitsu Data"
    optional = True
    durationChanged = False
    __kitsuShot = None

    def _extract_default(self) -> None:
        """
        Resolve output path of the preview and sends it to kitsu
        """
        blendPath = self.resolve_output()
        previewPath = blendPath.replace(f"/{self.extract_name}/", "/previews/") + ".mp4"
        folderPath = previewPath.rsplit("/", 1)[0]
        print(folderPath)

        self.updateShotInKitsu(folderPath)
        self.updateFollowingShots()

    def duration(self):
        start = bpy.context.scene.frame_start
        end = bpy.context.scene.frame_end
        duration = end - start + 1
        print(duration)
        self.durationChanged = True
        return duration

    def updateShotInKitsu(self, previewPath):
        shot = self.getKitsuShot()
        shot["data"]["absolutepath"] = previewPath
        shot["nb_frames"] = self.duration()
        gazu.shot.update_shot(shot)

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

    ### Helper Functions ###

    def getKitsuShot(self):
        if self.__kitsuShot is None:

            projectId = self.getKitsuProjectId()
            sequenceId = self.getKitsuSequenceId()
            filter = {
                "sequence_id": sequenceId,
                "project_id": projectId,
            }
            shotName = self.getMetaData()["shot"]
            allShots = self.getAllKitsuShots(filter)
            self.__kitsuShot = [shot for shot in allShots if shot["name"] == shotName][0]
        return self.__kitsuShot

    def getKitsuSequenceId(self):
        sequenceName = self.getMetaData()["sequence"]
        projectId = self.getKitsuProjectId()
        allSequences = gazu.client.get("/data/sequences")
        kitsuSequence = [sequence for sequence in allSequences if
                         ((sequence["name"] == sequenceName) & (sequence["project_id"] == projectId))][0]
        return kitsuSequence["id"]

    def getKitsuProjectId(self):
        projectName = self.getMetaData()["project"]
        allProjects = gazu.client.get("/data/projects/all")
        kitsuProject = [project for project in allProjects if project["name"] == projectName][0]
        return kitsuProject["id"]

    def getAllKitsuShots(self, kitsuFilter):
        allShots = gazu.client.get("/data/shots", params=kitsuFilter)

        # We sort by sequence_name and then by name to get the correct order of the shots

        return sorted(
            allShots,
            key=lambda shot: (
                (shot.get("sequence_name") or "").casefold(),
                (shot.get("name") or "").casefold(),
            ),
        )

    def getAllFollowingShotsAndCurrentShot(self):
        projectId = self.getKitsuProjectId()
        filter = {
            "project_id": projectId,
        }
        allShots = self.getAllKitsuShots(filter)
        currentShot = self.getKitsuShot()

        followingShots = []
        for shot in allShots:
            sequenceName = shot["sequence_name"]
            shotName = shot["name"]

            if sequenceName == currentShot["sequence_name"]:
                if shotName >= currentShot["name"]:
                    followingShots.append(shot)
            elif sequenceName > currentShot["sequence_name"]:
                followingShots.append(shot)

        return followingShots

    def updateFollowingShots(self):
        shots = self.getAllFollowingShotsAndCurrentShot()
        currentFrame = self.getKitsuShot()["data"]["frame_in"]  # start position
        for shot in shots:
            shot["data"]["frame_in"] = currentFrame
            duration = shot["nb_frames"]
            currentFrame += duration
            shot["data"]["frame_out"] = currentFrame - 1
            gazu.shot.update_shot(shot)
            currentFrame += 1
