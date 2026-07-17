from pathlib import Path

import hou
from tik_manager4.dcc.ingest_core import IngestCore


class UsdGeoIngest(IngestCore):
    nice_name = "Ingest USD geo (stage)"
    valid_extensions = [".usd", ".usda", ".usdz", ".usdb", ".usdnc"]
    referencable = False

    def __init__(self) -> None:
        super().__init__()

    def _bring_in_default(self) -> None:
        """Import Alembic via sopcreate LOP > sopnet > create > alembic SOP."""
        jobPath = hou.getenv("JOB")
        try:
            filePath = "$JOB/" + str(Path(self.ingest_path).relative_to(jobPath))
        except (ValueError, TypeError):
            filePath = str(self.ingest_path)

        nodeName = Path(self.ingest_path).stem
        stageNode = hou.node("/stage")

        payloadNode = stageNode.createNode("reference", node_name=nodeName)
        payloadNode.parm("filepath1").set(filePath)
        payloadNode.parm("reftype1").set("payload")
        payloadNode.parm("primpath").set("/geo/")
        payloadNode.parm("primpath1").set("/geo/")
        payloadNode.moveToGoodPosition()

        graftGeoNode = payloadNode.createOutputNode("graftstages", node_name="place_in_geo")
        graftGeoNode.parm("primpath").set("")
        graftGeoNode.parm("destpath").set("/geo/")

        configureLayerNode = graftGeoNode.createOutputNode("configurelayer", node_name="geo")
        namespace = self._namespace
        configureLayerNode.parm("setsavepath").set(True)
        configureLayerNode.parm("savepath").set(f"$HIP/usd/geo_{namespace}.usda")

        referenceGeoNode = stageNode.createNode("reference", node_name="reference_usd_geo")
        referenceGeoNode.setInput(1, configureLayerNode)
        referenceGeoNode.parm("primpath").set("/geo/")

        materialLibraryNode = stageNode.createNode("materiallibrary", node_name="materiallib")
        configureMaterialLayerNode = materialLibraryNode.createOutputNode(
            "configurelayer",
            node_name="material"
        )

        assetName = namespace.split("_")[0]
        configureMaterialLayerNode.parm("setsavepath").set(True)
        configureMaterialLayerNode.parm("savepath").set(f"$HIP/usd/geo_{assetName}_Shading.usda")

        referenceMatNode = stageNode.createNode("reference", node_name="reference_usd_mat")
        referenceMatNode.setInput(1, configureMaterialLayerNode)
        referenceMatNode.parm("primpath").set("/material/")

        # reference1
        merge = stageNode.createNode("merge", node_name="merge")
        merge.setInput(0, referenceGeoNode)
        merge.setInput(1, referenceMatNode)

        # assign material -> usd rop
        assignMaterialNode = merge.createOutputNode(
            "assignmaterial",
            node_name="assignmaterial1"
        )

        placeInAssetGraft = stageNode.createNode("graftstages", node_name=f"place_in_{assetName}")
        placeInAssetGraft.setInput(1, assignMaterialNode)

        placeInAssetGraft.parm("destpath").set(f"/{assetName}/")
        placeInAssetGraft.parm("primpath").set("")

        usdRopNode = placeInAssetGraft.createOutputNode(
            "usd_rop",
            node_name="usd_rop1"
        )
        usdRopNode.parm("lopoutput").set(f"$HIP/usd/{assetName}_assembly.usda")
        usdRopNode.parm("enableoutputprocessor_simplerelativepaths").set(False)

        stageNode.layoutChildren(
            items=[
                payloadNode,
                configureLayerNode,
                referenceGeoNode,
                referenceMatNode,
                graftGeoNode,
                materialLibraryNode,
                configureMaterialLayerNode,
                merge,
                assignMaterialNode,
                usdRopNode,
                placeInAssetGraft,
            ]
        )

    def _reference_default(self) -> None:
        """Reference Alembic file — identical to bring-in for stage context."""
        self._bring_in_default()
