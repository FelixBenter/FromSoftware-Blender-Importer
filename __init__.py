bl_info = {
    "name": "Import DCX model files",
    "description": "Import models from FROMSOFT games",
    "author": "Felix Benter",
    "version": (0, 0, 1),
    "blender": (2, 90, 1),
    "category": "Import-Export",
    "location": "File > Import",
    "warning": "",
    "support": "COMMUNITY",
    "wiki_url": "https://github.com/FelixBenter/DCX-Blender",
    "tracker_url": "https://github.com/FelixBenter/DCX-Blender/issues",
}

_submodules = {
    "importer",
    "bnd",
    "dcx",
    "utils",
}

if "bpy" in locals():
    import importlib
    for sm in _submodules:
        if sm in locals():
            importlib.reload(locals()[sm])
else:
    from .importer import run

import bpy
import gc
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, CollectionProperty, BoolProperty

class DcxImporter(bpy.types.Operator, ImportHelper):
    bl_idname = "import_scene.dcx"
    bl_label = "Compressed Fromsoft (.dcx, .bnd)"
    bl_options = {"REGISTER", "UNDO"}

    filter_glob = StringProperty(default="*.flver.dcx;*.mapbnd.dcx;*.chrbnd.dcx;*.bnd", options = {"HIDDEN"})

    get_textures = BoolProperty(name = "Import Textures (Not implemented yet)", default = False)
    unwrap_mesh = BoolProperty(name = "Unwrap UVs (Very slow on large models)", default = False)

    files: CollectionProperty(
            type=bpy.types.OperatorFileListElement,
            options={'HIDDEN', 'SKIP_SAVE'},
        )

    directory = StringProperty(subtype='DIR_PATH')
    
    def execute(self, context):
        for file in self.files:
            run(self.directory, file.name, self.get_textures, self.unwrap_mesh)
            gc.collect() # Probably not necessary, but just in case Blender keeps the plugin running for whatever reason
        return {"FINISHED"}
    
def menu_import(self, context):
    self.layout.operator(DcxImporter.bl_idname)

def register():
    bpy.utils.register_class(DcxImporter)
    bpy.types.TOPBAR_MT_file_import.append(menu_import)

def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_import)
    bpy.utils.unregister_class(DcxImporter)
