import bpy
import re

"""
Direcciones gradiente 0-1:
"LEFT_RIGHT"   X+ → X-
"RIGHT_LEFT"   X- → X+
"BOTTOM_TOP"   Z- → Z+
"TOP_BOTTOM"   Z+ → Z-
"ALL_ZERO": 0
"ALL_ONE": 1
"""

# Mapeo HEX → dirección
HEX_DIRECTION_MAP = {
    # pierna izquierda
    0x08: "LEFT_RIGHT",
    0x09: "TOP_BOTTOM",
    0x0a: "TOP_BOTTOM",
    0x0b: "TOP_BOTTOM",
    # pelvis
    0x03: "ALL_ZERO",
    # pierna derecha
    0x0c: "RIGHT_LEFT",
    0x0d: "TOP_BOTTOM",
    0x0e: "TOP_BOTTOM",
    0x0f: "TOP_BOTTOM",
    # torso, cadera, pecho
    0x10: "BOTTOM_TOP",
    0x11: "BOTTOM_TOP",
    0x12: "LEFT_RIGHT",
    0x20: "RIGHT_LEFT",
    # brazo izquierdo
    0x13: "LEFT_RIGHT",
    0x14: "LEFT_RIGHT",
    0x15: "LEFT_RIGHT",
    # brazo derecho
    0x21: "RIGHT_LEFT",
    0x22: "RIGHT_LEFT",
    0x23: "RIGHT_LEFT",
    # cabeza
    0x2e: "TOP_BOTTOM",
    0x30: "ALL_ONE",
    0x2f: "ALL_ONE",
    # mano derecha
    0x16: "LEFT_RIGHT",
    0x17: "LEFT_RIGHT",
    0x18: "LEFT_RIGHT",
    0x19: "LEFT_RIGHT",
    0x1a: "LEFT_RIGHT",
    0x1b: "LEFT_RIGHT",
    0x1c: "LEFT_RIGHT",
    0x1d: "LEFT_RIGHT",
    0x1e: "LEFT_RIGHT",
    # mano izquierda
    0x24: "RIGHT_LEFT",
    0x25: "RIGHT_LEFT",
    0x26: "RIGHT_LEFT",
    0x27: "RIGHT_LEFT",
    0x28: "RIGHT_LEFT",
    0x29: "RIGHT_LEFT",
    0x2a: "RIGHT_LEFT",
    0x2b: "RIGHT_LEFT",
    0x2c: "RIGHT_LEFT",
}


def get_hex_from_name(name: str):
    """
    Extrae el valor hex después de "_" en el nombre
    Ej: "mesh_0B" → 0x0B
    """
    match = re.search(r'_([0-9A-Fa-f]{2})$', name)
    if match:
        return int(match.group(1), 16)
    return None



class OBJECT_OT_gradient_weights(bpy.types.Operator):
    bl_idname = "object.gradient_weights_auto"
    bl_label = "Apply Gradient Weights (Auto)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):

        for obj in context.selected_objects:

            if obj.type != 'MESH':
                continue

            mesh = obj.data

            hex_value = get_hex_from_name(obj.name)

            if hex_value is None:
                self.report({'WARNING'}, f"{obj.name} sin hex válido")
                continue

            if hex_value not in HEX_DIRECTION_MAP:
                self.report({'WARNING'}, f"{obj.name} hex no mapeado")
                continue

            direction = HEX_DIRECTION_MAP[hex_value]

            # nombre del vertex group esperado (ej: "0x0B")
            vg_name = f"0x{hex_value:02X}"
            vg = obj.vertex_groups.get(vg_name)

            if vg is None:
                vg = obj.vertex_groups.new(name=vg_name)


            # elegir eje
            if direction in {"LEFT_RIGHT", "RIGHT_LEFT"}:
                coords = [v.co.x for v in mesh.vertices]
            else:
                coords = [v.co.z for v in mesh.vertices]

            cmin = min(coords)
            cmax = max(coords)
            size = cmax - cmin if cmax != cmin else 1.0

            for v in mesh.vertices:

                if direction == "ALL_ONE":
                    weight = 1.0

                elif direction == "ALL_ZERO":
                    weight = 0.0

                else:
                    if direction in {"LEFT_RIGHT", "RIGHT_LEFT"}:
                        val = (v.co.x - cmin) / size
                    else:
                        val = (v.co.z - cmin) / size

                    if direction in {"RIGHT_LEFT", "TOP_BOTTOM"}:
                        val = 1.0 - val

                    weight = int(val * 10) / 10

                vg.add([v.index], weight, 'REPLACE')


        return {'FINISHED'}


class VIEW3D_PT_gradient_weights(bpy.types.Panel):
    bl_label = "Gradient Weights"
    bl_idname = "VIEW3D_PT_gradient_weights"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Tools"

    def draw(self, context):
        layout = self.layout
        layout.operator("object.gradient_weights_auto", text="Auto Gradient (by HEX)")


classes = (
    OBJECT_OT_gradient_weights,
    #VIEW3D_PT_gradient_weights,
)


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
