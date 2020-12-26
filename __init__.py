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
    "wiki_url": "",
    "tracker_url": "",
}

_submodules = {
    "importer",
    "bnd",
    "dcx",
    "utils",
    "magic",
}

if "bpy" in locals():
    import importlib
    for sm in _submodules:
        if sm in locals():
            importlib.reload(locals()[sm])
else:
    from .importer import run


import bpy
import os
import sys
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, BoolProperty

class DcxImporter(bpy.types.Operator, ImportHelper):
    bl_idname = "import_scene.dcx"
    bl_label = "Compressed Fromsoft (.dcx)"
    bl_options = {"REGISTER", "UNDO"}
    
    filter_glob = StringProperty(default="*.dcx", options={"HIDDEN"})

    getTextures = BoolProperty(name = "Import Textures", default = True)
    

    def execute(self, context):
        run(self.filepath, self.getTextures)
        return {"FINISHED"}
    
def menu_import(self, context):
    self.layout.operator(DcxImporter.bl_idname)

def register():
    bpy.utils.register_class(DcxImporter)
    bpy.types.TOPBAR_MT_file_import.append(menu_import)

def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_import)
    bpy.utils.unregister_class(DcxImporter)
