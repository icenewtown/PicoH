# Dual-core memory hierarchy simulation - Revised with TTL Manager
import utime
from machine import Pin, I2C
import _thread

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

# EEPROM storage configuration
EEPROM_SLOTS = {
    ADDR_TEMP: [84, 85, 86, 87],
    ADDR_MQ2: [0, 1, 2, 3],
    ADDR_MQ7: [42, 43, 44, 45]
}
write_pointers = {ADDR_TEMP: 0, ADDR_MQ2: 0, ADDR_MQ7: 0}
eeprom_ttl = {}

# Cache parameters
CACHE_SIZE = 2
TTL_MS = 2000
TEST_MODE = False
current_ttl = 0
ttl_values = [500, 1000, 1500, 2000, 2500, 3000]
test_results = []
test_start_time = 0
cache = {}
cache_lock = _thread.allocate_lock()
eeprom_lock = _thread.allocate_lock()


def read_temperature():
    ds_sensor.convert_temp()
    utime.sleep_ms(50)
    return ds_sensor.read_temp(ds_roms[0]) if (ds_sensor.read_temp(ds_roms[0])>0) else None

def read_sensor(addr):
    if addr == ADDR_TEMP:
        return read_temperature()
    elif addr == ADDR_MQ2:
        return calculate_ppm(read_voltage_mq2(), "MQ2")
    elif addr == ADDR_MQ7:
        return calculate_ppm(read_voltage_mq7(), "MQ7")

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


def update_cache(addr, value):
    if len(cache) >= CACHE_SIZE:
        oldest = min(cache.items(), key=lambda x: x[1]['last_used'])[0]
        del cache[oldest]
    cache[addr] = {'value': value, 'last_used': utime.ticks_ms()}

def check_ttl(addr):
    entry = cache.get(addr)
    if entry and utime.ticks_diff(utime.ticks_ms(), entry['last_used']) > TTL_MS:
        del cache[addr]

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

total_access, cache_hits, eeprom_hits = 0, 0, 0

def format_timestamp(ticks):
    sec, ms = divmod(ticks, 1000)
    t = utime.localtime(sec)
    return "{}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}.{:03d}".format(
        t[0], t[1], t[2], t[3], t[4], t[5], ms)

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

def reset_counters():
    global cache_hits, eeprom_hits, total_access
    cache_hits = 0
    eeprom_hits = 0
    total_access = 0

def start_ttl_test():
    global TEST_MODE, test_start_time, current_ttl, TTL_MS
    TEST_MODE = True
    test_start_time = utime.ticks_ms()
    current_ttl = 0
    TTL_MS = ttl_values[current_ttl]
    print(f"\n=== Starting TTL Test ===\nFirst TTL: {TTL_MS}ms")

def next_ttl_test():
    global current_ttl, TTL_MS, test_start_time, current_idx
    cache_hit_rate = cache_hits / total_access * 100 if total_access > 0 else 0
    eeprom_hit_rate = eeprom_hits / total_access * 100 if total_access > 0 else 0
    test_results.append({
        'ttl': TTL_MS,
        'total_hit_rate': (cache_hits + eeprom_hits) / total_access * 100 if total_access > 0 else 0,
        'cache_hit_rate': cache_hit_rate,
        'eeprom_hit_rate': eeprom_hit_rate,
        'cache_hits': cache_hits,
        'eeprom_hits': eeprom_hits,
        'total_access': total_access,
        'sensor_name': NAME_MAP[ADDR_LIST[current_idx]],
        'sensor_addr': ADDR_LIST[current_idx]
    })
    current_idx = (current_idx + 1) % len(ADDR_LIST)
    if current_idx == 0:
        current_ttl += 1
    if current_ttl < len(ttl_values):
        TTL_MS = ttl_values[current_ttl]
        reset_counters()
        test_start_time = utime.ticks_ms()
        print(f"\nTesting {NAME_MAP[ADDR_LIST[current_idx]]} with TTL: {TTL_MS}ms")
        return False
    else:
        print("\n=== TTL Test Complete ===")
        print_results()
        return True

def print_results():
    print("\nTTL, Total Hit Rate (%), Cache Hit Rate (%), EEPROM Hit Rate (%), Cache Hits, EEPROM Hits, Total Accesses, Sensor, Address")
    for result in test_results:
        print(f"{result['ttl']}, {result['total_hit_rate']:.2f}, {result['cache_hit_rate']:.2f}, {result['eeprom_hit_rate']:.2f}, {result['cache_hits']}, {result['eeprom_hits']}, {result['total_access']}, {result['sensor_name']}, {hex(result['sensor_addr'])}")
    with open('ttl_test_results.csv', 'w') as f:
        f.write("TTL (ms),Total Hit Rate (%),Cache Hit Rate (%),EEPROM Hit Rate (%),Cache Hits,EEPROM Hits,Total Accesses,Sensor,Address\n")
        for result in test_results:
            f.write(f"{result['ttl']},{result['total_hit_rate']:.2f},{result['cache_hit_rate']:.2f},{result['eeprom_hit_rate']:.2f},{result['cache_hits']},{result['eeprom_hits']},{result['total_access']},{result['sensor_name']},{hex(result['sensor_addr'])}\n")
    print("\nResults saved to ttl_test_results.csv")

def sensor_loop():
       while True:
        for addr in ADDR_LIST:
            val = read_sensor(addr)
            if(val is not None):
             eeprom_write(addr, val)
             update_cache(addr, val)
        utime.sleep(0.8)  # Optimization: reduced from 1s to 0.8s


_thread.start_new_thread(sensor_loop, ())

log_file = open('sensor_log.txt', 'a')
current_idx = 0
last_switch_time = utime.ticks_ms()
sensor_duration = 10000  # 10 seconds

OLED.OLED_clear(i2c)
OLED.OLED_frame(i2c,OLED.UI)
start_ttl_test()
reset_counters()
OLED.OLED_clear(i2c)
last_values={}
while True:
    if utime.ticks_diff(utime.ticks_ms(), last_switch_time) >= sensor_duration:
        current_idx = (current_idx + 1) % len(ADDR_LIST)
        last_switch_time = utime.ticks_ms()
        next_ttl_test()

    addr = ADDR_LIST[current_idx]
    label = NAME_MAP[addr]
    start_time = utime.ticks_ms()
    value, level, _ = request_data(addr)  # Ignore returned timestamp
    
    # OLED display
    if value != last_values.get(addr):
        
     OLED.OLED_word_write(i2c, label)
     OLED.OLED_num_write(i2c, value)
   
    last_values[addr] = value

    # Calculate total time (including request and display time)
    current_time = utime.ticks_ms()
    elapsed = utime.ticks_diff(current_time, start_time)
    hit_rate = (cache_hits + eeprom_hits) / total_access * 100 if total_access > 0 else 0
    time_str = format_timestamp(current_time)  # Use current time as timestamp
    
    log_line = f"[{total_access}] {label} = {value:.2f} | Source: {level} @ {time_str} | Hit Rate: {hit_rate:.2f}% | Latency: {elapsed} ms"
    print(log_line)
    log_file.write(log_line + '\n')
    log_file.flush()

    if TEST_MODE and utime.ticks_diff(utime.ticks_ms(), test_start_time) > 30000:
        if next_ttl_test():
            TEST_MODE = False
            break
        else:
            last_switch_time = utime.ticks_ms()  # Reset switch time
    
    utime.sleep_ms(510)
