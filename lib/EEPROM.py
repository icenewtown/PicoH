from machine import Pin, I2C
import time, struct

# ---------- Parameter definitions ----------
EEPROM_ADDR = 0x50  # AT24C32 I2C address
i2c = I2C(1, scl=Pin(3), sda=Pin(2), freq=100000)

eeprom_next_addr = 0  # Write address pointer
PAGE_SIZE = 32
TOTAL_PAGES = 128

# ---------- Data storage locations ----------
# Page ranges for storage
mq2_page = 0
mq2_offset = 0
mq7_page = 42
mq7_offset = 0
therm_page = 84
therm_offset = 0

# ---------- EEPROM write operations ----------
def eeprom_write_bytes(addr, data):
    for i in range(len(data)):
        a = addr + i
        high = (a >> 8) & 0xFF
        low = a & 0xFF
        i2c.writeto(EEPROM_ADDR, bytes([high, low, data[i]]))
        time.sleep_ms(5)

def write_to_eeprom(page_num, offset, data):
    """Write data to EEPROM, automatically managing page and offset"""
    base_addr = page_num * PAGE_SIZE + offset
    packed = struct.pack('f', data)
    eeprom_write_bytes(base_addr, packed)
    offset += 4
    if offset >= PAGE_SIZE:
        offset = 0
        page_num += 1
    return page_num, offset

def save_data(value, sensor_type):
    """Automatically determine storage location based on sensor type"""
    global mq2_page, mq2_offset, mq7_page, mq7_offset, therm_page, therm_offset

    if sensor_type == 'MQ2':
        mq2_page, mq2_offset = write_to_eeprom(mq2_page, mq2_offset, value)
    elif sensor_type == 'MQ7':
        mq7_page, mq7_offset = write_to_eeprom(mq7_page, mq7_offset, value)
    elif sensor_type == 'ds18x20':
        therm_page, therm_offset = write_to_eeprom(therm_page, therm_offset, value)

def read_last_value(sensor_type, offset=0):
    """Read last valid float data of specified sensor type from EEPROM"""
    if sensor_type == "MQII":
        addr = 0 * PAGE_SIZE + offset * 4
    elif sensor_type == "MQIV":
        addr = 42 * PAGE_SIZE + offset * 4
    elif sensor_type == "TEMP":
        addr = 84 * PAGE_SIZE + offset * 4
    else:
        return None

    try:
        high = (addr >> 8) & 0xFF
        low = addr & 0xFF
        i2c.writeto(EEPROM_ADDR, bytes([high, low]))
        raw = i2c.readfrom(EEPROM_ADDR, 4)
        if raw != b'\xFF\xFF\xFF\xFF' and raw != b'\x00\x00\x00\x00':
            return struct.unpack('f', raw)[0]
    except:
        return None
    return None  # No valid value found
