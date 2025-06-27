# ds18x20.py
import time, onewire
from machine import Pin

buzz=Pin(11,Pin.OUT,Pin.PULL_UP)

class DS18X20:
    def __init__(self, onewire):
        self.ow = onewire

    def scan(self):
        return [rom for rom in self.ow.scan() if rom[0] == 0x28]

    def convert_temp(self):
        self.ow.reset()
        self.ow.writebyte(0xCC)  # Skip ROM
        self.ow.writebyte(0x44)  # Convert Temp

    def read_scratch(self, rom):
        self.ow.reset()
        self.ow.select_rom(rom)
        self.ow.writebyte(0xBE)  # Read Scratch
        buf = bytearray(9)
        self.ow.readinto(buf)  
        return buf

    def read_temp(self, rom):
        buf = self.read_scratch(rom)
        if buf[1] == 0:
            temp = buf[0]
        else:
            temp = buf[1] << 8 | buf[0]
        if temp & 0x8000:  # negative
            temp = -((temp ^ 0xffff) + 1)
        return temp / 16

def Buzzer(switch):
    if switch == 0 or switch==1:
     buzz.value(switch)
    else:
        raise ValueError("switch should be 0 or 1")
    