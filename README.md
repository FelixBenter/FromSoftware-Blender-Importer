# DCX-Blender
A Blender plugin for importing Fromsoft DCX files. Code based heavily from the [SoulsFormats](https://github.com/JKAnderson/SoulsFormats) and uses [Yabber](https://github.com/JKAnderson/Yabber) to unpack dcx files. Currently supports DS1, DS2, DS3 & Sekiro characters and DS1 & DS3 maps.


![](https://i.redd.it/rshisri0rg961.gif)

## Usage:
* Set the path to unpack files to in the addon configuration.
* If you intend to use this for Sekiro files, also set the path to the "oo2core_6_win64.dll" file in steamapps/common/Sekiro/.
* Set a path for the addon to unpack the dcx files to (Preferably an empty folder).
* File -> Import -> Compressed Fromsoftware
* Some materials may need to be appended to their respective mesh if not automatically done so.

## Import options:
* Import Textures: Will look for a texture file in the same directory with the same name as the model dcx file, then use [DirectXTex texconv](https://github.com/microsoft/DirectXTex) to extract png textures and create blender principled shader materials in the scene.
* Clean up files after import: Will delete all copied/extracted files (Except for texture files) from the unpack directory after importing.

## To Do:
* Rigging Support
* Fixing edge cases with certain flver files.
* DS1 & DS2 texture support
* More robust texture matching
