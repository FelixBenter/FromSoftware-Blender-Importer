from enum import Enum
import struct


class Endianness(Enum):
    BIG = b"B\0"
    LITTLE = b"L\0"


class TextEncoding(Enum):
    SHIFT_JIS = 0
    UTF_16 = 1


class Header:
    def __init__(self, endianness, version, bounding_box_min, bounding_box_max,
                 default_vertex_index_size, text_encoding, unk4A, unk4C, unk5C,
                 unk5D, unk68):
        self.endianness = endianness
        self.version = version
        self.bounding_box_min = bounding_box_min
        self.bounding_box_max = bounding_box_max
        self.default_vertex_index_size = default_vertex_index_size
        self.text_encoding = text_encoding
        self.unk4A = unk4A
        self.unk4C = unk4C
        self.unk5C = unk5C
        self.unk5D = unk5D
        self.unk68 = unk68


class Dummy:
    def __init__(self, position, color, forward, reference_id,
                 parent_bone_index, upward, attach_bone_index, flag1,
                 use_upward_vector, unk30, unk34):
        self.position = position
        self.color = color
        self.forward = forward
        self.reference_id = reference_id
        self.parent_bone_index = parent_bone_index
        self.upward = upward
        self.attach_bone_index = attach_bone_index
        self.flag1 = flag1
        self.use_upward_vector = use_upward_vector
        self.unk30 = unk30
        self.unk34 = unk34


class Material:
    def __init__(self, name, mtd_path, texture_count, texture_index, flags,
                 unk18):
        self.name = name
        self.mtd_path = mtd_path
        self.texture_count = texture_count
        self.texture_index = texture_index
        self.flags = flags
        self.unk18 = unk18


class Bone:
    def __init__(self, translation, name, rotation, parent_index, child_index,
                 scale, next_sibling_index, previous_sibling_index,
                 bounding_box_min, unk3C, bounding_box_max):
        self.translation = translation
        self.name = name
        self.rotation = rotation
        self.parent_index = parent_index
        self.child_index = child_index
        self.scale = scale
        self.next_sibling_index = next_sibling_index
        self.bounding_box_min = bounding_box_min
        self.unk3C = unk3C
        self.bounding_box_max = bounding_box_max


class Mesh:
    # According to upstream: when 1, mesh is in bind pose; when 0, it isn't.
    # Most likely has further implications.
    class DynamicMode(Enum):
        NON_DYNAMIC = 0
        DYNAMIC = 1

    def __init__(self, dynamic_mode, material_index, default_bone_index,
                 bone_indices, index_buffer_indices, vertex_buffer_indices):
        self.dynamic_mode = dynamic_mode
        self.material_index = material_index
        self.default_bone_index = default_bone_index
        self.bone_indices = bone_indices
        self.index_buffer_indices = index_buffer_indices
        self.vertex_buffer_indices = vertex_buffer_indices


class IndexBuffer:
    class DetailFlags(Enum):
        LOD_LEVEL1 = 0x01000000
        LOD_LEVEL2 = 0x02000000
        MOTION_BLUR = 0x80000000

    class PrimitiveMode(Enum):
        TRIANGLES = 0
        TRIANGLE_STRIP = 1

    class BackfaceVisibility(Enum):
        SHOW = 0
        CULL = 1

    def __init__(self, detail_flags, primitive_mode, backface_visibility,
                 unk06, indices):
        self.detail_flags = detail_flags
        self.primitive_mode = primitive_mode
        self.backface_visibility = backface_visibility
        self.unk06 = unk06
        self.indices = indices

    def _inflate(self, faces):
        if self.primitive_mode == self.PrimitiveMode.TRIANGLES:
            for i in range(0, len(self.indices), 3):
                faces.append(tuple(self.indices[i:i + 3]))
        else:
            direction = -1
            f1 = self.indices[0]
            f2 = self.indices[1]
            for i in range(2, len(self.indices)):
                f3 = self.indices[i]
                direction *= -1
                if f1 != f2 and f2 != f3 and f3 != f1:
                    if direction > 0:
                        faces.append((f1, f2, f3))
                    else:
                        faces.append((f1, f3, f2))
                f1 = f2
                f2 = f3


class VertexBuffer:
    def __init__(self, buffer_index, struct_index, struct_size, vertex_count,
                 buffer_data):
        self.buffer_index = buffer_index
        self.struct_index = struct_index
        self.struct_size = struct_size
        self.vertex_count = vertex_count
        self.buffer_data = buffer_data

    def _inflate(self, vertices, struct, version):
        struct_size = sum(member.size() for member in struct)
        assert self.struct_size == struct_size
        assert len(self.buffer_data) % self.struct_size == 0

        # For now, only select from a limited set of attributes: POSITION,
        # BONE_WEIGHTS, BONE_INDICES, and UV.
        struct_members = [
            member for member in struct if member.attribute_type in {
                VertexBufferStructMember.AttributeType.POSITION,
                VertexBufferStructMember.AttributeType.BONE_WEIGHTS,
                VertexBufferStructMember.AttributeType.BONE_INDICES,
                VertexBufferStructMember.AttributeType.UV,
            }
        ]

        attribute_map = {
            VertexBufferStructMember.AttributeType.POSITION:
            vertices.positions,
            VertexBufferStructMember.AttributeType.BONE_WEIGHTS:
            vertices.bone_weights,
            VertexBufferStructMember.AttributeType.BONE_INDICES:
            vertices.bone_indices,
            VertexBufferStructMember.AttributeType.UV: vertices.uv,
        }
        for member in struct_members:
            for i in range(self.vertex_count):
                data = member._unpack(self.buffer_data, i * self.struct_size,
                                      version)
                attribute_map[member.attribute_type].append(data)


class VertexBufferStructMember:
    class DataType(Enum):
        # Two single-precision floats.
        FLOAT2 = 0x01
        # Three single-precision floats.
        FLOAT3 = 0x02
        # Four single-precision floats.
        FLOAT4 = 0x03
        # Unknown.
        BYTE4A = 0x10
        # Four bytes
        BONE_INDICES = 0x11
        # Two shorts?
        SHORT2_TO_FLOAT2 = 0x12
        # Four bytes.
        BYTE4C = 0x13
        # Two shorts.
        UV = 0x15
        # Two shorts and two shorts.
        UV_PAIR = 0x16
        # Four shorts, maybe unsigned?
        SHORT_BONE_INDICES = 0x18
        # Four shorts.
        BONE_WEIGHTS = 0x1A
        # Unknown.
        SHORT4_TO_FLOAT4B = 0x2E
        # Unknown.
        BYTE4E = 0x2F

    class AttributeType(Enum):
        # Location of the vertex.
        POSITION = 0
        # Weight of the vertex's attachment to bones.
        BONE_WEIGHTS = 1
        # Bones the vertex is weighted to, indexing the parent mesh's bone
        # indices.
        BONE_INDICES = 2
        # Orientation of the vertex.
        NORMAL = 3
        # Texture coordinates of the vertex.
        UV = 5
        # Vector pointing perpendicular to the normal.
        TANGENT = 6
        # Vector pointing perpendicular to the normal and tangent.
        BITANGENT = 7
        # Data used for blending, alpha, etc.
        VERTEX_COLOR = 10

    def __init__(self, unk00, struct_offset, data_type, attribute_type, index):
        self.unk00 = unk00
        self.struct_offset = struct_offset
        self.data_type = data_type
        self.attribute_type = attribute_type
        self.index = index

    def size(self):
        if self.data_type in {
                self.DataType.BYTE4A,
                self.DataType.BONE_INDICES,
                self.DataType.SHORT2_TO_FLOAT2,
                self.DataType.BYTE4C,
                self.DataType.UV,
                self.DataType.BYTE4E,
        }:
            return 4
        if self.data_type in {
                self.DataType.FLOAT2,
                self.DataType.UV_PAIR,
                self.DataType.BONE_INDICES,
                self.DataType.BONE_WEIGHTS,
                self.DataType.SHORT4_TO_FLOAT4B,
        }:
            return 8
        if self.data_type == self.DataType.FLOAT3:
            return 12
        if self.data_type == self.DataType.FLOAT4:
            return 16
        raise Exception("unknown size for data type")

    def _unpack(self, buf, offset, version):
        if version >= 0x2000F:
            uv_divisor = 2048.0
        else:
            uv_divisor = 1024.0
        offset += self.struct_offset
        if self.data_type == self.DataType.FLOAT2:
            return tuple(struct.unpack_from("ff", buf, offset))
        if self.data_type == self.DataType.FLOAT3:
            return tuple(struct.unpack_from("fff", buf, offset))
        if self.data_type == self.DataType.FLOAT4:
            return tuple(struct.unpack_from("ffff", buf, offset))
        if self.data_type == self.DataType.UV:
            uv = struct.unpack_from("hh", buf, offset)
            return tuple(component / uv_divisor for component in uv)
        if self.data_type == self.DataType.BONE_INDICES:
            return tuple(struct.unpack_from("BBBB", buf, offset))
        if self.data_type == self.DataType.BONE_WEIGHTS:
            weights = struct.unpack_from("HHHH", buf, offset)
            return tuple(weight / 32767.0 for weight in weights)


class Texture:
    def __init__(self, path, type_name, scale, unk10, unk11, unk14, unk18,
                 unk1C):
        self.path = path
        self.type_name = type_name
        self.scale = scale
        self.unk10 = unk10
        self.unk11 = unk11
        self.unk14 = unk14
        self.unk18 = unk18
        self.unk1C = unk1C


class InflatedMesh:
    class Vertices:
        def __init__(self):
            self.positions = []
            self.bone_weights = []
            self.bone_indices = []
            self.uv = []

    def __init__(self):
        self.faces = []
        self.vertices = self.Vertices()


class Flver:
    def __init__(self, header, dummies, materials, bones, meshes,
                 index_buffers, vertex_buffers, vertex_buffer_structs,
                 textures):
        self.header = header
        self.dummies = dummies
        self.materials = materials
        self.bones = bones
        self.meshes = meshes
        self.index_buffers = index_buffers
        self.vertex_buffers = vertex_buffers
        self.vertex_buffer_structs = vertex_buffer_structs
        self.textures = textures

    # For every mesh, combine all index buffers into a single index buffer and
    # all vertex buffer attributes into individual corresponding attribute
    # lists.
    def inflate(self):
        return [self._inflate_mesh(mesh) for mesh in self.meshes]

    def _inflate_mesh(self, mesh):
        result = InflatedMesh()

        # Triangulate faces
        index_buffers = [
            self.index_buffers[index] for index in mesh.index_buffer_indices
            if len(self.index_buffers[index].detail_flags) == 0
        ]
        if len(index_buffers) == 0:
            return None
        assert len(index_buffers) == 1
        index_buffers[0]._inflate(result.faces)

        # Parse vertex buffer attributes
        vertex_buffers = [
            self.vertex_buffers[index] for index in mesh.vertex_buffer_indices
        ]
        assert len(vertex_buffers) > 0
        for vertex_buffer in vertex_buffers:
            struct = self.vertex_buffer_structs[vertex_buffer.struct_index]
            vertex_buffer._inflate(vertices=result.vertices,
                                   struct=struct,
                                   version=self.header.version)

        return result