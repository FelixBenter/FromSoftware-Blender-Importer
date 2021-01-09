bl_info = {
    "name": "Import DCX model files",
    "description": "Import dcx files from FROMSOFT games",
    "author": "Felix Benter",
    "version": (0, 2, 0),
    "blender": (2, 80, 1),
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

import bpy, gc
from os.path import realpath, dirname
from shutil import copyfile
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, CollectionProperty, BoolProperty

class UnpackPathPreference(bpy.types.AddonPreferences):
    bl_idname = __name__

    unpack_path = StringProperty(
        default = "",
        description = "The path that textures & models will be unpacked to.\nPreferably an empty folder",
        subtype = "DIR_PATH")

    dll_path = StringProperty(
        default = "",
        description = "Path to the oo2core_6_win64.dll file.\nOnly necessary for Sekiro files.",
        subtype = "FILE_PATH")

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "unpack_path")
        layout.prop(self, "dll_path")

class DcxImporter(bpy.types.Operator, ImportHelper):
    bl_idname = "import_scene.dcx"
    bl_label = "Compressed Fromsoft (.dcx, .bnd)"
    bl_options = {"REGISTER", "UNDO"}

    filter_glob = StringProperty(
        default="*.chrbnd.dcx;*.mapbnd.dcx;*.flver.dcx;*.partsbnd.dcx;*.bnd", 
        options = {"HIDDEN"})
    get_textures = BoolProperty(
        name = "Import Textures (Only DS3 & Sekiro)", 
        default = False)
    clean_up_files = BoolProperty(
        name = "Clean up files after import", 
        default = True)
    import_rig = BoolProperty(
        name = "Import rig",
        default = False)
    files = CollectionProperty(
        type=bpy.types.OperatorFileListElement, 
        options={'HIDDEN', 'SKIP_SAVE'})
    directory = StringProperty(
        subtype='DIR_PATH')

    def execute(self, context):

        unpack_path = context.preferences.addons[__name__].preferences.unpack_path
        dll_path = context.preferences.addons[__name__].preferences.dll_path
        sys_path = dirname(realpath(__file__))
        if dll_path != "":
            copyfile(dll_path, f"{sys_path}\\Yabber\\oo2core_6_win64.dll")
        if unpack_path == "":
            raise Exception("Unpack path not set.\nSet it in the addon configuration.")
        
        for file in self.files:
            run(unpack_path, self.directory, file.name, self.get_textures, self.clean_up_files, self.import_rig)
            gc.collect() # Probably not necessary, but in case Blender keeps the plugin running for whatever reason
        return {"FINISHED"}
    
def menu_import(self, context):
    self.layout.operator(DcxImporter.bl_idname)

def register():
    bpy.utils.register_class(DcxImporter)
    bpy.types.TOPBAR_MT_file_import.append(menu_import)
    bpy.utils.register_class(UnpackPathPreference)

def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_import)
    bpy.utils.unregister_class(DcxImporter)
    bpy.utils.unregister_class(UnpackPathPreference)