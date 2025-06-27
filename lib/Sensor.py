
from time import sleep
from machine import Pin, I2C, ADC
import math

# ---------- Parameter Definitions ----------
Vc = 3.3             # Supply voltage (volts)
Rl = 1000.0     # Load resistance (ohms)
R0 = 2900.0
R0_mq2 = 22500.0    # Calibrated Rs value in clean air (ohms)
RO_mq7 = 15000.0
mq2_adc = ADC(Pin(26))  # GPIO26 (ADC0)
mq7_adc = ADC(Pin(27))  # GPIO27 (ADC1)


# ---------- Read Voltage & Calculate Concentration ----------
def read_voltage_mq2():
    """Read MQ2 sensor voltage"""
    raw = mq2_adc.read_u16()
    return raw * Vc / 65535.0

def read_voltage_mq7():
    """Read MQ7 sensor voltage"""
    raw = mq7_adc.read_u16()
    return raw * Vc / 65535.0


def calculate_ppm(Vrl, type):
    """Calculate PPM concentration from voltage reading"""
    if Vrl <= 0:
        return None
    
    Vrl = 2 * Vrl
    if type == "MQ2":
        Rs = ((5 - Vrl) * Rl) / Vrl
        ratio = Rs / R0_mq2
        ppm = math.pow(ratio / 11.5428, -1.526)
     
    elif type == "MQ7":
        Rs = ((5 - Vrl) * Rl) / Vrl
        ratio = Rs / RO_mq7
        ppm = math.pow(ratio / 22.07, -1.498)
    
    if ratio <= 0:
        return None
    
    return round(ppm, 2)

'''
Test code example:
while True:
    sleep(1)
    mq2 = read_voltage_mq2()
    print("MQ2 voltage:", mq2)
    mq7 = read_voltage_mq7()
    print("MQ7 voltage:", mq7)
    ppm_mq2 = calculate_ppm(mq2, "MQ2")
    ppm_mq7 = calculate_ppm(mq7, "MQ7")    
    print("MQ2 voltage:", mq2, "PPM:", ppm_mq2)
    print("MQ7 voltage:", mq7, "PPM:", ppm_mq7)  
'''
