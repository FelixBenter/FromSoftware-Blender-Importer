import os
from os.path import isfile, join
import subprocess


class TPF:   
    """
    A container for texture files.
    """
    def __init__(self, tpf_path):
         
        self.tpf_path = tpf_path
        self.textures = []
        self.file_path = self.tpf_path[:-4]
        self.filenames = []

    def unpack(self):
        """
        Unpackes the textures files and appends them to self.textures
        """
        with open(self.tpf_path, "rb") as self.data:
            signature = self.data.read(4)  # ".TPF "
            net_file_size = int32(self.data.read(4))
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
                    self.filenames.append(self.read_double_null_terminated_string())

                if data_offset > 0:
                    self.data.seek(data_offset)
                    result = self.data.read(data_size)

                self.data.seek(position)
    
                self.textures.append(result)

    def save_textures_to_file(self, file_path):
        print("Writing {} textures to {}".format(len(self.textures), file_path + "_textures\\"))
        if not os.path.exists(file_path + "_textures\\"):
            os.mkdir(file_path + "_textures\\")

        for i in range(len(self.textures)):
            with open(file_path + "_textures\\" + self.filenames[i].rstrip() + ".dds", "wb") as file:
                file.write(self.textures[i])

    def read_double_null_terminated_string(self):
        """
        Dark souls 3 TPF file image names seem to be double null terminated.
        """
        buffer = b""
        prev_byte = b""
        while True:
            byte = self.data.read(1)
            if (byte == prev_byte == b'') or (byte == prev_byte == b'\x00'):
                break
            buffer += byte
            prev_byte = byte
        try:
            return buffer.decode("shift_jis").replace("\x00", "", -1) # Remove trailing null
        except UnicodeDecodeError as e:
            print("Failed to decode {}".format(buffer))
            raise e


def unpack_all(tpf_path):
    """
    Unpacks all tpf files in the tpf_path directory
    """
    files = [f for f in os.listdir(tpf_path) if isfile(join(tpf_path, f))]
    for file in files:
        tpf.unpack()
        tpf.save_textures_to_file()

def convert_to_png(tpf_path):
    """
    Invokes the DirectXTex texture converter executable to convert dds files
    in the directory to png files, then deletes the old dds file.
    """
    dds_files = [f for f in os.listdir(tpf_path) if isfile(join(tpf_path, f))]
    for dds_file in dds_files:
        sys_path = os.path.dirname(os.path.realpath(__file__))
        command = "{}\\texconv.exe {} -ft png -o {} -y".format(sys_path, tpf_path + dds_file, tpf_path)
        # I haven't been able to find a way to convert the dds files that DS3 uses from within python,
        # So currently this is the most consistent method, as texconv covers many versions of dds files.
        subprocess.run(command, shell = False, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        os.remove(tpf_path + dds_file)  

def int32(data):
    return int.from_bytes(data, byteorder= "little", signed = False)


if __name__ == "__main__":
    tpf_path = "E:\\Projects\\test\\c6210.tpf"
    tpf = TPF(tpf_path)
    tpf.unpack()
    tpf.save_textures_to_file()
    convert_to_png(tpf.file_path + "_textures\\")

