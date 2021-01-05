

from os import remove, listdir
from os.path import isfile, join
import bpy
import bmesh
from .dcx import DCX
from .bnd import BND3, BND4
from .flver_utils import read_flver
from .tpf import TPF, convert_to_png
from bpy.app.translations import pgettext
from mathutils import Matrix, Vector
from enum import Enum
from random import random

class Mode(Enum):
    CHR = 1 # Must be unpacked from dcx and a rig applied
    DS2_CHR = 2 # Already unpacked from dcx, rig must be applied
    DS1_MAP = 3 # Must be unpacked from dcx, no rig
    DS3_MAP = 4 # Must be unpacked from dcx, no rig



def run(unpack_path, path, name, get_textures, unwrap_mesh):
        
        print("Importing {} from {}".format(name, str(path)))

        if name.endswith(".chrbnd.dcx"): # DS1 & 3 Character files
            name = name[:-11]
            game_mode = Mode.CHR
        elif name.endswith(".mapbnd.dcx"): # DS3 Map
            name = name[:-11]
            game_mode = Mode.DS3_MAP
        elif name.endswith(".flver.dcx"): # DS1 Map
            name = name[:-10]
            game_mode = Mode.DS1_MAP
        elif name.endswith(".bnd"): # DS2 Character files
            name = name[:-4]
            game_mode = Mode.DS2_CHR
        else:
            raise TypeError("Unsupported DCX type")
        
        import_mesh(unpack_path, path, name, get_textures, unwrap_mesh, game_mode)


def import_mesh(unpack_path, path, name, get_textures, unwrap_mesh, game_mode):

    if game_mode == Mode.CHR:
        DCXFile = DCX(path + name + ".chrbnd.dcx", None)
        magic = DCXFile.data[:4]
        map(ord, magic)
        magic = magic.decode("utf-8")
        if (magic == 'BND4'):             # CHR game_mode can be from DS1 or DS3, 
            BNDFile = BND4(DCXFile.data)  # so have to check which BND version.
        elif (magic == 'BND3'):
            BNDFile = BND3(DCXFile.data)
        else:
            raise Exception("File must be in BND4 or BND3 format")
        BNDFile.write_unpacked_dir(unpack_path)
        flver_path = unpack_path + "\\.unpacked\\" + name + ".flver"


    elif game_mode == Mode.DS3_MAP:
        DCXFile = DCX(path + name + ".mapbnd.dcx", None)
        BNDFile = BND4(DCXFile.data)
        BNDFile.write_unpacked_dir(unpack_path)
        flver_path = unpack_path + "\\.unpacked\\" + name + ".flver"
    
    elif game_mode == Mode.DS1_MAP:
        DCXFile = DCX(path + name + ".flver.dcx", None)
        DCXFile.write_unpacked(unpack_path + name + ".flver")
        flver_path = unpack_path + name + ".flver"

    elif game_mode == Mode.DS2_CHR:
        BNDFile = BND4(path + name + ".bnd")
        BNDFile.write_unpacked_dir(unpack_path)
        flver_path = unpack_path + "\\" + name + ".bnd.unpacked\\" + name + ".flv"
    
    elif game_mode == Mode.DS2_MAP:
        DCXFile = DCX(path, None)
        BNDFile = BND4(DCXFile.data)
        BNDFile.write_unpacked_dir(unpack_path)
        flver_path = unpack_path + ".unpacked\\" + name + ".flver"
        
    else:
        raise Exception("Unsupported game/file type")

    import_rig = False # Replace with proper usage once rigging is fixed

    flver_data = read_flver(flver_path)
    inflated_meshes = flver_data.inflate()

    collection = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(collection)
    
    # Create armature
    if import_rig:
        armature = create_armature(name, collection, flver_data)

    materials = []

    if get_textures:
        texture_path = import_textures(path, name, unpack_path)
        files = [f for f in listdir(texture_path) if isfile(join(texture_path, f))]
        for file in files:
            if "_a" in file:
                base_name = file[:-6]
                materials.append(create_material(texture_path, base_name))


    for index, (flver_mesh, inflated_mesh) in enumerate(
            zip(flver_data.meshes, inflated_meshes)):
        if inflated_mesh is None:
            continue

        # Construct mesh
        material_name = flver_data.materials[flver_mesh.material_index].name
        verts = [
            Vector((v[0], v[2], v[1]))
            for v in inflated_mesh.vertices.positions
        ]
        
        if material_name.endswith("_cloth"):
            material_name = material_name[:-6] # _cloth used for physics items

        mesh_name = f"{name}.{index}.{material_name}"
        mesh = bpy.data.meshes.new(name=mesh_name)
        mesh.from_pydata(verts, [], inflated_mesh.faces)

        # Create object and append it to the current collection
        obj = bpy.data.objects.new(mesh_name, mesh)
        collection.objects.link(obj)

        # Assign armature to object
        if import_rig:
            obj.modifiers.new(type="ARMATURE",
                              name=pgettext("Armature")).object = armature
            obj.parent = armature

        # Assign materials to object
        # Materials usually match the name of the object they are part of, but not always.
        # Should be replaced with a more robust method
        for material in materials:
            if material.name.lower().endswith(material_name.lower()):
                obj.data.materials.append(material)

        # Create vertex groups for bones
        for bone_index in flver_mesh.bone_indices:
            obj.vertex_groups.new(name=flver_data.bones[bone_index].name)

        bm = bmesh.new()
        bm.from_mesh(mesh)

        if unwrap_mesh:
            uv_layer = bm.loops.layers.uv.new()
            for face in bm.faces:
                for loop in face.loops:
                    u, v = inflated_mesh.vertices.uv[loop.vert.index] # Currently none types on DS3 models
                    loop[uv_layer].uv = (u, 1.0 - v)
                face.smooth = True
        if import_rig:
            weight_layer = bm.verts.layers.deform.new()
            for vert in bm.verts:
                weights = inflated_mesh.vertices.bone_weights[vert.index]
                indices = inflated_mesh.vertices.bone_indices[vert.index]
                for index, weight in zip(indices, weights):
                    if weight == 0.0:
                        continue
                    vert[weight_layer][index] = weight
        
        bm.to_mesh(mesh)
        bm.free()
        mesh.update()        
        
def create_armature(name, collection, flver_data):
    armature = bpy.data.objects.new(name, bpy.data.armatures.new(name))
    collection.objects.link(armature)
    armature.data.display_type = "STICK"
    
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.editmode_toggle() 

    root_bones = []
    for f_bone in flver_data.bones:
        bone = armature.data.edit_bones.new(f_bone.name)
        if f_bone.parent_index < 0:
            root_bones.append(bone)
    
    def transform_bone_and_siblings(bone_index, parent_matrix):
        while bone_index != -1:
            flver_bone = flver_data.bones[bone_index]
            bone = armature.data.edit_bones[bone_index]
            if flver_bone.parent_index >= 0:
                bone.parent = armature.data.edit_bones[flver_bone.parent_index]

            translation_vector = Vector(
                (flver_bone.translation[0], flver_bone.translation[1],
                 flver_bone.translation[2]))
            rotation_matrix = (
                Matrix.Rotation(flver_bone.rotation[1], 4, 'Y')
                @ Matrix.Rotation(flver_bone.rotation[2], 4, 'Z')
                @ Matrix.Rotation(flver_bone.rotation[0], 4, 'X'))

            head = parent_matrix @ translation_vector
            tail = head + rotation_matrix @ Vector((0, 0.05, 0))

            bone.head = (head[0], head[2], head[1])
            bone.tail = (tail[0], tail[2], tail[1])

            # Transform children and advance to next sibling
            transform_bone_and_siblings(
                flver_bone.child_index, parent_matrix
                @ Matrix.Translation(translation_vector) @ rotation_matrix)
            bone_index = flver_bone.next_sibling_index

    transform_bone_and_siblings(0, Matrix())

    def connect_bone(bone):
        children = bone.children
        if len(children) == 0:
            parent = bone.parent
            if parent is not None:
                direction = parent.tail - parent.head
                direction.normalize()
                length = (bone.tail - bone.head).magnitude
                bone.tail = bone.head + direction * length
            return
        if len(children) > 1:
            for child in children:
                connect_bone(child)
            return
        child = children[0]
        bone.tail = child.head
        child.use_connect = True
        connect_bone(child)

    for bone in root_bones:
        connect_bone(bone)

    bpy.ops.object.editmode_toggle() 
    return armature

def import_textures(path, name, unpack_path):
    """
    Unpacks the specified tpf file into dds textures
    and returns the directory where unpacked.
    """
    if isfile(path + name + ".texbnd.dcx"):
        DCXFile = DCX(path + name + ".texbnd.dcx", None)
        BNDFile = BND4(DCXFile.data)
    else:
        raise FileNotFoundError("Missing texture file.")

    BNDFile.write_unpacked_dir(unpack_path)
    tpf_path = unpack_path + "\\.unpacked\\" + name + ".tpf"
    TPFFile = TPF(tpf_path)
    print("Importing TPF file from " + str(tpf_path))
    TPFFile.unpack()
    TPFFile.save_textures_to_file()
    convert_to_png(TPFFile.file_path + "_textures\\")
    remove(tpf_path)
    return TPFFile.file_path + "_textures\\"
    

def create_material(texture_path, name):
    """
    Creates a blender principled shader material
    with an albedo, roughness and normal map.

    texture_path: absolute path to texture unpack directory
    name: basename of texture (eg: {name}_a.PNG)

    return: blender material
    """

    material = bpy.data.materials.new(name)
    material.use_nodes = True
    node_tree = material.node_tree

    bsdf = material.node_tree.nodes.get("Principled BSDF")
    material.diffuse_color = (random(), random(), random(), 1.0) # Viewport display colour
    material.blend_method = 'CLIP'

    try:
        albedo_node = material.node_tree.nodes.new("ShaderNodeTexImage")   
        albedo_node.image = bpy.data.images.load(texture_path + name + "_a.PNG")
        node_tree.links.new(albedo_node.outputs["Color"], bsdf.inputs["Base Color"])
        node_tree.links.new(albedo_node.outputs["Alpha"], bsdf.inputs["Alpha"]) # Only available on Blender 2.9+
    except (RuntimeError):
        # Occasionally a texture will be missing some maps, so for now just skip these missing textures/nodes
        pass
    
    try:
        roughness_node = material.node_tree.nodes.new("ShaderNodeTexImage")
        roughness_node.image = bpy.data.images.load(texture_path + name + "_r.PNG")
        roughness_node.image.colorspace_settings.name = 'Non-Color'
        invert_rough = material.node_tree.nodes.new("ShaderNodeInvert")
        node_tree.links.new(roughness_node.outputs["Color"], invert_rough.inputs["Color"])
        node_tree.links.new(invert_rough.outputs["Color"], bsdf.inputs["Roughness"])
    except (RuntimeError):
        pass

    try:
        normal_node = material.node_tree.nodes.new("ShaderNodeTexImage")   
        normal_node.image = bpy.data.images.load(texture_path + name + "_n.PNG")
        normal_node.image.colorspace_settings.name = 'Non-Color'
        invert_norm = material.node_tree.nodes.new("ShaderNodeInvert")                   # Need to invert the normal map as
        normal_conv = material.node_tree.nodes.new("ShaderNodeNormalMap")                # from seems to use a different
        node_tree.links.new(normal_node.outputs["Color"], invert_norm.inputs["Color"])   # coordinate system
        node_tree.links.new(invert_norm.outputs["Color"], normal_conv.inputs["Color"])
        node_tree.links.new(normal_conv.outputs["Normal"], bsdf.inputs["Normal"])
        normal_conv.inputs[0].default_value = 0.5
    except (RuntimeError):
        pass

    
    return material
    
if __name__ == "__main__":
    run("E:\\Projects\\unpack", "E:\\Projects\\test", "c1130.chrbnd.dcx", False, True)