# FromSoftware-Blender-Importer
A Blender plugin for importing FromSoftware files. Code based heavily from the [SoulsFormats](https://github.com/JKAnderson/SoulsFormats) and uses [Yabber](https://github.com/JKAnderson/Yabber) to unpack dcx files. Currently supports DS1, DS2, DS3 & Sekiro characters, partsbnds and DS1 & DS3 maps.

![](https://i.redd.it/rshisri0rg961.gif)

## Usage:
* In the add-on configuartion, set a path for the addon to unpack the dcx files to (Preferably an empty folder separate from the game directory).
* Set a path to, or move into the default path, the [Yabber](https://www.nexusmods.com/sekiro/mods/42/) tool.
* If you intend to use this for Sekiro files, also set the path to the "oo2core_6_win64.dll" file. (Located in steamapps/common/Sekiro/).

* File -> Import -> Compressed FromSoftware File
* Materials may need to be appended to their respective mesh if not automatically done so.
* Many bone weights will likely be broken for ds3 models.

## Import options:
* Import Textures: Will look for a texture file in the same directory with the same name as the model dcx file, then use [DirectXTex texconv](https://github.com/microsoft/DirectXTex) to extract png textures and create blender principled shader materials in the scene.
* Clean up files after import: Will delete all copied/extracted files (Except for texture files) from the unpack directory after importing.
* Import Rig: (Experimental) Will attempt to rig the model. Weights are currently not functional on DS2 or DS3 models.

## To Do:
* Fixing edge cases with certain flver files.
* More robust texture matching using master material file.