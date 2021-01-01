import os
from os.path import isfile, join

class TPF:   
    """
    A container for texture files.
    """
    def __init__(self, tpf_path):
         
        self.tpf_path = tpf_path
        self.textures = []
        self.data = open(self.tpf_path, "rb")
        self.file_path = self.tpf_path[:-4]

    def unpack(self):
        """
        Unpackes the textures files and appends them to self.textures
        """
    
        signature = self.data.read(4)
        net_size = int32(self.data.read(4))
        texture_count = int32(self.data.read(4))

        version = self.data.read(1)
        flag2 = self.data.read(1)
        encoding = self.data.read(1)
        flag3 = self.data.read(1)
        

        for i in range(texture_count):
            data_offset = int32(self.data.read(4))
            data_size = int32(self.data.read(4))
            format = self.data.read(1)
            is_cube_map = self.data.read(1)
            mipmap_count = self.data.read(1)
            flags = self.data.read(1)

            # Changes here depending on game type
            is_bloodborne = False
            if is_bloodborne:
                width = self.data.read(2)
                height = self.data.read(2)
                self.data.read(4)
                self.data.read(4)
                file_name_offset = int32(self.data.read(4))
                self.data.read(4)
                dxgi_format = self.data.read(4)

            else:
                file_name_offset = int32(self.data.read(4))
                unknown = self.data.read(4)

            position = self.data.tell()

            if file_name_offset > 0:
                self.data.seek(file_name_offset)

            if data_offset > 0:
                self.data.seek(data_offset)
                result = self.data.read(data_size)

            self.data.seek(position)
  
            self.textures.append(result)

    def save_textures_to_file(self):
        print("Writing {} textures to {}".format(len(self.textures), self.file_path + "_textures\\"))
        os.mkdir(self.file_path + "_textures\\")

        for i in range(len(self.textures)):
            with open(self.file_path + "_textures\\" + str(i) + ".dds", "wb") as file:
                file.write(self.textures[i])

    def read_null_terminated_string(self):
        buffer = b""
        while True:
            byte = self.data.read(1)
            if byte == b'' or byte == b'\x00':
                break
            buffer += byte
        try:
            return buffer.decode("shift_jis")
        except UnicodeDecodeError as e:
            raise e


def unpack_all(tpf_path):
    """
    Unpacks all tpf files in the tpf_path directory
    """

    files = [f for f in listdir(tpf_path) if isfile(join(tpf_path, f))]
    for file in files:
        tpf = TPF(tpf_path + file)
        tpf.unpack()
        tpf.save_textures_as_png()
    


def int32(data):
    return int.from_bytes(data, byteorder= "little", signed = False)


if __name__ == "__main__":
    tpf = TPF("E:\\Projects\\test\\c5110.tpf")
    tpf.unpack()
    tpf.save_textures_to_file()