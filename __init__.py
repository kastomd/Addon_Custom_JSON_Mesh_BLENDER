bl_info = {
    "name": "Custom JSON Mesh Suite (PART + TTT)",
    "author": "Kasto",
    "version": (2, 2, 1),
    "blender": (4, 0, 0),
    "location": "File > Import-Export",
    "description": "Import/Export PART y Subpart (TTT) JSON Mesh",
    "category": "Import-Export",
    "doc_url": "https://github.com/kastomd/Addon_Custom_JSON_Mesh_BLENDER/releases/latest",
}

import bpy
import bmesh
import json
import os
from pathlib import Path
from collections import defaultdict
from bpy.types import (
    Operator,
    Panel,
    PropertyGroup,
    Menu,
    OperatorFileListElement,
)
from bpy.props import (
    StringProperty,
    BoolProperty,
    CollectionProperty,
    FloatVectorProperty,
    IntProperty,
    PointerProperty,
)
from bpy_extras.io_utils import ImportHelper, ExportHelper
from . import gradient_weights


# =========================================================
# PROPIEDADES TTT
# =========================================================

class JSONMeshProperties(PropertyGroup):

    grosor: FloatVectorProperty(
        name="Grosor",
        size=3,
        default=(512.0, 512.0, 512.0)
    )

    unk: IntProperty(
        name="UNK",
        default=302007041
    )

# =========================================================
# PANEL TTT
# =========================================================

class OBJECT_PT_json_mesh_panel(Panel):
    bl_label = "JSON Mesh Data TTT"
    bl_idname = "OBJECT_PT_json_mesh_panel"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"

    def draw(self, context):
        obj = context.object
        if not obj:
            return

        layout = self.layout
        props = obj.json_mesh_props

        layout.prop(props, "grosor")
        layout.prop(props, "unk")

        layout.separator()
        layout.label(text="Weights Tools:")

        layout.operator("object.gradient_weights_auto", icon='MOD_VERTEX_WEIGHT')


# =========================================================
# EXPORT PART
# =========================================================

class EXPORT_OT_part_json(Operator, ExportHelper):
    bl_idname = "export_scene.part_json_mesh"
    bl_label = "Export PART JSON Mesh"
    bl_description = (
        "Exporta la malla activa al formato Part.\n"
        "Guarda uv (0-255), vertices, unk, influencias, faces."
    )

    filename_ext = ".json"

    directory: StringProperty(
        name="Output Directory",
        subtype='DIR_PATH'
    )

    def execute(self, context):

        selected = [o for o in context.selected_objects if o.type == 'MESH']

        if not selected:
            self.report({'ERROR'}, "Selecciona al menos un objeto MESH")
            return {'CANCELLED'}

        depsgraph = context.evaluated_depsgraph_get()

        for obj in selected:

            eval_obj = obj.evaluated_get(depsgraph)
            mesh = eval_obj.to_mesh()

            bm = bmesh.new()
            bm.from_mesh(mesh)
            bmesh.ops.triangulate(bm, faces=bm.faces)
            bm.to_mesh(mesh)
            bm.free()

            mesh.calc_loop_triangles()

            uv_layer = mesh.uv_layers.active.data if mesh.uv_layers.active else None

            id_bones = [vg.name for vg in obj.vertex_groups]

            vertices_json = []
            faces_json = []
            vertex_map = {}
            counter = 0

            for tri in mesh.loop_triangles:
                face_indices = []

                for loop_index in tri.loops:

                    loop = mesh.loops[loop_index]
                    vert = mesh.vertices[loop.vertex_index]

                    pos = [vert.co.x, vert.co.y, vert.co.z]

                    if uv_layer:
                        uv = uv_layer[loop_index].uv

                        # Flip vertical (equivalente a escala Y = -1)
                        u = uv.x
                        v = 1.0 - uv.y

                        uv_int = [int(u * 256), int(v * 256)]
                    else:
                        uv_int = [0, 0]

                    weights = ["N/A"] * len(id_bones)

                    for g in vert.groups:
                        name = obj.vertex_groups[g.group].name
                        idx = id_bones.index(name)
                        weights[idx] = float(g.weight)

                    key = (tuple(pos), tuple(uv_int), tuple(weights))

                    if key not in vertex_map:
                        vertex_map[key] = counter
                        vertices_json.append({
                            "id_v": str(counter),
                            "pos": pos,
                            "uv": uv_int,
                            "weights": weights
                        })
                        counter += 1

                    face_indices.append(vertex_map[key])

                faces_json.append(face_indices)

            id_bones_hex = []

            for name in id_bones:

                name = name.strip()

                if name.lower().startswith("0x"):
                    value = int(name, 16)
                else:
                    value = int(name)

                id_bones_hex.append(hex(value))

            data = {
                "type": "part",
                "id_bones": id_bones_hex,
                "vertices": vertices_json,
                "faces": faces_json
            }

            filepath = os.path.join(self.directory, obj.name + ".json")

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)

            eval_obj.to_mesh_clear()

        self.report({'INFO'}, f"Exportados {len(selected)} objetos")
        return {'FINISHED'}

# =========================================================
# EXPORT SUBPART (TTT)
# =========================================================

class EXPORT_OT_subpart_json(Operator, ExportHelper):
    bl_idname = "export_scene.subpart_json_mesh"
    bl_label = "Export Subpart JSON Mesh (TTT)"
    bl_options = {'REGISTER'}
    bl_description = (
        "Exporta la malla activa al formato Subpart.\n"
        "Guarda grosor, uv(0-255), vertices, unk, influencias."
    )

    filename_ext = ".json"
    filter_glob: StringProperty(
        default="*.json",
        options={'HIDDEN'}
    )

    ordenar_vertices: BoolProperty(
        name="Ordenar Vertices",
        description="Ordena los vértices antes de exportar\n(USAR SOLO SI ELIMINO, AGRUEGO O MOVIO VERTICES)",
        default=True
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "ordenar_vertices")

    def execute(self, context):
        obj = context.object

        if obj is None or obj.type != 'MESH':
            self.report({'ERROR'}, "Selecciona un objeto tipo MESH")
            return {'CANCELLED'}

        mesh = obj.data
        mesh.calc_loop_triangles()

        # -----------------------------
        # Copiar malla
        # -----------------------------
        mesh_copy = mesh.copy()
        if self.ordenar_vertices:
            # crear bmesh temporal en memoria
            bm = bmesh.new()
            bm.from_mesh(mesh_copy)

            # eliminar vértices duplicados
            bmesh.ops.remove_doubles(
                bm,
                verts=bm.verts,
                dist=0.00001
            )

            # escribir cambios en la copia
            bm.to_mesh(mesh_copy)

            # liberar bmesh
            bm.free()
        list_triangulos = self.obtener_indices_triangulos(mesh_copy) if self.ordenar_vertices else []

        # -----------------------------
        # Obtener strip
        # -----------------------------
        strip = self.find_strip(list_triangulos) if self.ordenar_vertices else []

        # -----------------------------
        # Obtener UV
        # -----------------------------
        uv_layer = mesh_copy.uv_layers.active
        uv_data = uv_layer.data if uv_layer else None

        # -----------------------------
        # Obtener id_bones desde vertex_groups
        # -----------------------------
        id_bones = []
        group_index_map = {}

        for vg in obj.vertex_groups:
            bone_id = vg.name if "0x" in vg.name.lower() else f"0x{int(vg.name):02X}"
            id_bones.append(bone_id)
            group_index_map[vg.index] = len(id_bones) - 1

        # -----------------------------
        # Construir vertices en orden STRIP
        # -----------------------------
        vertices_json = []

        iterable = strip if strip else range(len(mesh_copy.vertices))

        for new_index, original_index in enumerate(iterable):
            vert = mesh_copy.vertices[original_index]

            # Posición
            pos = [vert.co.x, vert.co.y, vert.co.z]

            # UV (primer loop que use ese vert)
            uv_final = [0, 0]
            if uv_data:
                for loop in mesh_copy.loops:
                    if loop.vertex_index == original_index:
                        uv = uv_data[loop.index].uv
                        u = int(round(uv.x * 256.0))
                        v = int(round((1.0 - uv.y) * 256.0))
                        uv_final = [u, v]
                        break

            # Pesos
            weights = ["N/A"] * len(id_bones)

            for g in vert.groups:
                if g.group in group_index_map:
                    idx = group_index_map[g.group]
                    weights[idx] = g.weight

            vertex_data = {
                "id_v": str(new_index),  # ahora es índice secuencial del strip
                "original_index": original_index,  # opcional, útil para debug
                "pos": pos,
                "uv": uv_final,
                "weights": weights
            }

            vertices_json.append(vertex_data)

        # -----------------------------
        # Construir JSON final
        # -----------------------------
        data = {
            "type": "subpart",
            "grosor": list(obj.json_mesh_props.grosor) if not self.ordenar_vertices else [512.0, 512.0, 512.0],
            "id_bones": id_bones,
            "unk": obj.json_mesh_props.unk,
            "vertices": vertices_json
        }

        # -----------------------------
        # Guardar archivo
        # -----------------------------
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

        self.report({'INFO'}, f"Exportado: {len(vertices_json)} vertices")
        return {'FINISHED'}
    
    def obtener_indices_triangulos(self, mesh):
        lista_triangulos = []

        for tri in mesh.loop_triangles:
            indices = list(tri.vertices)
            lista_triangulos.append(indices)

        return lista_triangulos

    
    """ Function to generate a (not guaranteed optimal) triangle strip out
    of a set of triangles.

    Triangle strips can be required in geometry shaders or other
    applications.

    The performance and runtime of this solution is not optimal, but it is
    sufficient for small enough problems.

    Authors: Corbinian Gruber <dev.gruco0002@gmail.com>

    License: The Unlicence

        This is free and unencumbered software released into the public domain.

        Anyone is free to copy, modify, publish, use, compile, sell, or
        distribute this software, either in source code form or as a compiled
        binary, for any purpose, commercial or non-commercial, and by any
        means.

        In jurisdictions that recognize copyright laws, the author or authors
        of this software dedicate any and all copyright interest in the
        software to the public domain. We make this dedication for the benefit
        of the public at large and to the detriment of our heirs and
        successors. We intend this dedication to be an overt act of
        relinquishment in perpetuity of all present and future rights to this
        software under copyright law.

        THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
        EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
        MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
        IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
        OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
        ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
        OTHER DEALINGS IN THE SOFTWARE.

        For more information, please refer to <https://unlicense.org>
"""

    def build_edge_map(self, triangles):
        edge_map = defaultdict(list)

        for i, (a, b, c) in enumerate(triangles):
            edges = [
                tuple(sorted((a, b))),
                tuple(sorted((b, c))),
                tuple(sorted((c, a)))
            ]
            for e in edges:
                edge_map[e].append(i)

        return edge_map

    def find_strip(self, triangles):
        triangles = [tuple(t) for t in triangles]
        edge_map = self.build_edge_map(triangles)

        used = [False] * len(triangles)
        result = []

        for start_idx in range(len(triangles)):
            if used[start_idx]:
                continue

            tri = triangles[start_idx]

            # iniciar strip
            strip = [tri[0], tri[1], tri[2]]
            used[start_idx] = True

            flip = False  # controla winding

            while True:
                if flip:
                    edge = (strip[-1], strip[-2])
                else:
                    edge = (strip[-2], strip[-1])

                edge_key = tuple(sorted(edge))
                candidates = edge_map[edge_key]

                found = False

                for idx in candidates:
                    if used[idx]:
                        continue

                    t = triangles[idx]
                    s = set(t)

                    if not s.issuperset(edge):
                        continue

                    new_v = next(iter(s - set(edge)))

                    # validar que realmente forma triángulo
                    a, b = edge
                    if len({a, b, new_v}) < 3:
                        continue  # degenerate real, evitar

                    strip.append(new_v)
                    used[idx] = True
                    flip = not flip
                    found = True
                    break

                if not found:
                    break

            # conectar strips con degenerates
            if not result:
                result.extend(strip)
            else:
                # degenerates: repetir último y primero
                result.append(result[-1])
                result.append(strip[0])
                result.extend(strip)

        return result


# =========================================================
# IMPORTADORES
# =========================================================

class IMPORT_OT_json_mesh(Operator, ImportHelper):
    bl_idname = "import_scene.subpart_json_mesh"
    bl_label = "Import JSON Mesh TTT"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = (
        "Importa la malla de formato Subpart."
    )

    filename_ext = ".json"
    filter_glob: StringProperty(
        default="*.json",
        options={'HIDDEN'}
    )

    # Permitir múltiples archivos
    files: CollectionProperty(type=OperatorFileListElement)

    def execute(self, context):

        for file_elem in self.files:

            base_dir = Path(self.filepath).parent
            filepath = base_dir / file_elem.name


            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data["type"] != "subpart":
                    raise ValueError("El archivo no es una subpart")

            vertices = data.get("vertices", []) if isinstance(data, dict) else data

            verts = []
            faces = []
            uv_coords = []

            # -----------------------------
            # Leer vertices y UV
            # -----------------------------
            for v in vertices:
                pos = v.get("pos")
                uv = v.get("uv")

                if pos and len(pos) == 3:
                    x, y, z = pos
                    verts.append((x, y, z))

                    if uv and len(uv) == 2:
                        u = uv[0] / 256.0
                        v_coord = 1.0 - (uv[1] / 256.0)
                        uv_coords.append((u, v_coord))
                    else:
                        uv_coords.append((0.0, 0.0))

            # -----------------------------
            # Generar caras (triangle strip)
            # -----------------------------
            for i in range(len(verts) - 2):
                if i % 2 == 0:
                    tri = (i, i+1, i+2)
                else:
                    tri = (i+1, i, i+2)

                if len(set(tri)) == 3:
                    faces.append(tri)

            # -----------------------------
            # Crear malla
            # -----------------------------
            mesh = bpy.data.meshes.new(filepath.stem)
            mesh.from_pydata(verts, [], faces)
            mesh.update()

            obj = bpy.data.objects.new(filepath.stem, mesh)
            context.collection.objects.link(obj)

            # -----------------------------
            # UVMap
            # -----------------------------
            if uv_coords:
                uv_layer = mesh.uv_layers.new(name="UVMap")
                uv_data = uv_layer.data

                for face in mesh.polygons:
                    for loop_index in face.loop_indices:
                        vert_index = mesh.loops[loop_index].vertex_index
                        uv_data[loop_index].uv = uv_coords[vert_index]

            # -----------------------------
            # Vertex Groups / Bones
            # -----------------------------
            id_bones = data.get("id_bones", [])
            groups = {}

            for bone_id in id_bones:
                name = bone_id if "0x" in bone_id.lower() else f"0x{(int(bone_id)):02X}"
                groups[bone_id] = obj.vertex_groups.new(name=name)

            for vert_index, v in enumerate(vertices):
                weights = v.get("weights", [])

                for i, w in enumerate(weights):
                    if w != "N/A" and w is not None:
                        bone_id = id_bones[i]
                        groups[bone_id].add([vert_index], float(w), 'REPLACE')

            # Propiedades personalizadas
            obj.json_mesh_props.grosor = tuple(data.get("grosor", [0, 0, 0]))
            obj.json_mesh_props.unk = data.get("unk", 0)

            self.report({'INFO'}, f"Importado: {filepath.name}")

        return {'FINISHED'}

class IMPORT_OT_custom_json(Operator, ImportHelper):
    bl_idname = "import_scene.part_json_mesh"
    bl_label = "Import PART JSON Mesh"
    bl_description = (
        "Importa la malla de formato Part."
    )

    filename_ext = ".json"

    filter_glob: StringProperty(
        default="*.json",
        options={'HIDDEN'}
    )

    # 🔹 Permitir selección múltiple
    files: CollectionProperty(
        type=OperatorFileListElement,
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    directory: StringProperty(
        subtype='DIR_PATH'
    )

    def execute(self, context):

        # Si no hay selección múltiple, usar filepath normal
        if not self.files:
            filepaths = [self.filepath]
        else:
            filepaths = [
                self.directory + file.name
                for file in self.files
            ]

        for path in filepaths:
            self.import_json(context, Path(path))

        self.report({'INFO'}, f"Importados {len(filepaths)} archivo(s)")
        return {'FINISHED'}

    # -----------------------------------------------------

    def import_json(self, context, filepath):

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            if data["type"] != "part":
                raise ValueError("El archivo no es tipo part")

        id_bones = data.get("id_bones", [])
        id_bones_hex = []

        for name in id_bones:
            name = name.strip()

            if name.lower().startswith("0x"):
                # ya es hexadecimal
                value = int(name, 16)
            else:
                # asumir decimal
                value = int(name)

            id_bones_hex.append(hex(value))
        id_bones = id_bones_hex

        vertices_data = data["vertices"]
        faces_data = data["faces"]

        mesh = bpy.data.meshes.new("ImportedMesh")
        obj = bpy.data.objects.new(filepath.stem, mesh)
        context.collection.objects.link(obj)

        verts = []

        for v in vertices_data:
            x, y, z = v["pos"]

            # Inversa de la transformación
            orig_x = x
            orig_y = y
            orig_z = z

            verts.append([orig_x, orig_y, orig_z])


        mesh.from_pydata(verts, [], faces_data)
        mesh.update()

        # 🔹 Crear vertex groups
        for bone_name in id_bones:
            obj.vertex_groups.new(name=bone_name)

        # 🔹 Asignar weights
        for i, v in enumerate(vertices_data):
            weights = v["weights"]

            for group_index, weight in enumerate(weights):
                if weight != "N/A":
                    obj.vertex_groups[group_index].add(
                        [i],
                        float(weight),
                        'REPLACE'
                    )

        # 🔹 UV
        if vertices_data and "uv" in vertices_data[0]:
            uv_layer = mesh.uv_layers.new(name="UVMap")

            for poly in mesh.polygons:
                for loop_index in poly.loop_indices:
                    vert_index = mesh.loops[loop_index].vertex_index
                    uv_raw = vertices_data[vert_index]["uv"]

                    uv_layer.data[loop_index].uv = (
                        uv_raw[0] / 256.0,
                        1 - (uv_raw[1] / 256.0)
                    )

# =========================================================
# SUBMENÚ
# =========================================================

class MENU_MT_json_mesh_import(Menu):
    bl_idname = "MENU_MT_json_mesh_import"
    bl_label = "Custom JSON Mesh"

    def draw(self, context):
        layout = self.layout
        layout.operator("import_scene.part_json_mesh")
        layout.operator("import_scene.subpart_json_mesh")

class MENU_MT_json_mesh_export(Menu):
    bl_idname = "MENU_MT_json_mesh_export"
    bl_label = "Custom JSON Mesh"

    def draw(self, context):
        layout = self.layout
        layout.operator("export_scene.part_json_mesh")
        layout.operator("export_scene.subpart_json_mesh")



# =========================================================
# REGISTRO
# =========================================================

classes = (
    JSONMeshProperties,
    OBJECT_PT_json_mesh_panel,
    EXPORT_OT_part_json,
    EXPORT_OT_subpart_json,

    IMPORT_OT_json_mesh,
    IMPORT_OT_custom_json,

    MENU_MT_json_mesh_import,
    MENU_MT_json_mesh_export,
)

def menu_import(self, context):
    self.layout.menu("MENU_MT_json_mesh_import")

def menu_export(self, context):
    self.layout.menu("MENU_MT_json_mesh_export")



def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    gradient_weights.register()

    bpy.types.Object.json_mesh_props = PointerProperty(type=JSONMeshProperties)

    bpy.types.TOPBAR_MT_file_import.append(menu_import)
    bpy.types.TOPBAR_MT_file_export.append(menu_export)

def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_import)
    bpy.types.TOPBAR_MT_file_export.remove(menu_export)

    del bpy.types.Object.json_mesh_props

    gradient_weights.unregister()

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
