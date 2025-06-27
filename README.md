# PicoH Memory Simulation Project  
# PicoH 存储系统模拟项目

A dual-core memory hierarchy simulation system based on Raspberry Pi Pico H, integrating OLED display, EEPROM with FIFO + TTL logic, and temperature sensors.  
这是一个基于 Raspberry Pi Pico H 的双核内存层级模拟系统，集成了 OLED 显示屏、具备 FIFO 与 TTL 机制的 EEPROM 以及温度传感器模块。

---

## 📦 Features / 功能特色

- 🧠 Dual-core concurrency based on MicroPython  
  基于 MicroPython 的双核并行处理设计  
- 📺 SSD1306 OLED display support  
  支持 SSD1306 OLED 显示模块  
- 💾 EEPROM storage with FIFO + TTL eviction policy  
  采用 FIFO 与 TTL 的 EEPROM 存储模拟  
- 🌡️ DS18B20 temperature sensor integration  
  集成 DS18B20 温度传感器  
- 🔘 Physical button control for cache access  
  使用按键进行缓存数据读取与交互控制  

---

## 🔧 Hardware Requirements / 硬件要求

| Module 模块          | Model 型号            |
|---------------------|----------------------|
| MCU 微控制器        | Raspberry Pi Pico H  |
| OLED 显示屏         | SSD1306 (I2C, 128x64)|
| 温度传感器          | DS18B20              |
| EEPROM 存储器       | AT24C02 / AT24C04    |
| 控制按键            | 2 × Tactile buttons  |

---

## 🚀 Getting Started / 快速开始

### Upload Procedure / 上传步骤：

1. Flash MicroPython to your Pico H using [Thonny](https://thonny.org/)  
   使用 Thonny 烧录 MicroPython 到你的 Pico H  
2. Upload all `.py` files to the Pico using Thonny, `ampy`, or `mpremote`  
   使用 Thonny、`ampy` 或 `mpremote` 上传所有 `.py` 文件  
3. Connect the OLED, EEPROM, and DS18B20 according to your schematic  
   按照电路连接 OLED、EEPROM 和温度传感器  
4. Power on and observe the OLED screen for status  
   上电后在 OLED 显示屏上查看系统状态信息  

---

## 📁 Directory Structure / 目录结构

PicoH/
├── main.py # Main execution logic / 主程序入口
├── lib/ # Library folder / 驱动与模块库
│ ├── OLED.py # OLED display driver / OLED 显示驱动
│ ├── DS18x20.py # Temperature sensor driver / 温度传感器驱动
│ └── EEPROM.py # EEPROM access logic / EEPROM 存取逻辑
├── assets/ # (Optional) images or diagrams / 图片或电路图
├── README.md # Project description / 项目说明文件
└── LICENSE # Open-source license / 开源许可证

