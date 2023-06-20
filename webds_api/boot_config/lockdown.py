class LockdownStructure:
    def __init__(self, data):
        self.data = data

    def get_value(self, offset):
        offset_a = offset[0]
        offset_b = offset[1]
        if offset_a < 0 or offset_b >= len(self.data) * 8 or offset_a > offset_b:
            raise ValueError("Invalid offset range")

        byte_start = offset_a // 8
        bit_start = offset_a % 8
        byte_end = offset_b // 8
        bit_end = offset_b % 8

        if byte_start == byte_end:
            value = (self.data[byte_start] >> bit_start) & ((1 << (bit_end - bit_start + 1)) - 1)
        else:
            value = (self.data[byte_start] >> bit_start)
            for i in range(byte_start + 1, byte_end):
                value = (value << 8) | self.data[i]
            value = (value << (bit_end + 1)) | (self.data[byte_end] & ((1 << (bit_end + 1)) - 1))

        return value

    def set_value(self, value, offset):
        offset_a = offset[0]
        offset_b = offset[1]
        if offset_a < 0 or offset_b >= len(self.data) * 8 or offset_a > offset_b:
            raise ValueError("Invalid offset range")

        byte_start = offset_a // 8
        bit_start = offset_a % 8
        byte_end = offset_b // 8
        bit_end = offset_b % 8

        if byte_start == byte_end:
            mask = ((1 << (bit_end - bit_start + 1)) - 1) << bit_start
            self.data[byte_start] &= ~mask  # Clear bits within the range
            self.data[byte_start] |= (value << bit_start) & mask  # Set new value
        else:
            self.data[byte_start] &= (1 << bit_start) - 1  # Clear bits from start position
            self.data[byte_start] |= value >> (bit_end + 1 - bit_start)  # Set bits from start position

            for i in range(byte_start + 1, byte_end):
                self.data[i] = value & 0xFF  # Set full byte value

            self.data[byte_end] &= ~((1 << (bit_end + 1)) - 1)  # Clear bits up to end position
            self.data[byte_end] |= value & ((1 << (bit_end + 1)) - 1)  # Set bits up to end position

    def get_byte_array(self):
        return self.data

    def get_lockdown_struct(protocol):
        lockdown_arr = []
        if protocol == "spi":
            lockdown_arr.append(["cpha", [0, 0]])
            lockdown_arr.append(["cpol", [1, 1]])
        elif protocol == "i2c":
            lockdown_arr.append(["address", [0, 6]])
        lockdown_arr.append(["enable", [7, 7]])
        lockdown_arr.append(["pin", [8, 11]])
        lockdown_arr.append(["polarity", [12, 12]])
        lockdown_arr.append(["drive", [13, 13]])
        lockdown_arr.append(["pullup", [14, 14]])
        lockdown_arr.append(["nonempty", [15, 15]])
        lockdown_arr.append(["flash_wp_enable", [32, 32]])
        lockdown_arr.append(["high_range_guarding", [33, 33]])
        return lockdown_arr

    def set_lockdown(self, data, protocol):
        lockdown_arr = LockdownStructure.get_lockdown_struct(protocol)

        for element in lockdown_arr:
            try:
                print(element[0], element[1])
                self.set_value(data[element[0]], element[1])
            except Exception as e:
                print("Error", str())
                pass

    def get_lockdown(self, protocol):
        lockdown_arr = LockdownStructure.get_lockdown_struct(protocol)

        data = {}
        for element in lockdown_arr:
            print(element[0], element[1])
            value = self.get_value(element[1])
            data[element[0]] = value
        return data