bl_info = {
    "name": "Custom JSON Mesh Suite (PART + TTT)",
    "author": "Kasto",
    "version": (2, 0, 0),
    "blender": (3, 0, 0),
    "location": "File > Import-Export",
    "description": "Import/Export PART y Subpart (TTT) JSON Mesh",
    "category": "Import-Export",
    "doc_url": "https://github.com/kastomd",
}

import bpy
import bmesh
import json
from pathlib import Path
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

# =========================================================
# EXPORT PART
# =========================================================

class EXPORT_OT_part_json(Operator, ExportHelper):
    bl_idname = "export_scene.part_json_mesh"
    bl_label = "Export PART JSON Mesh"
    bl_description = (
        "Exporta la malla activa al formato Part.\n"
        "Guarda las coordenadas, uv, faces y grupos de influencia."
    )

    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'})

    def execute(self, context):

        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "Selecciona un objeto MESH")
            return {'CANCELLED'}

        depsgraph = context.evaluated_depsgraph_get()
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

                pos = [vert.co.x, vert.co.z, -vert.co.y]

                if uv_layer:
                    uv = uv_layer[loop_index].uv
                    uv_int = [int(uv.x * 255), int(uv.y * 255)]
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

        data = {
            "type": "part",
            "id_bones": id_bones,
            "vertices": vertices_json,
            "faces": faces_json
        }

        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

        eval_obj.to_mesh_clear()
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
        "Convierte UV al formato TTT."
    )

    filename_ext = ".json"
    filter_glob: StringProperty(
        default="*.json",
        options={'HIDDEN'}
    )

    ordenar_vertices: BoolProperty(
        name="Ordenar Vertices",
        description="Ordena los vértices antes de exportar\n(USAR SOLO SI ELIMINO O AGRUEGO VERTICES)",
        default=False
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
        # Copiar malla y aplicar rotación inversa
        # -----------------------------
        mesh_copy = mesh.copy()
        list_triangulos = self.obtener_indices_triangulos(mesh_copy) if self.ordenar_vertices else []
        
        for v in mesh_copy.vertices:
            x = v.co.x
            y = v.co.y
            z = v.co.z

            v.co.x = x
            v.co.y = z
            v.co.z = -y

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
            bone_id = "0x" + vg.name
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
                        u = int(round(uv.x * 255.0))
                        v = int(round((1.0 - uv.y) * 255.0))
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
            "grosor": list(obj.json_mesh_props.grosor),
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


    def find_strip(self, triangles):
        """ Finds a triangle strip representation for a given set of triangle
            faces.

        Args:
            triangles (list of triangles): A list of triangles. A triangle is
                represented by a list or tuple of 3 elements. The order of those
                elements does not matter. The elements should be comparable and
                should be able to be an element of a set.

        Returns:
            List of elements: A list consisting of the triangle elements that form
            a triangle strip covering all triangles at least once.
        """

        def find_strip_internal(current_strip, used_triangles, max_triangle_usage):

            # check if we covered all triangles by now
            unused_triangles_existing = False
            for i in range(len(triangles)):
                if used_triangles[i] == 0:
                    unused_triangles_existing = True
                    break

            # if we covered all triangles, we found a solution and return it
            if not unused_triangles_existing:
                return current_strip

            if len(current_strip) == 0:
                # initial state, iterate over all triangles and use each one as
                # the starting point for the recursive algorithm.
                for i, triangle in enumerate(triangles):
                    # mark the triangle as used triangle (used once)
                    used_triangles[i] = 1

                    # Each permutation of the first triangles vertices have to
                    # be tested, since their order matters.

                    # add the triangles elements (vertices) to the current triangle
                    # strip and recursively find adjacent triangles
                    current_strip += [triangle[0], triangle[1], triangle[2]]
                    result = find_strip_internal(
                        current_strip, used_triangles, max_triangle_usage)

                    # if the result of that search is not none, we found a solution
                    # hence return the solution
                    if result is not None:
                        return result
                    # otherwise undo our changes to the current triangle strip
                    current_strip = current_strip[:-3]

                    # and repeat the same for all other permutations
                    current_strip += [triangle[0], triangle[2], triangle[1]]
                    result = find_strip_internal(
                        current_strip, used_triangles, max_triangle_usage)
                    if result is not None:
                        return result
                    current_strip = current_strip[:-3]

                    current_strip += [triangle[1], triangle[0], triangle[2]]
                    result = find_strip_internal(
                        current_strip, used_triangles, max_triangle_usage)
                    if result is not None:
                        return result
                    current_strip = current_strip[:-3]

                    current_strip += [triangle[1], triangle[2], triangle[0]]
                    result = find_strip_internal(
                        current_strip, used_triangles, max_triangle_usage)
                    if result is not None:
                        return result
                    current_strip = current_strip[:-3]

                    current_strip += [triangle[2], triangle[0], triangle[1]]
                    result = find_strip_internal(
                        current_strip, used_triangles, max_triangle_usage)
                    if result is not None:
                        return result
                    current_strip = current_strip[:-3]

                    current_strip += [triangle[2], triangle[1], triangle[0]]
                    result = find_strip_internal(
                        current_strip, used_triangles, max_triangle_usage)
                    if result is not None:
                        return result
                    current_strip = current_strip[:-3]

                    # if we checked all permutations of the current triangle and
                    # none was successfull, reset the usage of the triangle and
                    # try the next one
                    used_triangles[i] = 0
            else:
                # non initial state
                # checking each triangle if it can be used to extend the current
                # triangle strip. Therefore the triangles strip last two vertices
                # have to be part of the triangle
                for i, triangle in enumerate(triangles):

                    # check if the triangle is already covered the maximum allowed
                    # amount, if this is true, we cannot use it again for the
                    # solution
                    if used_triangles[i] >= max_triangle_usage:
                        continue

                    # check if the last two vertices of the current strip are part
                    # of the current triangle
                    triangle_as_set = set(triangle)
                    part_of_triangle = {current_strip[-1], current_strip[-2]}
                    if not triangle_as_set.issuperset(part_of_triangle):
                        # triangle does not share two of the same vertices, hence
                        # we cannot use it
                        continue

                    # get the vertex that was not part of the triangle strip
                    triangle_vertex = list(
                        triangle_as_set.difference(part_of_triangle))[0]

                    # increase the usage of the current triangle and append its
                    # vertex to the current strip
                    used_triangles[i] += 1
                    current_strip.append(triangle_vertex)

                    # now check recursively for a solution
                    result = find_strip_internal(
                        current_strip, used_triangles, max_triangle_usage)
                    # if a solution was found, we return it
                    if result is not None:
                        return result

                    # otherwise remove the current triangle from the strip and
                    # reduce its usage counter and continue with the next one.
                    current_strip.pop()
                    used_triangles[i] -= 1

            # if we reached here, we did not find a solution an thus return None
            return None

        # since it is possible that some triangles have to be covered twice by the
        # triangle strip in order to allow for a solution to exist, we increase the
        # allowed triangle usage / coverage until we find a solution
        usage = 1
        result = None

        # we repeat the search until we found a solution
        while result is None:
            # initialize the used / covered triangle count and set it to zero for
            # every triangle
            tmp_used_triangles = dict()
            for i in range(len(triangles)):
                tmp_used_triangles[i] = 0

            # we start out with an empty triangle strip
            tmp_triangle_strip = []
            # call our function to find a triangle strip for the given constraints
            result = find_strip_internal(
                tmp_triangle_strip, tmp_used_triangles, usage)

            # increase the allowed usage for the next check
            usage += 1

        # return the found solution
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
                    verts.append((x, -z, y))

                    if uv and len(uv) == 2:
                        u = uv[0] / 255.0
                        v_coord = 1.0 - (uv[1] / 255.0)
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
                name = bone_id.replace("0x", "")
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
            self.import_json(context, path)

        self.report({'INFO'}, f"Importados {len(filepaths)} archivo(s)")
        return {'FINISHED'}

    # -----------------------------------------------------

    def import_json(self, context, filepath):

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            if data["type"] != "part":
                raise ValueError("El archivo no es tipo part")

        id_bones = data.get("id_bones", [])
        vertices_data = data["vertices"]
        faces_data = data["faces"]

        mesh = bpy.data.meshes.new("ImportedMesh")
        obj = bpy.data.objects.new("ImportedObject", mesh)
        context.collection.objects.link(obj)

        verts = []

        for v in vertices_data:
            x, y, z = v["pos"]

            # Inversa de la transformación
            orig_x = x
            orig_y = -z
            orig_z = y

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
                        uv_raw[0] / 255.0,
                        uv_raw[1] / 255.0
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

    bpy.types.Object.json_mesh_props = PointerProperty(type=JSONMeshProperties)

    bpy.types.TOPBAR_MT_file_import.append(menu_import)
    bpy.types.TOPBAR_MT_file_export.append(menu_export)

def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_import)
    bpy.types.TOPBAR_MT_file_export.remove(menu_export)

    del bpy.types.Object.json_mesh_props

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
