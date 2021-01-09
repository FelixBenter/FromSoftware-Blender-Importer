import struct
from collections import deque
from . import flver

class StructReader:
    def __init__(self, fp):
        self.fp = fp
        self.endianness = None
        self.text_encoding = None

    def tell(self):
        return self.fp.tell()

    def seek(self, offset):
        self.fp.seek(offset, 0)

    def read(self, count, offset=None):
        if offset is not None:
            position = self.fp.tell()
            self.fp.seek(offset, 0)
        result = self.fp.read(count)
        if offset is not None:
            self.fp.seek(position, 0)
        return result

    def read_struct(self, fmt, offset=None):
        if offset is not None:
            position = self.fp.tell()
            self.fp.seek(offset, 0)

        # Prefix endianness marker for struct
        prefix = ""
        if self.endianness == flver.Endianness.BIG:
            prefix = ">"
        elif self.endianness == flver.Endianness.LITTLE:
            prefix = "<"

        result = struct.unpack(prefix + fmt,
                               self.fp.read(struct.calcsize(fmt)))
        if offset is not None:
            self.fp.seek(position, 0)
        return result

    def read_string(self, offset=None):
        if self.text_encoding == flver.TextEncoding.UTF_16:
            terminator = b"\0\0"
            encoding = "utf_16_le"
        elif self.text_encoding == flver.TextEncoding.SHIFT_JIS:
            terminator = b"\0"
            encoding = "shift_jis"

        if offset is not None:
            position = self.fp.tell()
            self.fp.seek(offset, 0)
        raw_string = bytearray()
        while True:
            char = self.fp.read(len(terminator))
            if char == terminator:
                break
            raw_string.extend(char)
        result = raw_string.decode(encoding=encoding)
        if offset is not None:
            self.fp.seek(position, 0)
        return result


def read_dummy(reader, header):
    data = deque(reader.read_struct("fffBBBBfffHhfffh??IIII"))

    position = (data.popleft(), data.popleft(), data.popleft())

    # Upstream is uncertain about RGB ordering
    if header.version == 0x20010:
        b = data.popleft()  # B
        g = data.popleft()  # B
        r = data.popleft()  # B
        a = data.popleft()  # B
    else:
        a = data.popleft()  # B
        r = data.popleft()  # B
        g = data.popleft()  # B
        b = data.popleft()  # B
    color = (r, g, b, a)

    forward = (data.popleft(), data.popleft(), data.popleft())  # fff
    reference_id = data.popleft()  # H
    parent_bone_index = data.popleft()  # h
    upward = (data.popleft(), data.popleft(), data.popleft())  # fff
    attach_bone_index = data.popleft()  # h
    flag1 = data.popleft()  # ?
    use_upward_vector = data.popleft()  # ?
    unk30 = data.popleft()  # I
    unk34 = data.popleft()  # I
    assert data.popleft() == 0  # I
    assert data.popleft() == 0  # I

    return flver.Dummy(
        position=position,
        color=color,
        forward=forward,
        reference_id=reference_id,
        parent_bone_index=parent_bone_index,
        upward=upward,
        attach_bone_index=attach_bone_index,
        flag1=flag1,
        use_upward_vector=use_upward_vector,
        unk30=unk30,
        unk34=unk34,
    )


def read_material(reader):
    data = deque(reader.read_struct("IIIIIIII"))

    name = reader.read_string(data.popleft())  # I
    mtd_path = reader.read_string(data.popleft())  # I
    texture_count = data.popleft()  # I
    texture_index = data.popleft()  # I
    flags = data.popleft()  # I
    data.popleft()  # TODO: gx offset (I)
    unk18 = data.popleft()  # I
    assert data.popleft() == 0  # I

    return flver.Material(
        name=name,
        mtd_path=mtd_path,
        texture_count=texture_count,
        texture_index=texture_index,
        flags=flags,
        unk18=unk18,
    )


def read_bone(reader):
    data = deque(reader.read_struct("fffIfffhhfffhhfffIfff"))

    translation = (data.popleft(), data.popleft(), data.popleft())  # fff
    name = reader.read_string(data.popleft())  # I
    rotation = (data.popleft(), data.popleft(), data.popleft())  # fff
    parent_index = data.popleft()  # h
    child_index = data.popleft()  # h
    scale = (data.popleft(), data.popleft(), data.popleft())  # fff
    next_sibling_index = data.popleft()  # h
    previous_sibling_index = data.popleft()  # h
    bounding_box_min = (data.popleft(), data.popleft(), data.popleft())  # fff
    unk3C = data.popleft()  # I
    bounding_box_max = (data.popleft(), data.popleft(), data.popleft())  # fff
    assert reader.read(0x34) == b"\0" * 0x34

    return flver.Bone(
        translation=translation,
        name=name,
        rotation=rotation,
        parent_index=parent_index,
        child_index=child_index,
        scale=scale,
        next_sibling_index=next_sibling_index,
        previous_sibling_index=previous_sibling_index,
        bounding_box_min=bounding_box_min,
        unk3C=unk3C,
        bounding_box_max=bounding_box_max,
    )


def read_mesh(reader):
    data = deque(reader.read_struct("BBBBIIIIIIIIIII"))

    dynamic_mode = flver.Mesh.DynamicMode(data.popleft())  # B
    assert data.popleft() == 0  # B
    assert data.popleft() == 0  # B
    assert data.popleft() == 0  # B
    material_index = data.popleft()  # I
    assert data.popleft() == 0  # I
    assert data.popleft() == 0  # I
    default_bone_index = data.popleft()  # I
    bone_count = data.popleft()  # I
    bounding_offset = data.popleft()  # TODO: bounding box offset (I)
    bone_offset = data.popleft()  # I
    index_buffer_count = data.popleft()  # I
    index_buffer_offset = data.popleft()  # I
    vertex_buffer_count = data.popleft()  # I
    assert vertex_buffer_count in {1, 2, 3}
    vertex_buffer_offset = data.popleft()  # I

    bone_count = default_bone_index # In DS3+ this seems to be necessary to import rigs, however it is inconsistent.
    # TODO: Find more robust method for DS3+ rigs.
    

    bone_indices = reader.read_struct("I" * bone_count, bone_offset)
    index_buffer_indices = reader.read_struct("I" * index_buffer_count,
                                              index_buffer_offset)
    vertex_buffer_indices = reader.read_struct("I" * vertex_buffer_count,
                                               vertex_buffer_offset)

    return flver.Mesh(
        dynamic_mode=dynamic_mode,
        material_index=material_index,
        default_bone_index=default_bone_index,
        bone_indices=bone_indices,
        index_buffer_indices=index_buffer_indices,
        vertex_buffer_indices=vertex_buffer_indices,
    )


def read_index_buffer(reader, header, data_offset):
    data = deque(reader.read_struct("IBBHII"))

    detail_flags = set()
    detail_binary_flags = data.popleft()  # I
    for flag in flver.IndexBuffer.DetailFlags:
        if (detail_binary_flags & flag.value) != 0:
            detail_flags.add(flag)

    primitive_mode = flver.IndexBuffer.PrimitiveMode(data.popleft())  # B
    backface_visibility = flver.IndexBuffer.BackfaceVisibility(
        data.popleft())  # B
    unk06 = data.popleft()
    index_count = data.popleft()  # I
    indices_offset = data.popleft()  # I

    index_size = 0
    if header.version > 0x20005:
        additional_data = deque(reader.read_struct("IIII"))
        assert additional_data.popleft() >= 0  # indices length (I)
        assert additional_data.popleft() == 0  # I
        index_size = additional_data.popleft()  # I
        assert index_size in {0, 16, 32}
        assert additional_data.popleft() == 0  # I
    if index_size == 0:
        index_size = header.default_vertex_index_size

    if index_size == 16:
        indices = reader.read_struct("H" * index_count,
                                     data_offset + indices_offset)
    elif index_size == 32:
        indices = reader.read_struct("I" * index_count,
                                     data_offset + indices_offset)

    return flver.IndexBuffer(
        detail_flags=detail_flags,
        primitive_mode=primitive_mode,
        backface_visibility=backface_visibility,
        unk06=unk06,
        indices=indices,
    )


def read_vertex_buffer(reader, data_offset):
    data = deque(reader.read_struct("IIIIIIII"))

    buffer_index = data.popleft()  # I
    struct_index = data.popleft()  # I
    struct_size = data.popleft()  # I
    vertex_count = data.popleft()  # I
    assert data.popleft() == 0  # I
    assert data.popleft() == 0  # I
    buffer_length = data.popleft()  # I
    buffer_offset = data.popleft()  # I

    # Read buffer data
    buffer_data = reader.read(buffer_length, data_offset + buffer_offset)

    return flver.VertexBuffer(
        buffer_index=buffer_index,
        struct_index=struct_index,
        struct_size=struct_size,
        vertex_count=vertex_count,
        buffer_data=buffer_data,
    )


def read_vertex_buffer_struct_member(reader, struct_offset):
    data = deque(reader.read_struct("IIIII"))

    unk00 = data.popleft()  # I
    assert data.popleft() == struct_offset
    data_type = flver.VertexBufferStructMember.DataType(data.popleft())  # I
    attribute_type = flver.VertexBufferStructMember.AttributeType(
        data.popleft())  # I
    index = data.popleft()  # I

    return flver.VertexBufferStructMember(
        unk00=unk00,
        struct_offset=struct_offset,
        data_type=data_type,
        attribute_type=attribute_type,
        index=index,
    )


def read_vertex_buffer_structs(reader):
    data = deque(reader.read_struct("IIII"))

    member_count = data.popleft()  # I
    assert data.popleft() == 0  # I
    assert data.popleft() == 0  # I
    member_offset = data.popleft()  # I

    position = reader.tell()
    reader.seek(member_offset)

    struct_offset = 0
    result = []
    for _ in range(member_count):
        member = read_vertex_buffer_struct_member(reader, struct_offset)
        struct_offset += member.size()
        result.append(member)

    reader.seek(position)
    return result


def read_texture(reader):
    data = deque(reader.read_struct("IIffB?BBfff"))

    path = reader.read_string(data.popleft())  # I
    type_name = reader.read_string(data.popleft())  # I
    scale = (data.popleft(), data.popleft())  # ff
    unk10 = data.popleft()  # B
    assert unk10 in {0, 1, 2}
    unk11 = data.popleft()  # ?
    assert data.popleft() == 0  # B
    assert data.popleft() == 0  # B
    unk14 = data.popleft()  # f
    unk18 = data.popleft()  # f
    unk1C = data.popleft()  # f

    return flver.Texture(
        path=path,
        type_name=type_name,
        scale=scale,
        unk10=unk10,
        unk11=unk11,
        unk14=unk14,
        unk18=unk18,
        unk1C=unk1C,
    )


def read_flver(file_name):
    with open(file_name, 'rb') as fp:
        reader = StructReader(fp)

        # Read until endianness
        data = deque(reader.read_struct("6s2s"))
        assert data.popleft() == b"FLVER\0"
        endianness = flver.Endianness(data.popleft())
        reader.endianness = endianness

        data = deque(
            reader.read_struct("IIIIIIIIffffffIIBB?BIIIIBBBBIIIIIIII"))
        # Gundam Unicorn: 0x20005, 0x2000E
        # DS1: 2000C, 2000D
        # DS2 NT: 2000F, 20010
        # DS2: 20010, 20009 (armor 9320)
        # SFS: 20010
        # BB:  20013, 20014
        # DS3: 20013, 20014
        # SDT: 2001A, 20016 (test chr)
        version = data.popleft()  # I
        assert version in {
            0x20005, 0x20009, 0x2000C, 0x2000D, 0x2000E, 0x2000F, 0x20010,
            0x20013, 0x20014, 0x20016, 0x2001A
        }

        data_offset = data.popleft()  # I
        assert data.popleft() >= 0  # data length (I)
        dummy_count = data.popleft()  # I
        material_count = data.popleft()  # I
        bone_count = data.popleft()  # I
        mesh_count = data.popleft()  # I
        vertex_buffer_count = data.popleft()  # I

        # fff
        bounding_box_min = (data.popleft(), data.popleft(), data.popleft())
        # fff
        bounding_box_max = (data.popleft(), data.popleft(), data.popleft())

        assert data.popleft() >= 0  # Face count of main mesh (I)
        assert data.popleft() >= 0  # Total face count of all meshes (I)

        default_vertex_index_size = data.popleft()  # B
        assert default_vertex_index_size in {0, 16, 32}
        text_encoding = flver.TextEncoding(data.popleft())  # B
        reader.text_encoding = text_encoding
        unk4A = data.popleft()  # ?
        assert data.popleft() == 0  # B

        unk4C = data.popleft()  # I
        index_buffer_count = data.popleft()  # I
        vertex_buffer_struct_count = data.popleft()  # I
        texture_count = data.popleft()  # I

        unk5C = data.popleft()  # B
        unk5D = data.popleft()  # B
        assert data.popleft() == 0  # B
        assert data.popleft() == 0  # B

        assert data.popleft() == 0  # I
        assert data.popleft() == 0  # I
        unk68 = data.popleft()  # I
        assert unk68 in {0, 1, 2, 3, 4}
        assert data.popleft() == 0
        assert data.popleft() == 0
        assert data.popleft() == 0
        assert data.popleft() == 0
        assert data.popleft() == 0

        header = flver.Header(
            endianness=endianness,
            version=version,
            bounding_box_min=bounding_box_min,
            bounding_box_max=bounding_box_max,
            default_vertex_index_size=default_vertex_index_size,
            text_encoding=text_encoding,
            unk4A=unk4A,
            unk4C=unk4C,
            unk5C=unk5C,
            unk5D=unk5D,
            unk68=unk68,
        )

        dummies = []
        for _ in range(dummy_count):
            dummies.append(read_dummy(reader, header))
        materials = []
        for _ in range(material_count):
            materials.append(read_material(reader))
        bones = []
        for _ in range(bone_count):
            bones.append(read_bone(reader))
        meshes = []
        for _ in range(mesh_count):
            meshes.append(read_mesh(reader))
        index_buffers = []
        for _ in range(index_buffer_count):
            index_buffers.append(read_index_buffer(reader, header,
                                                   data_offset))
        vertex_buffers = []
        for _ in range(vertex_buffer_count):
            vertex_buffers.append(read_vertex_buffer(reader, data_offset))
        vertex_buffer_structs = []
        for _ in range(vertex_buffer_struct_count):
            vertex_buffer_structs.append(read_vertex_buffer_structs(reader))
        textures = []
        for _ in range(texture_count):
            textures.append(read_texture(reader))
        # Ignore unknown Sekiro struct for now

    return flver.Flver(
        header=header,
        dummies=dummies,
        materials=materials,
        bones=bones,
        meshes=meshes,
        index_buffers=index_buffers,
        vertex_buffers=vertex_buffers,
        vertex_buffer_structs=vertex_buffer_structs,
        textures=textures,
    )