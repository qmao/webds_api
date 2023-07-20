import zlib


class ImageParser:
    def __init__(self, fileName):
        self._fileName = fileName
        with open(fileName, mode='rb') as file: # b is important -> binary
            self._fileContent = file.read()

    def le2int(data):
        return int.from_bytes(data, byteorder="little")


    def int2le(data, num_bytes):
        return list(data.to_bytes(num_bytes, "little"))

    def calculate_crc32(data):
        crc32 = zlib.crc32(data)
        return crc32

    def checkHeader(self):
        ##hexFormat = ' '.join(hex(byte) for byte in fileContentRange)
        identifier = ImageParser.le2int(self._fileContent[0: 4])
        if identifier != 0x4818472B:
            print("INVALID IMAGE FILE. identifier:", identifier)
            return False
        else:
            print(hex(identifier))
            return True

    def getNumberOfMemoryAreas(self):
        count = ImageParser.le2int(self._fileContent[4: 8])
        return count

    def getMemoryAreaList(self):
        count = self.getNumberOfMemoryAreas()
        alist = []
        for number in range(count):
            start = 8 + 4*number
            offset = ImageParser.le2int(self._fileContent[start : start + 4])
            area = {}
            area["id"] = bytes(self._fileContent[offset + 4 : offset + 20]).decode('utf-8', errors='ignore').strip()
            area["identifier"] = hex(ImageParser.le2int(self._fileContent[offset : offset + 4]))
            area["flag"] = ImageParser.le2int(self._fileContent[offset + 20 : offset + 24])
            area["address"] = hex(ImageParser.le2int(self._fileContent[offset + 24 : offset + 28]))
            area["length"] = ImageParser.le2int(self._fileContent[offset + 28 : offset + 32])
            area["offset"] = offset
            area["crc"] = hex(ImageParser.le2int(self._fileContent[offset + 32 : offset + 36]))

            ##data = self._fileContent[offset + 36 : offset + 36 + area["length"]]
            ##crc = ImageParser.calculate_crc32(data)
            ##print("CRC:", hex(crc))

            alist.append(area)
        return alist
