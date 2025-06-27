# Dual-core memory hierarchy simulation - Complete version

import utime
from machine import Pin, I2C
import _thread
import gc

# Import existing modules
import lib.OLED as OLED
from lib.EEPROM import read_last_value, write_to_eeprom
from lib.Sensor import read_voltage_mq2, read_voltage_mq7, calculate_ppm
from lib.ds18x20 import DS18X20
import onewire
import math

# System initialization
i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=400000)
OLED.OLED_init(i2c)
OLED.OLED_clear(i2c)

# Temperature sensor DS18B20
ds_pin = Pin(16)
ds_sensor = DS18X20(onewire.OneWire(ds_pin))
ds_roms = ds_sensor.scan()

# Button GPIO15
button = Pin(15, Pin.IN, Pin.PULL_UP)

# Address mapping
ADDR_TEMP = 0x10
ADDR_MQ2  = 0x11
ADDR_MQ7  = 0x12
ADDR_LIST = [ADDR_TEMP, ADDR_MQ2, ADDR_MQ7]
NAME_MAP = {
    ADDR_TEMP: "TEMP",
    ADDR_MQ2:  "MQII", 
    ADDR_MQ7:  "MQIV"
}

# EEPROM storage configuration (4 slots per sensor)
EEPROM_SLOTS = {
    ADDR_TEMP: [84, 85, 86, 87],  # Temperature sensor
    ADDR_MQ2: [0, 1, 2, 3],       # MQ2 sensor
    ADDR_MQ7: [42, 43, 44, 45]    # MQ7 sensor
}
write_pointers = {ADDR_TEMP: 0, ADDR_MQ2: 0, ADDR_MQ7: 0}  # FIFO pointers
eeprom_ttl = {}  # {addr: {"timestamp": int, "value": float}}

# Global cache chain + precise time synchronization
CACHE_SIZE = 2
TTL_MS = 600
GC_INTERVAL = 10  # Run GC every 10 loops
PRINT_INTERVAL = 5  # Print memory every 5 loops
loop_count = 0  # Loop counter
cache = {}
cache_lock = _thread.allocate_lock()
eeprom_lock = _thread.allocate_lock()

# Sensor reading wrapper
def read_temperature():
    ds_sensor.convert_temp()
    utime.sleep_ms(50)  # Optimization: reduced from 750ms to 500ms
    return ds_sensor.read_temp(ds_roms[0]) if (ds_sensor.read_temp(ds_roms[0])>0) else None

def read_sensor(addr):
    if addr == ADDR_TEMP:
        return read_temperature()
    elif addr == ADDR_MQ2:
        return calculate_ppm(read_voltage_mq2(), "MQ2")
    elif addr == ADDR_MQ7:
        return calculate_ppm(read_voltage_mq7(), "MQ7")
   

# EEPROM write wrapper

def eeprom_write(addr, value):
    with eeprom_lock:
        current_time = utime.ticks_ms()
        
        # 1. Check for expired slots in memory records
        for i, page in enumerate(EEPROM_SLOTS[addr]):
            if addr in eeprom_ttl and \
               utime.ticks_diff(current_time, eeprom_ttl[addr]["timestamp"]) > TTL_MS:
                # Overwrite this expired slot
                write_to_eeprom(page, i, value)
                write_pointers[addr] = (i + 1) % 4
                break
        else:
            # 2. No expired slots, use FIFO
            ptr = write_pointers[addr]
            page = EEPROM_SLOTS[addr][ptr]
            write_to_eeprom(page, ptr, value)
            write_pointers[addr] = (ptr + 1) % 4

        # Update memory record
        eeprom_ttl[addr] = {
            "timestamp": current_time,
            "value": value
        }

# Cache management

def update_cache(addr, value):
    if len(cache) >= CACHE_SIZE:
        oldest = min(cache.items(), key=lambda x: x[1]['last_used'])[0]
        del cache[oldest]
    cache[addr] = {'value': value, 'last_used': utime.ticks_ms()}

def check_ttl(addr):
    entry = cache.get(addr)
    if entry and utime.ticks_diff(utime.ticks_ms(), entry['last_used']) > TTL_MS:
        del cache[addr]

# EEPROM read wrapper

def eeprom_read(addr):
    if addr in NAME_MAP:
        with eeprom_lock:
            # First check memory TTL
            if addr in eeprom_ttl:
                entry = eeprom_ttl[addr]
                if utime.ticks_diff(utime.ticks_ms(), entry["timestamp"]) < TTL_MS:
                    return entry["value"]
            
            # Read latest data from EEPROM (using same ptr calculation)
            ptr = (write_pointers[addr] - 1) % 4
            return read_last_value(NAME_MAP[addr], offset=ptr)
    return None

# Unified read interface

total_access, cache_hits, eeprom_hits = 0, 0, 0

def format_timestamp(ticks):
    sec, ms = divmod(ticks, 1000)
    t = utime.localtime(sec)
    return "{}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}.{:03d}".format(
        t[0], t[1], t[2], t[3], t[4], t[5], ms)

def show_memory_layout():
    print("\n=== Memory Layout ===")
    print("[Cache]")
    for addr, entry in cache.items():
        print(f"{NAME_MAP[addr]}: {entry['value']} (last: {entry['last_used']%1000}ms)")
    
    print("\n[EEPROM Pointers]")
    for addr in ADDR_LIST:
        print(f"{NAME_MAP[addr]}: slot={write_pointers[addr]}")
    print("=====================")

def request_data(addr):
    global total_access, cache_hits, eeprom_hits
    total_access += 1
    check_ttl(addr)

    with cache_lock:
        if addr in cache:
            cache[addr]['last_used'] = utime.ticks_ms()
            cache_hits += 1
            return cache[addr]['value'], "Cache", cache[addr]['last_used']

    val = eeprom_read(addr)
    if val is not None and not (isinstance(val, float) and math.isnan(val)):
        with cache_lock:
            update_cache(addr, val)
        eeprom_hits += 1
        return val, "EEPROM", eeprom_ttl[addr]["timestamp"]

    val = read_sensor(addr)
    timestamp = utime.ticks_ms()
    eeprom_write(addr, val)
    with cache_lock:
        update_cache(addr, val)
    return val, "Sensor", timestamp

# Secondary core data collection thread

def sensor_loop():
    while True:
        for addr in ADDR_LIST:
            val = read_sensor(addr)
            if(val is not None):
             eeprom_write(addr, val)
             update_cache(addr, val)
        utime.sleep(0.8)  # Optimization: reduced from 1s to 0.8s

_thread.start_new_thread(sensor_loop, ())

# -------- Main loop --------
# Initialize log file
log_file = open('sensor_log.txt', 'a')

def print_memory():
    alloc = gc.mem_alloc()
    free = gc.mem_free()
    print(f"[MEM] Used:{alloc}B Free:{free}B Usage:{alloc/(alloc+free)*100:.1f}%")
current_idx = 0
last_btn = button.value()
OLED.OLED_clear(i2c)
OLED.OLED_frame(i2c,OLED.UI)
last_values={}
while True:
    loop_count += 1
    
    # Scheduled GC and memory printing
    if loop_count % GC_INTERVAL == 0:
        gc.collect()
    if loop_count % PRINT_INTERVAL == 0:
        print_memory()
        
    btn = button.value()
    if last_btn == 1 and btn == 0:
        current_idx = (current_idx + 1) % len(ADDR_LIST)
        OLED.OLED_arrow_movement(i2c)
    last_btn = btn

    # Automatically update current selected sensor data every second
    addr = ADDR_LIST[current_idx]
    label = NAME_MAP[addr]
    start_time = utime.ticks_ms()
    value, level, data_time = request_data(addr)
    
    if value != last_values.get(addr):
     OLED.OLED_word_write(i2c, label)
     OLED.OLED_num_write(i2c, value)
   
    last_values[addr] = value
    
    elapsed = utime.ticks_diff(utime.ticks_ms(), start_time)
    hit_rate = (cache_hits + eeprom_hits) / total_access * 100
    cache_hits_rate=cache_hits / total_access*100
    eeprom_hits_rate=eeprom_hits/total_access*100
    
    time_str = format_timestamp(data_time)
    log_line = "[{}] {} = {:.2f} | Source: {} @ {} | Hit Rate: {:.2f}%|Cache Hit Rate: {:.2f}% |EEPROM Hit Rate: {:.2f}%| Latency: {} ms".format(
        total_access, label, value, level, time_str, hit_rate,cache_hits_rate,eeprom_hits_rate, elapsed)
    print(log_line)
    #show_memory_layout()
    utime.sleep_ms(510)
