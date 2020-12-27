import os
import bpy
import bmesh
from .dcx import DCX
from .bnd import BND3, BND4
from .flver_utils import read_flver
from .flver import Flver
import tempfile
import ntpath
from mathutils import Matrix, Vector
from mathutils.noise import random

def run(path, get_textures, unwrap_mesh):

        name = os.path.basename(path)

        if name.endswith(".chrbnd.dcx") | name.endswith(".mapbnd.dcx"): # Character or Map file
            name = name[:-11]
            import_mesh(path, name, get_textures, unwrap_mesh, True)
            return
        elif name.endswith(".bnd"): # DS2 Character files
            name = name[:-4]
            import_mesh(path, name, get_textures, unwrap_mesh, False)
            return
        else:
            raise TypeError("Unsupported DCX type")


def import_mesh(path, name, get_textures, unwrap_mesh, unpack_dcx):
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

        collection = bpy.context.view_layer.active_layer_collection.collection

    # Create materials
    materials = []
    for flver_material in flver_data.materials:
        material = bpy.data.materials.new(flver_material.name)
        material.diffuse_color = (random(), random(), random(), 1.0)
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

        # Assign material
        obj.data.materials.append(materials[flver_mesh.material_index])

        # Create vertex groups for bones
        for bone_index in flver_mesh.bone_indices:
            obj.vertex_groups.new(name=flver_data.bones[bone_index].name)

        bm = bmesh.new()
        bm.from_mesh(mesh)

        if unwrap_mesh:
            # Creating UV with basic unwrap method
            bpy.context.view_layer.objects.active = obj
            obj.data.uv_layers.new(name="UVMap")
            lm = obj.data.uv_layers[0]
            lm.active = True
            bpy.ops.object.editmode_toggle() 
            bpy.ops.mesh.select_all(action='SELECT') 
            bpy.ops.uv.unwrap()
            bpy.ops.object.editmode_toggle() 

        bm.free()
        mesh.update()


def import_tex(path, name):
    return




        