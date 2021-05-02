bl_info = {
    "name": "FromSoftware-Blender-Importer",
    "description": "Import various model files from FromSoftware games",
    "author": "Felix Benter",
    "version": (0, 3, 1),
    "blender": (2, 92, 0),
    "category": "Import-Export",
    "location": "File > Import",
    "warning": "",
    "support": "COMMUNITY",
    "wiki_url": "https://github.com/FelixBenter/FromSoftware-Blender-Importer",
    "tracker_url": "https://github.com/FelixBenter/FromSoftware-Blender-Importer/issues",
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
    from .importer import import_mesh

import bpy, gc
from os.path import realpath, dirname, join, isfile
from shutil import copyfile
from bpy_extras.io_utils import ImportHelper
from pathlib import Path
from bpy.props import StringProperty, CollectionProperty, BoolProperty

class DCXBLENDER_PT_preferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    unpack_path = StringProperty(
        default = "",
        description = "REQUIRED: The path that textures & models will be unpacked to.\nPreferably an empty folder",
        subtype = "DIR_PATH")

    yabber_path = StringProperty(
        default = join(dirname(realpath(__file__)), 'Yabber'),
        description = "REQUIRED: The path to the Yabber tool directory.\
            \nYabber can be downloaded from https://www.nexusmods.com/sekiro/mods/42/\
            \nPlace Yabber.exe and all adjacent files in this directory",
        subtype = "DIR_PATH")

    dll_path = StringProperty(
        default = "",
        description = "OPTIONAL: Path to the oo2core_6_win64.dll file.\nOnly necessary for Sekiro files",
        subtype = "FILE_PATH")

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "unpack_path")
        layout.prop(self, "yabber_path")
        layout.prop(self, "dll_path")

        has_set_unpack = (context.preferences.addons[__name__].preferences.unpack_path != "")
        has_yabber_installed = isfile(Path(join(context.preferences.addons[__name__].preferences.yabber_path, 'Yabber.exe')))

        if not has_set_unpack:
            layout.label(text="Missing unpack path, set it above", icon="ERROR")
        if not has_yabber_installed:
            layout.label(text="Missing yabber.exe, download and point to location above.")
            layout.row().operator(
                "wm.url_open",
                icon="LINKED",
                text="Download Yabber from nexus").url = "https://www.nexusmods.com/sekiro/mods/42/"

class DCXBLENDER_PT_importer(bpy.types.Operator, ImportHelper):
    bl_idname = "import_scene.dcx"
    bl_label = "Compressed FromSoftware File (.dcx, .bnd)"
    bl_options = {"REGISTER", "UNDO"}

    filter_glob = StringProperty(
        default="*.chrbnd.dcx;*.mapbnd.dcx;*.flver.dcx;*.partsbnd.dcx;*.bnd;*.objbnd.dcx", 
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
        unpack_path = Path(context.preferences.addons[__name__].preferences.unpack_path)
        yabber_path = Path(context.preferences.addons[__name__].preferences.yabber_path)
        dll_path = (context.preferences.addons[__name__].preferences.dll_path)
        sys_path = Path(dirname(realpath(__file__)))

        if dll_path != "":
            copyfile(Path(dll_path), yabber_path / "oo2core_6_win64.dll")
        else:
            print("No oo2core_6_win64.dll file found, Sekiro files will not work.")
        if unpack_path == "":
            raise Exception("Unpack path not set.\nSet it in the addon configuration.")
        
        for file in self.files:
            import_mesh(
                path = Path(self.directory),
                file_name = file.name,
                unpack_path = unpack_path,
                yabber_path = yabber_path,
                get_textures = self.get_textures,
                clean_up_files = self.clean_up_files,
                import_rig = self.import_rig)
            gc.collect() # Probably not necessary, but in case Blender keeps the plugin running for whatever reason
        return {"FINISHED"}
    
def menu_import(self, context):
    self.layout.operator(DCXBLENDER_PT_importer.bl_idname)

def register():
    bpy.utils.register_class(DCXBLENDER_PT_importer)
    bpy.types.TOPBAR_MT_file_import.append(menu_import)
    bpy.utils.register_class(DCXBLENDER_PT_preferences)

def unregister():
    bpy.utils.unregister_class(DCXBLENDER_PT_preferences)
    bpy.types.TOPBAR_MT_file_import.remove(menu_import)
    bpy.utils.unregister_class(DCXBLENDER_PT_importer)