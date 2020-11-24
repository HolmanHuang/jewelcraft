# ##### BEGIN GPL LICENSE BLOCK #####
#
#  JewelCraft jewelry design toolkit for Blender.
#  Copyright (C) 2015-2020  Mikhail Rachinskiy
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# ##### END GPL LICENSE BLOCK #####


from typing import Sequence, List, Optional, Iterable

import bpy
from bpy.types import Object
import bmesh
from bmesh.types import BMesh, BMVert, BMEdge
from mathutils import Matrix, Vector

from .iterutils import pairwise_cyclic, quadwise_cyclic


# Primitives
# ---------------------------


def make_rect(bm: BMesh, x: float, y: float, z: float) -> List[BMVert]:
    return [
        bm.verts.new(co)
        for co in (
            ( x,  y, z),
            (-x,  y, z),
            (-x, -y, z),
            ( x, -y, z),
        )
    ]


def make_tri(bm: BMesh, x: float, y: float, z: float) -> List[BMVert]:
    return [
        bm.verts.new(co)
        for co in (
            (  x,  y / 3.0, z),
            ( -x,  y / 3.0, z),
            (0.0, -y / 1.5, z),
        )
    ]


# Tools
# ---------------------------


def est_volume(obs: Iterable[Object]) -> float:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    bm = bmesh.new()

    for ob in obs:
        ob_eval = ob.evaluated_get(depsgraph)
        me = ob_eval.to_mesh()
        me.transform(ob.matrix_world)

        bm.from_mesh(me)

        ob_eval.to_mesh_clear()

    bmesh.ops.triangulate(bm, faces=bm.faces, quad_method="SHORT_EDGE")

    vol = bm.calc_volume()
    bm.free()

    return vol


def est_curve_length(ob: Object) -> float:
    if ob.modifiers:

        # Reset curve
        # ---------------------------

        settings = {
            "bevel_object": None,
            "bevel_depth": 0.0,
            "extrude": 0.0,
        }

        for k, v in settings.items():
            x = getattr(ob.data, k)
            setattr(ob.data, k, v)
            settings[k] = x

        # Calculate length
        # ---------------------------

        depsgraph = bpy.context.evaluated_depsgraph_get()
        ob_eval = ob.evaluated_get(depsgraph)
        me = ob_eval.to_mesh()
        me.transform(ob.matrix_world)

        bm = bmesh.new()
        bm.from_mesh(me)

        ob_eval.to_mesh_clear()

        length = 0.0

        for edge in bm.edges:
            length += edge.calc_length()

        bm.free()

        # Restore curve
        # ---------------------------

        for k, v in settings.items():
            setattr(ob.data, k, v)

    else:

        curve = ob.data.copy()
        curve.transform(ob.matrix_world)

        length = 0.0

        for spline in curve.splines:
            length += spline.calc_length()

        bpy.data.curves.remove(curve)

    return length


def make_edges(bm: BMesh, verts: Iterable[BMVert]) -> List[BMEdge]:
    return [bm.edges.new(x) for x in pairwise_cyclic(verts)]


def bridge_verts(bm: BMesh, v1: Iterable[BMVert], v2: Iterable[BMVert]) -> dict:
    faces = [bm.faces.new(x) for x in quadwise_cyclic(v1, v2)]
    edges = [f.edges[1] for f in faces]

    return {"faces": faces, "edges": edges}


def duplicate_verts(bm: BMesh, verts: Sequence[BMVert], z: Optional[float] = None) -> List[BMVert]:
    dup = bmesh.ops.duplicate(bm, geom=verts)
    verts = [x for x in dup["geom"] if isinstance(x, bmesh.types.BMVert)]

    if z is not None:
        for v in verts:
            v.co.z = z

    return verts


def duplicate_edges(bm: BMesh, edges: Sequence[BMEdge], z: Optional[float] = None) -> List[BMEdge]:
    dup = bmesh.ops.duplicate(bm, geom=edges)
    edges = [x for x in dup["geom"] if isinstance(x, bmesh.types.BMEdge)]

    if z is not None:
        for v in dup["geom"]:
            if isinstance(v, bmesh.types.BMVert):
                v.co.z = z

    return edges


def edge_loop_expand(e: BMEdge, limit: int = 0) -> List[BMEdge]:
    edges = []
    app = edges.append

    loop = e.link_loops[0]
    loop_next = loop
    loop_prev = loop
    app(e)

    for _ in range(1, limit):
        loop_next = loop_next.link_loop_next.link_loop_radial_next.link_loop_next
        loop_prev = loop_prev.link_loop_prev.link_loop_radial_prev.link_loop_prev
        app(loop_next.edge)
        app(loop_prev.edge)

    return edges


def edge_loop_walk(verts: Sequence[BMVert]) -> List[Vector]:
    v = verts[0]
    e = v.link_edges[1]

    coords = []
    app = coords.append
    app(v.co.copy())

    for _ in range(len(verts) - 1):

        ov = e.other_vert(v)
        app(ov.co.copy())
        v = ov

        for oe in ov.link_edges:
            if oe != e:
                e = oe
                break

    return coords


def face_pos() -> List[Matrix]:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    mats = []

    for ob in bpy.context.objects_in_mode:
        ob.update_from_editmode()
        depsgraph.update()

        ob_eval = ob.evaluated_get(depsgraph)
        me = ob_eval.to_mesh()
        me.transform(ob.matrix_world)

        for poly in me.polygons:
            if poly.select:
                mat_loc = Matrix.Translation(poly.center)
                mat_rot = poly.normal.to_track_quat("Z", "Y").to_matrix().to_4x4()
                mat = mat_loc @ mat_rot

                mats.append(mat)

        ob_eval.to_mesh_clear()

    return mats
