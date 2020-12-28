import os
import bpy
import bmesh
from .dcx import DCX
from .bnd import BND3, BND4
from .flver_utils import read_flver
from .flver import Flver
import tempfile
import ntpath
from bpy.app.translations import pgettext
from mathutils import Matrix, Vector
from mathutils.noise import random

def run(path, get_textures, unwrap_mesh):

        name = os.path.basename(path)

        if name.endswith(".chrbnd.dcx"): # Character
            name = name[:-11]
            import_mesh(path, name, get_textures, unwrap_mesh, True, False)
            return
        elif name.endswith(".mapbnd.dcx"): # Map
            name = name[:-11]
            import_mesh(path, name, get_textures, unwrap_mesh, True, False)
            return
        elif name.endswith(".bnd"): # DS2 Character files
            name = name[:-4]
            import_mesh(path, name, get_textures, unwrap_mesh, False, False)
            return
        else:
            raise TypeError("Unsupported DCX type")


def import_mesh(path, name, get_textures, unwrap_mesh, unpack_dcx, import_rig):
    with tempfile.TemporaryDirectory() as tmpdirname:
        if unpack_dcx:
            # Unpacking DCX to get DCX.data
            DCXFile = DCX(path, None)

            # Unpacking BND
            magic = DCXFile.data[:4]
            map(ord, magic)
            magic = magic.decode("utf-8")
            if (magic == 'BND4'):
                BNDFile = BND4(DCXFile.data)
            elif (magic == 'BND3'):
                BNDFile = BND3(DCXFile.data)
            else:
                raise Exception("File must be in BND4 or BND3 format")
        else:
            BNDFile = BND4(path)
        
        BNDFile.write_unpacked_dir(tmpdirname)

        # Creating Mesh with from FLVER file
        if unpack_dcx:
            flver_path = tmpdirname + "\\.unpacked\\" + name + ".flver"
        else:
            flver_path = tmpdirname + "\\" + name + ".bnd.unpacked\\" + name + ".flv"

        flver_data = read_flver(flver_path)
        inflated_meshes = flver_data.inflate()

        collection = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(collection)
    
    # Create armature
    if import_rig:
        armature = create_armature(name, collection, flver_data)

    # Create materials
    materials = []
    for flver_material in flver_data.materials:
        material = bpy.data.materials.new(flver_material.name)
        material.use_nodes = True
        bsdf = material.node_tree.nodes.get("Principled BSDF")
        material.diffuse_color = (random(), random(), random(), 1.0) # Viewport display colour
        materials.append(material)

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
        mesh_name = f"{name}.{index}.{material_name}"
        mesh = bpy.data.meshes.new(name=mesh_name)
        mesh.from_pydata(verts, [], inflated_mesh.faces)

        # Create object
        obj = bpy.data.objects.new(mesh_name, mesh)
        collection.objects.link(obj)

        # Assign armature
        if import_rig:
            obj.modifiers.new(type="ARMATURE",
                              name=pgettext("Armature")).object = armature
            obj.parent = armature

        # Assign material
        obj.data.materials.append(materials[flver_mesh.material_index])

        # Create vertex groups for bones
        for bone_index in flver_mesh.bone_indices:
            obj.vertex_groups.new(name=flver_data.bones[bone_index].name)

        bm = bmesh.new()
        bm.from_mesh(mesh)
        """ # Would be a better uv method if it worked here
        uv_layer = bm.loops.layers.uv.new()
        for face in bm.faces:
            for loop in face.loops:
                u, v = inflated_mesh.vertices.uv[loop.vert.index] # Currently none-types
                loop[uv_layer].uv = (u, 1.0 - v)
        """
        if unwrap_mesh:
            # Creating UV with basic seam unwrap method
            bpy.context.view_layer.objects.active = obj
            obj.data.uv_layers.new(name="UVMap")
            lm = obj.data.uv_layers[0]
            lm.active = True
            bpy.ops.object.editmode_toggle() 
            bpy.ops.mesh.select_all(action='SELECT') 
            bpy.ops.uv.unwrap()
            bpy.ops.object.editmode_toggle() 
        # Applying bone weights
        if import_rig:
            weight_layer = bm.verts.layers.deform.new()
            for vert in bm.verts:
                weights = inflated_mesh.vertices.bone_weights[vert.index]
                indices = inflated_mesh.vertices.bone_indices[vert.index]
                for index, weight in zip(indices, weights):
                    if weight == 0.0:
                        continue
                    vert[weight_layer][index] = weight
        

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

        
