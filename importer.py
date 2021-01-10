import bpy, bmesh, subprocess
from os import listdir, mkdir, walk
from os.path import isfile, join, dirname, realpath
from pathlib import Path
from .flver_utils import read_flver
from .tpf import TPF, convert_to_png
from bpy.app.translations import pgettext
from mathutils import Matrix, Vector
from random import random
from shutil import copyfile, rmtree

def import_mesh(path, file_name, unpack_path, get_textures, clean_up_files, import_rig):
    """
    Converts a DCX file to flver and imports it into Blender.
    
    Args:
        path (str): Directory of the dcx file.
        file_name (str): File name of the dcx file
        base_name (str): ID of the object.
        unpack_path (str): Where the dcx file and textures will be unpacked to.
        get_textures (bool): If to look for textures in {path} and convert them to png.
        yabber_dcx (bool): Whether to unpack with yabber.dcx.exe (true) or regular yabber.exe

    TODO:
        Replace all file paths with python Path type
    """

    print("Importing {} from {}".format(file_name, str(path)))

    base_name = file_name.split('.')[0]
    try:
        mkdir(unpack_path / Path(base_name))
    except FileExistsError:
        pass
    tmp_path = Path(unpack_path / base_name)
    sys_path = Path(dirname(realpath(__file__)))
    copyfile( path / file_name, tmp_path / file_name)

    if  file_name.endswith(".flver.dcx"):
        command = f'"{sys_path}\\Yabber\\Yabber.DCX.exe" "{tmp_path}\\{file_name}"'
    elif file_name.endswith(".flver"):
        command = ""
    else:
        command = f'"{sys_path}\\Yabber\\Yabber.exe" "{tmp_path}\\{file_name}"'

    p = subprocess.Popen(command, stderr = subprocess.PIPE, stdout = subprocess.PIPE)
    while True:
        out, err = p.communicate()
        if p.returncode is not None: 
            break # Prevents Yabber from holding up Blender if it fails unpacking.
    
    flver_path = None
    for dirpath, subdirs, files in walk(tmp_path):
        for x in files:
            if x.endswith(".flver") | x.endswith(".flv"):
                flver_path = Path(join(dirpath, x))
    if flver_path == None:
        raise Exception(f"Unsupported file type: {file_name}")

    flver_data = read_flver(flver_path)
    inflated_meshes = flver_data.inflate()

    collection = bpy.data.collections.new(base_name)
    bpy.context.scene.collection.children.link(collection)
    
    # Create armature
    if import_rig:
        armature = create_armature(base_name, collection, flver_data)

    materials = []

    if get_textures:
        try:
            texture_path = import_textures(path, base_name, unpack_path)
            files = [f for f in listdir(texture_path) if isfile(join(texture_path, f))]
            for file in files:
                if "_a" in file:
                    name = file[:-6]
                    materials.append(create_material(texture_path, name))
        except FileNotFoundError:
            print("Texture file not found.")
            pass

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

        mesh_name = f"{base_name}_{material_name}"
        mesh = bpy.data.meshes.new(name=mesh_name)
        mesh.from_pydata(verts, [], inflated_mesh.faces)

        # Create object and append it to the current collection
        obj = bpy.data.objects.new(mesh_name, mesh)
        collection.objects.link(obj)

        # Assign armature to object
        if import_rig:
            obj.modifiers.new(type="ARMATURE", name=pgettext("Armature")).object = armature
            obj.parent = armature
            
            # Create vertex groups for bones
            if len(flver_mesh.bone_indices) == 0:
                print(f"{mesh_name} Has empty bone indices")
            for bone_index in flver_mesh.bone_indices:
                try:
                    obj.vertex_groups.new(name=flver_data.bones[bone_index].name)
                except IndexError:
                    print(f"Bone index error at {bone_index}")

        # Assign materials to object
        # TODO: Replace with a more robust method.
        if get_textures:
            for material in materials:
                if (material.name.lower() == mesh_name.lower()) or \
                    (material.name.lower().endswith(mesh_name.lower())) or \
                    (mesh_name.lower().endswith(material.name.lower())):
                    obj.data.materials.append(material)



        bm = bmesh.new()
        bm.from_mesh(mesh)

        # Creating UVs
        uv_layer = bm.loops.layers.uv.new()
        for face in bm.faces:
            for loop in face.loops:
                u, v = inflated_mesh.vertices.uv[loop.vert.index]
                loop[uv_layer].uv = (u, 1.0 - v)
            face.smooth = True

        if import_rig:
            weight_layer = bm.verts.layers.deform.new()
            for vert in bm.verts:
                try:
                    weights = inflated_mesh.vertices.bone_weights[vert.index]
                    indices = inflated_mesh.vertices.bone_indices[vert.index]
                    for index, weight in zip(indices, weights):
                        if weight == 0.0:
                            continue
                        vert[weight_layer][index] = weight
                except IndexError:
                    # TODO: Replace with check for zero bone_count, which then uses
                    # the data from the flver file to get bone weights and indices,
                    # not each flver mesh.
                    continue 

        bm.to_mesh(mesh)
        bm.free()
        mesh.update()

    if clean_up_files:
        print(f"Removing {tmp_path}")
        rmtree(tmp_path)
        
def create_armature(name, collection, flver_data):
    """
    Creates a Blender armature.

    Args:
        name (str): Base name / ID of the file.
        collection (Collection): Blender scene collection to place the armature in.
        flver_data (Flver): Data for bone information.
    
    Returns:
        Object: Armature fitting to model.
    """
    armature = bpy.data.objects.new(name, bpy.data.armatures.new(name))
    collection.objects.link(armature)
    armature.data.display_type = "OCTAHEDRAL"
    armature.show_in_front = True
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

def import_textures(path, base_name, unpack_path):
    """
    Unpacks the specified tpf file into png textures
    and returns the directory where unpacked.
    
    Args:
        path (str): Path to the directory where the dcx texture file exists.
        base_name (str): 'ID' of the file being unpacked, consistent with model file.
        unpack_path (str): User defined unpack directory.

    Returns:
        str: The directory where the textures have been unpacked to.

    Raises:
        FileNotFoundError: If the texture file does not exist.

    TODO:
        Instead of looking for a same-name texture file, use allmaterialbnd.mtdbnd.dcx to lookup directory.
    """
    sys_path = Path(dirname(realpath(__file__)))

    print(f"Looking for texture file in {path}")
    copyfile(path / f"{base_name}.texbnd.dcx", unpack_path / base_name / (f"{base_name}.texbnd.dcx"))

    command = f'"{sys_path}\\Yabber\\Yabber.exe" "{unpack_path}\\{base_name}\\{base_name}.texbnd.dcx"'
    subprocess.run(command, shell = False)

    tpf_path = unpack_path / base_name / (f"{base_name}-texbnd-dcx") / "chr" / base_name / Path(f"{base_name}.tpf")
    TPFFile = TPF(tpf_path)
    print("Importing TPF file from " + str(tpf_path))
    TPFFile.unpack()
    TPFFile.save_textures_to_file(file_path = unpack_path / base_name)
    convert_to_png(unpack_path / f"{base_name}_textures\\")
    return unpack_path / f"{base_name}_textures\\"
    

def create_material(texture_path, base_name):
    """
    Creates a blender principled shader material
    with an albedo, roughness and normal map.

    Args:
        texture_path (str): absolute path to texture unpack directory
        base_name (str): 'ID' of the file being unpacked, consistent with model file.

    Returns:
        Material: Blender principled shader material.

    TODO:
        Add check for file existing before creating node
        Add emmissive support.
    """

    material = bpy.data.materials.new(base_name)
    material.use_nodes = True
    node_tree = material.node_tree

    bsdf = material.node_tree.nodes.get("Principled BSDF")
    material.diffuse_color = (random(), random(), random(), 1.0) # Viewport display colour
    material.blend_method = 'HASHED'


    albedo_node = create_tex_image(str(texture_path / (base_name + "_a.PNG")), material)
    if albedo_node:
        node_tree.links.new(albedo_node.outputs["Color"], bsdf.inputs["Base Color"])
        node_tree.links.new(albedo_node.outputs["Alpha"], bsdf.inputs["Alpha"]) # Only available on Blender 2.8+
    
    roughness_node = create_tex_image(str(texture_path / (base_name + "_r.PNG")), material)
    if roughness_node:
        roughness_node.image.colorspace_settings.name = 'Non-Color'
        invert_rough = material.node_tree.nodes.new("ShaderNodeInvert")
        node_tree.links.new(roughness_node.outputs["Color"], invert_rough.inputs["Color"])
        node_tree.links.new(invert_rough.outputs["Color"], bsdf.inputs["Roughness"])
        # Technically this is a specular reflection, not a roughness, however for Blender 2.8
        # its a bit of a pain to put specularity in through python, so until 2.9 becomes more
        # widespread this can probably just stay here (Looks extremely similar anyway).


    normal_node = create_tex_image(str(texture_path / (base_name + "_n.PNG")), material)
    if normal_node:
        normal_node.image.colorspace_settings.name = 'Non-Color'
        invert_norm = material.node_tree.nodes.new("ShaderNodeInvert")
        normal_conv = material.node_tree.nodes.new("ShaderNodeNormalMap")
        node_tree.links.new(normal_node.outputs["Color"], invert_norm.inputs["Color"])
        node_tree.links.new(invert_norm.outputs["Color"], normal_conv.inputs["Color"])
        node_tree.links.new(normal_conv.outputs["Normal"], bsdf.inputs["Normal"])
        normal_conv.inputs[0].default_value = 0.2
        # Seem to need to invert the normal map to get it to the correct coordinate system.

    metalness_node = create_tex_image(str(texture_path / (base_name + "_m.PNG")), material)
    if metalness_node:
        metalness_node.image.colorspace_settings.name = 'Non-Color'
        node_tree.links.new(metalness_node.outputs["Color"], bsdf.inputs["Metallic"])

    emissive_node = create_tex_image(str(texture_path / (base_name + "_em.PNG")), material)
    if emissive_node:
        node_tree.links.new(emissive_node.outputs["Color"], bsdf.inputs["Emission"])

    return material

def create_tex_image(path, material):
    if isfile(path):
        node = material.node_tree.nodes.new("ShaderNodeTexImage")
        node.image = bpy.data.images.load(path)
        return node
    return None