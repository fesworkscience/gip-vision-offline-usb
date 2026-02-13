from __future__ import annotations

import logging
import re
import tempfile
import time
from pathlib import Path

import numpy as np
import trimesh
from pygltflib import GLTF2
from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade, UsdUtils, Vt

logger = logging.getLogger(__name__)


def _sanitize_name(name: str) -> str:
    sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    if sanitized and sanitized[0].isdigit():
        sanitized = "_" + sanitized
    return sanitized or "_unnamed"


def _get_material_color(geom):
    if not hasattr(geom, "visual") or geom.visual is None:
        return None

    vis = geom.visual

    if hasattr(vis, "material") and vis.material is not None:
        mat = vis.material
        if hasattr(mat, "baseColorFactor") and mat.baseColorFactor is not None:
            c = mat.baseColorFactor
            if len(c) >= 3:
                r, g, b = c[0], c[1], c[2]
                if max(r, g, b) > 1:
                    return (r / 255.0, g / 255.0, b / 255.0)
                return (float(r), float(g), float(b))

    if hasattr(vis, "vertex_colors") and vis.vertex_colors is not None:
        colors = vis.vertex_colors
        if len(colors) > 0:
            avg = colors.mean(axis=0)[:3]
            if avg.max() > 1:
                return (avg[0] / 255.0, avg[1] / 255.0, avg[2] / 255.0)
            return tuple(avg)

    return None


def glb_to_usdz_fast(glb_path: str, usdz_path: str) -> dict:
    start_time = time.time()
    stats = {
        "vertex_count": 0,
        "face_count": 0,
        "mesh_count": 0,
        "material_count": 0,
    }

    try:
        gltf = GLTF2().load(str(glb_path))
        scene = trimesh.load(str(glb_path), process=False)

        node_to_guid = {}
        for node in gltf.nodes:
            if node.mesh is not None and node.name:
                node_to_guid[node.mesh] = node.name

        stats["file_size_bytes"] = Path(glb_path).stat().st_size

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_dir = Path(tmp_dir)
            usdc_path = tmp_dir / "model.usdc"

            stage = Usd.Stage.CreateNew(str(usdc_path))
            stage.SetMetadata("metersPerUnit", 1.0)
            stage.SetMetadata("upAxis", "Y")

            root = UsdGeom.Xform.Define(stage, "/Root")
            materials_cache = {}

            if isinstance(scene, trimesh.Scene):
                mesh_items = []
                for node_name in scene.graph.nodes_geometry:
                    transform, geom_name = scene.graph[node_name]
                    geom = scene.geometry.get(geom_name)
                    if geom is None or not isinstance(geom, trimesh.Trimesh) or len(geom.faces) == 0:
                        continue
                    transformed = geom.copy()
                    transformed.apply_transform(transform)
                    mesh_items.append((node_name, transformed, geom))
            else:
                mesh_items = [("mesh_0", scene, scene)]

            mesh_idx = 0
            for node_name, transformed_geom, original_geom in mesh_items:
                guid = node_to_guid.get(mesh_idx, node_name)
                prim_name = _sanitize_name(str(guid))
                mesh_path = f"/Root/{prim_name}"

                counter = 1
                base_path = mesh_path
                while stage.GetPrimAtPath(mesh_path).IsValid():
                    mesh_path = f"{base_path}_{counter}"
                    counter += 1

                mesh_prim = UsdGeom.Mesh.Define(stage, mesh_path)

                vertices = transformed_geom.vertices.astype(np.float64)
                faces = transformed_geom.faces.astype(np.int32)

                stats["vertex_count"] += len(vertices)
                stats["face_count"] += len(faces)
                stats["mesh_count"] += 1

                points = Vt.Vec3fArray([Gf.Vec3f(float(v[0]), float(v[1]), float(v[2])) for v in vertices])
                mesh_prim.GetPointsAttr().Set(points)
                mesh_prim.GetFaceVertexCountsAttr().Set(Vt.IntArray([3] * len(faces)))
                mesh_prim.GetFaceVertexIndicesAttr().Set(Vt.IntArray(faces.flatten().tolist()))
                mesh_prim.GetSubdivisionSchemeAttr().Set(UsdGeom.Tokens.none)
                mesh_prim.GetOrientationAttr().Set(UsdGeom.Tokens.rightHanded)

                if hasattr(transformed_geom, "vertex_normals") and len(transformed_geom.vertex_normals) > 0:
                    normals = transformed_geom.vertex_normals.astype(np.float64)
                    normals_vec = Vt.Vec3fArray([Gf.Vec3f(float(n[0]), float(n[1]), float(n[2])) for n in normals])
                    mesh_prim.GetNormalsAttr().Set(normals_vec)
                    mesh_prim.SetNormalsInterpolation(UsdGeom.Tokens.vertex)

                mesh_prim.GetDoubleSidedAttr().Set(True)

                color = _get_material_color(original_geom) or (0.8, 0.8, 0.8)
                color_key = (round(color[0], 3), round(color[1], 3), round(color[2], 3))

                if color_key not in materials_cache:
                    mat_idx = len(materials_cache)
                    mat_path = f"/Root/Materials/Mat_{mat_idx}"

                    material = UsdShade.Material.Define(stage, mat_path)
                    shader = UsdShade.Shader.Define(stage, f"{mat_path}/PBRShader")
                    shader.CreateIdAttr("UsdPreviewSurface")
                    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color))
                    shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
                    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.5)
                    material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")

                    materials_cache[color_key] = material
                    stats["material_count"] += 1

                UsdShade.MaterialBindingAPI(mesh_prim).Bind(materials_cache[color_key])
                mesh_prim.GetPrim().SetCustomDataByKey("ifcGuid", str(guid))
                mesh_idx += 1

            stage.SetDefaultPrim(root.GetPrim())
            stage.Save()

            usdz_out = Path(usdz_path)
            usdz_out.parent.mkdir(parents=True, exist_ok=True)
            if usdz_out.exists():
                usdz_out.unlink()

            if not UsdUtils.CreateNewUsdzPackage(str(usdc_path), str(usdz_out)):
                return {"success": False, "error": "Failed to package USDZ"}

        processing_time = time.time() - start_time
        stats["processing_time"] = round(processing_time, 3)
        stats["usdz_size_bytes"] = Path(usdz_path).stat().st_size
        return {"success": True, "stats": stats}

    except Exception as exc:
        logger.exception("[glb_to_usdz_fast] Failed")
        return {"success": False, "error": str(exc)}
