import bpy, bmesh, subprocess, time
from os import listdir, mkdir, walk
from os.path import isfile, join, dirname, realpath
from pathlib import Path
from .flver_utils import read_flver
from .tpf import TPF, convert_to_png
from bpy.app.translations import pgettext
from mathutils import Matrix, Vector
from random import random
from shutil import copyfile, rmtree

def import_mesh(path, file_name, unpack_path, yabber_path, get_textures, clean_up_files, import_rig):
    """
    Converts a DCX file to flver and imports it into Blender.
    
    Args:
        path (str): Directory of the dcx file.
        file_name (str): File name of the dcx file
        base_name (Path): ID of the object.
        unpack_path (str): Where the dcx file and textures will be unpacked to.
        get_textures (bool): If to look for textures in {path} and convert them to png.
        yabber_dcx (bool): Whether to unpack with yabber.dcx.exe (true) or regular yabber.exe

    """

    print("Importing {} from {}".format(file_name, str(path)))

    base_name = file_name.split('.')[0]
    try:
        mkdir(unpack_path / Path(base_name))
    except FileExistsError:
        pass
    tmp_path = Path(unpack_path / base_name)
    copyfile( path / file_name, tmp_path / file_name)

    if file_name.endswith(".flver.dcx"):
        command = f'"{yabber_path}\\Yabber.DCX.exe" "{tmp_path}\\{file_name}"'
    elif file_name.endswith(".flver"):
        command = ""
    else:
        command = f'"{yabber_path}\\Yabber.exe" "{tmp_path}\\{file_name}"'

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
                if file_name.endswith(".partsbnd.dcx"):
                    path = Path(dirpath)
    if flver_path == None:
        raise Exception(f"Unsupported file type: {file_name}")

    time_start = time.perf_counter()

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
            texture_path = import_textures(path, base_name, unpack_path, yabber_path)
            files = [f for f in listdir(texture_path) if isfile(join(texture_path, f))]
            for file in files:
                if "_a" in file:
                    name = file[:-6]
                    materials.append(create_material(texture_path, name))
        except FileNotFoundError as fne:
            print(f"Texture file not found {fne}")
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
                    #print(f"Bone index error at {bone_index}")
                    pass

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
                u_0, v_0 = inflated_mesh.vertices.uv[loop.vert.index][:2]
                loop[uv_layer].uv = (u_0, 1.0 - v_0)
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

    time_end = time.perf_counter()
    print(f'FLVER time taken: {time_end - time_start}')
        
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

def import_textures(path, base_name, unpack_path, yabber_path):
    """
    Unpacks the specified tpf file into png textures
    and returns the directory where unpacked.
    Unpacks if in dcx compression.
    
    Args:
        path (str): Path to the directory where the texture file exists.
        base_name (str): 'ID' of the file being unpacked, consistent with model file.
        unpack_path (str): User defined unpack directory.

    Returns:
        str: The directory where the textures have been unpacked to.

    Raises:
        FileNotFoundError: If the texture file does not exist.

    TODO:
        Instead of looking for a same-name texture file, use allmaterialbnd.mtdbnd.dcx to lookup directory.
    """
    
    if isfile(path / f"{base_name}.tpf"): # Dumb temp fix for partsbnd case
        tpf_path = path / f"{base_name}.tpf"
    else:
        copyfile(path / f"{base_name}.texbnd.dcx", unpack_path / base_name / (f"{base_name}.texbnd.dcx"))
        command = f'"{yabber_path}\\Yabber.exe" "{unpack_path}\\{base_name}\\{base_name}.texbnd.dcx"'
        subprocess.run(command, shell = False)
        tpf_path = unpack_path / base_name / (f"{base_name}-texbnd-dcx") / "chr" / base_name / Path(f"{base_name}.tpf")

    TPFFile = TPF(tpf_path)
    print(f'Importing TPF file from {str(tpf_path)}...', end = '')
    TPFFile.unpack()
    TPFFile.save_textures_to_file(file_path = unpack_path / base_name)
    convert_to_png(unpack_path / f"{base_name}_textures\\")
    print('done')
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
        node_tree.links.new(albedo_node.outputs["Alpha"], bsdf.inputs["Alpha"])
    
    specular_node = create_tex_image(str(texture_path / (base_name + "_r.PNG")), material)
    if specular_node:
        node_tree.links.new(specular_node.outputs["Color"], bsdf.inputs["Specular Tint"])

    metalness_node = create_tex_image(str(texture_path / (base_name + "_m.PNG")), material)
    if metalness_node:
        metalness_node.image.colorspace_settings.name = 'Non-Color'
        node_tree.links.new(metalness_node.outputs["Color"], bsdf.inputs["Metallic"])

    emissive_node = create_tex_image(str(texture_path / (base_name + "_em.PNG")), material)
    if emissive_node:
        node_tree.links.new(emissive_node.outputs["Color"], bsdf.inputs["Emission"])

    normal_node = create_tex_image(str(texture_path / (base_name + "_n.PNG")), material)
    if normal_node:
        normal_node.image.colorspace_settings.name = 'Non-Color'
        sep_rgb = material.node_tree.nodes.new("ShaderNodeSeparateRGB")
        node_tree.links.new(normal_node.outputs["Color"], sep_rgb.inputs["Image"])
        com_rgb = material.node_tree.nodes.new("ShaderNodeCombineRGB")
        node_tree.links.new(sep_rgb.outputs[0], com_rgb.inputs[0])
        node_tree.links.new(sep_rgb.outputs[1], com_rgb.inputs[1])
        node_tree.links.new(sep_rgb.outputs[2], bsdf.inputs["Specular"])
        normalise_node = material.node_tree.nodes.new("ShaderNodeVectorMath")
        normalise_node.operation = 'NORMALIZE'
        node_tree.links.new(com_rgb.outputs["Image"], normalise_node.inputs["Vector"])
        normal_conv = material.node_tree.nodes.new("ShaderNodeNormalMap")
        node_tree.links.new(normalise_node.outputs["Vector"], normal_conv.inputs["Color"])
        node_tree.links.new(normal_conv.outputs["Normal"], bsdf.inputs["Normal"])
        normal_conv.inputs[0].default_value = 0.5
    return material

def create_tex_image(path, material):
    if isfile(path):
        node = material.node_tree.nodes.new("ShaderNodeTexImage")
        node.image = bpy.data.images.load(path)
        return node
    return None