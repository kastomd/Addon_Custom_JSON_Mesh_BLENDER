# Custom JSON Mesh Suite (PART + TTT)

Blender Addon for importing and exporting custom JSON mesh formats used in PART and Subpart (TTT) pipelines.

Supports:
- `type: "part"`
- `type: "subpart"` (Tenkaichi Tag Team format)

---

## ✨ Features

### PART Format
- Triangulates mesh automatically
- Exports faces explicitly
- Axis conversion: `(x, y, z) → (x, z, -y)`
- UV conversion to 0–255 integer range
- Vertex Groups exported as `id_bones`
- Weights aligned with `id_bones` order

### Subpart (TTT) Format
- Optional triangle strip ordering
- Sequential vertex export
- UV conversion to 0–255
- Vertex Groups exported as hex bone IDs
- Includes custom properties:
  - `grosor`
  - `unk`

---

## 📦 Installation

1. Download the `.py` file.
2. Open Blender.
3. Go to: Edit > Preferences > Add-ons
4. Click **Install...**
5. Select the addon file.
6. Enable the addon.

---

## 📂 Menu Location

File

Import
* Custom JSON Mesh
  * Import PART JSON Mesh
  * Import Subpart JSON Mesh

Export
* Custom JSON Mesh
  * Export PART JSON Mesh
  * Export Subpart JSON Mesh

## 🧬 JSON Structure

### PART Example

```json
{
    "type": "part",
    "id_bones": ["bone1", "bone2"],
    "vertices": [
        {
            "id_v": "0",
            "pos": [0.0, 1.0, 2.0],
            "uv": [128, 200],
            "weights": [1.0, "N/A"]
        }
    ],
    "faces": [
        [0, 1, 2]
    ]
}
```
### Subpart Example

```json
{
    "type": "subpart",
    "grosor": [512.0, 512.0, 512.0],
    "unk": 302007041,
    "id_bones": ["0x01", "0x02"],
    "vertices": [
        {
            "id_v": "0",
            "pos": [0.0, 1.0, 2.0],
            "uv": [128, 200],
            "weights": [1.0, "N/A"]
        }
    ]
}
