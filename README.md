# 光学头电源控制系统

一个基于 PyQt5 开发的光学头电源控制管理系统，支持多路电源的集中控制、数据采集、实时监测和自动化测试。

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![PyQt5](https://img.shields.io/badge/PyQt5-5.15+-green.svg)
![License](https://img.shields.io/badge/License-MPL%202.0-brightgreen.svg)


## 📋 功能特性

### 核心功能
- **多路电源控制**：支持长条电源、方形电源、GPP 三通道电源和 MU_N 多通道电源的同时控制
  - 长条电源（PSW系列）：单通道电压/电流控制
  - 方形电源（GPD3303S）：双通道电压/电流控制
  - GPP 电源：三通道电压/电流控制，CH3 固定 5A 输出
  - MU_N 电源：2~10 可变通道，通过 VISA 连接，支持硬件过压/过流保护阈值设置
- **串口/设备通信**：自动检测和管理多个电源设备的串口/VISA 连接
- **实时数据监测**：
  - 实时电压/电流显示
  - 动态曲线绘制
  - 数据采集间隔：100ms
- **数据管理**：
  - 自动保存采集数据为 CSV 格式
  - 支持 FTP 自动上传功能
  - 数据保存路径：`./电源采集数据/`

### 高级功能
- **TCP 服务器**：支持远程控制和数据交互
- **电压拉偏测试**：
  - 36V → 45V → 42V 自动测试
  - 精度：0.1V 步进
  - 支持远程 TCP 控制拉偏测试
- **安全保护**：
  - 电流/电压过载保护
  - 可配置软件保护阈值
  - MU_N 电源支持下发硬件过压/过流保护阈值
  - 过载触发时自动播放报警声（`报警声.wav`）
- **自动化操作**：
  - 自动连接串口
  - 自动输出控制
  - 批量数据采集
- **操作日志**：自动记录所有界面操作（按钮点击、输入框修改、下拉框选择等），日志保存于 `./操作日志/` 目录，按日期命名
- **版本更新检测**：启动时自动检测新版本，支持自动下载、替换并重启程序

## 🚀 快速开始

### 环境要求

- Python 3.6+
- Windows 10/11
- 支持的电源型号：
  - GPD3303S（方形电源）
  - PSW 系列（长条电源）
  - GPP 系列（三通道电源）
  - MU_N 系列（多通道电源，需安装 VISA 驱动）

### 安装依赖

```bash
pip install PyQt5
pip install pandas
pip install bitstring
pip install pyserial
```

如需使用 MU_N 电源，还需安装 VISA 驱动和对应 Python 包（如 `pyvisa`）。

### 运行程序

```bash
python gxtdy.py
```

或直接运行已打包的可执行文件（如果有）。

## ⚙️ 配置说明

### Auto_config.ini 配置文件

#### TCP 配置
```ini
[TCP]
ip = 127.0.0.1          # TCP服务器IP地址
port = 4070             # TCP服务器端口
auto_connect = True     # 是否自动连接
```

#### 串口配置
```ini
[Serial]
power_supply_square1 = COM    # 方形电源1串口
power_supply_square2 = COM    # 方形电源2串口
power_supply_long = COM       # 长条电源串口
power_supply_gpp = COM        # GPP电源串口/VISA地址
auto_connect = False          # 是否自动连接串口
auto_output = False           # 是否自动输出
```

#### 安全限制
```ini
[Safty]
current_limit1_ch1 = 100    # 方形电源1通道1电流限制(A)
current_limit1_ch2 = 100    # 方形电源1通道2电流限制(A)
current_limit5_ch1 = 100    # 长条电源电流限制(A)
```

#### MU_N 电源保护阈值（每个电源实例一个 Section）
```ini
[MU_N_LIMITS:电源名称]
voltage_1 = 100.000    # CH1 硬件保护电压阈值(V)
current_1 = 100.000    # CH1 硬件保护电流阈值(A)
voltage_2 = 100.000    # CH2 硬件保护电压阈值(V)
current_2 = 100.000    # CH2 硬件保护电流阈值(A)
# ... 按通道数依此类推
```

#### 附加功能
```ini
[Additional]
power_add = False     # 是否启用电源添加功能
power_del = False     # 是否启用电源删除功能
```

#### 更新检测
```ini
[Update]
enabled = False                 # 是否启用启动时更新检测
check_on_startup = True         # 启动时是否自动检查
manifest_url =                  # 远端更新清单地址，可填 http(s) 或共享盘/本地 json 路径
request_timeout = 3             # 检测超时时间（秒）
```

## 📖 使用说明

### 版本更新检测

1. 准备更新清单文件，格式可参考 `update_manifest.example.json`
2. 将清单放到 HTTP 地址、共享盘路径或本地路径
3. 在 `Auto_config.ini` 的 `[Update]` 中填写 `manifest_url` 并将 `enabled` 设为 `True`
4. 软件启动后会自动检测，若发现新版本会弹窗提示并可自动下载、替换并重启程序
5. 更新包目前支持 `.zip` 和 `.exe`，其中 `.exe` 替换仅适用于打包后的程序

### 手动操作流程

1. **连接电源**
   - 点击"刷新设备"按钮检测可用串口/VISA 设备
   - 选择对应的串口或 VISA 地址
   - 点击"打开连接"连接电源

2. **设置参数**
   - 输入目标电压值（V）
   - 输入目标电流值（A）
   - 点击"发送"按钮设置参数
   - 可使用"发送全部数据"一次性设置所有通道

3. **启动输出**
   - 点击"开始输出"按钮启动电源
   - 系统自动开始数据采集
   - 实时曲线显示电压/电流变化

4. **停止输出**
   - 点击"停止输出"按钮关闭电源
   - 采集数据自动保存到 CSV 文件

### 注意事项

⚠️ **重要提示**：
1. 在发送或开始任何保存采集工作之前，请务必先打开串口，并输出电源，可使用按键控制或命令控制
2. 发送性能测试前后指令前，请检查数据采集是否停止，否则电源返回的信息会出错，导致软件报错，不能保存
3. 请根据实际设备配置合理的电流/电压限制值，避免设备损坏

### 电压拉偏测试

长条电源支持自动电压拉偏功能：
- **降至36V**：从当前电压自动降至36V
- **升至45V**：从当前电压自动升至45V
- **回到42V**：从当前电压自动恢复到42V
- 步进精度：0.1V/秒
- 支持通过 TCP 远程触发拉偏测试

### MU_N 电源通道管理

MU_N 电源支持运行时动态增加通道：
- 初始通道数可在创建实例时指定（默认 3 个，最多 10 个）
- 点击"增加通道"可在不断开连接的情况下扩展通道数
- 每个通道独立设置电压/电流目标值及硬件保护阈值
- 保护阈值实时持久化到 `Auto_config.ini`

## 📁 项目结构

```
光学头电源控制/
├── gxtdy.py                    # 主程序入口
├── Auto_config.ini             # 配置文件
├── version.json                # 版本信息文件
├── power.ico                   # 程序图标
├── 报警声.wav                   # 过载报警音频
├── 使用方法.txt                 # 使用说明
├── 更新内容.csv                 # 版本更新记录
├── Projects/
│   └── 电源控制/
│       ├── UpperPC.py          # 主窗口控制
│       ├── 长条电源控制.py       # 长条电源（PSW）控制模块
│       ├── 方形电源控制.py       # 方形电源（GPD3303S）控制模块
│       ├── GPP电源控制.py       # GPP 三通道电源控制模块
│       ├── MU_N电源控制.py      # MU_N 多通道电源控制模块
│       ├── psw_xx_xx.py        # PSW 电源驱动
│       ├── gpd3303s.py         # GPD3303S 电源驱动
│       ├── gpp_xx_xx.py        # GPP 电源驱动
│       ├── mu_n_xx_xx.py       # MU_N 电源驱动（VISA）
│       ├── MyPlot.py           # 数据绘图模块
│       ├── FTP.py              # FTP 上传模块
│       ├── TCP.py              # TCP 通信模块
│       ├── TCPServer.py        # TCP 服务器
│       ├── alarm_player.py     # 声音报警模块
│       ├── operation_logger.py # 操作日志模块
│       ├── update_checker.py   # 版本更新检测模块
│       ├── update_installer.py # 版本更新安装模块
│       ├── version_control.py  # 版本信息管理模块
│       └── tool.py             # 工具函数
├── Utility/
│   └── MainWindow/
│       ├── MainWindow.py       # 主窗口UI
│       └── MainWindow.ui       # UI设计文件
└── 采集表格/                    # 测试数据模板
    ├── 前放测试.xlsx
    ├── 快反镜测试.xlsx
    ├── 性能测试前电流.xlsx
    └── ...
```

## 🔧 开发说明

### 技术栈
- **GUI框架**：PyQt5
- **数据处理**：pandas
- **串口通信**：pyserial
- **VISA 通信**：pyvisa（MU_N 电源）
- **绘图**：matplotlib（通过 MyPlot 封装）
- **多线程**：threading, multiprocessing

### 核心模块

#### 1. 长条电源控制 (LongPower)
```python
from Projects.电源控制.长条电源控制 import LongPower

power = LongPower("长条电源")
power.port_open()
power.V_set(42.0)
power.I_set(3.5)
power.output_open()
```

#### 2. 方形电源控制 (SquarePower)
```python
from Projects.电源控制.方形电源控制 import SquarePower

power = SquarePower("方形电源1")
power.V_set(1, 5.0)  # 通道1设置5V
power.I_set(1, 1.0)  # 通道1设置1A
```

#### 3. GPP 三通道电源控制 (GPPPower)
```python
from Projects.电源控制.GPP电源控制 import GPPPower

power = GPPPower("GPP电源")
power.port_open()
power.V_set(1, 42.0)   # CH1 设置 42V
power.I_set(2, 3.5)    # CH2 设置 3.5A
# CH3 电流固定，只能设置电压
power.V_set(3, 5.0)
```

#### 4. MU_N 多通道电源控制 (MUNPower)
```python
from Projects.电源控制.MU_N电源控制 import MUNPower

power = MUNPower("MU_N电源", channel_count=3)
power.port_open()
power.V_set(1, 5.0)             # CH1 设置 5V
power.I_set(1, 1.0)             # CH1 设置 1A
power.voltage_limit_set(1, 6.0) # CH1 硬件过压保护阈值 6V
power.limit_set(1, 2.0)         # CH1 硬件过流保护阈值 2A
power.add_channel()             # 动态增加通道
```

### 信号说明

- `sigInfo`：信息提示信号
- `start_signal`：启动信号
- `current_warn`：电流报警信号
- `voltage_warn`：电压报警信号（MU_N）
- `volatge_signal`：电压数据更新信号
- `current_signal`：电流数据更新信号
- `dataUpSignal`：数据上传信号
- `structure_changed`：通道结构变化信号（MU_N）

## 📊 数据格式

### CSV 数据格式

#### 长条电源
```csv
时间,CH1电压,CH1电流
2023-10-12_16-30-45.123,42.0,3.5
2023-10-12_16-30-45.223,42.1,3.6
```

#### 方形电源
```csv
时间,CH1电压,电流,CH2电压,电流
2023-10-12_16-30-45.123,5.0,1.0,12.0,0.5
2023-10-12_16-30-45.223,5.0,1.1,12.0,0.5
```

#### GPP 三通道电源
```csv
时间,CH1电压,CH1电流,CH2电压,CH2电流,CH3电压,CH3电流
2023-10-12_16-30-45.123,42.0,3.5,12.0,1.0,5.0,0.8
```

#### MU_N 多通道电源
```csv
时间,CH1电压,CH1电流,CH2电压,CH2电流,...
2023-10-12_16-30-45.123,5.0,1.0,12.0,0.5,...
```

## 📝 更新日志

- **V1.0.3**：优化了使用体验，现在串口下拉栏会自动筛选电源使用的串口，点击链接时也会有弹窗提示是否成功
- **V1.0.4**：增加了自动上传电源数据的功能，现在每次测试时上下电后都会自动将电源数据上传到 FTP
- **V1.0.5**：增加了 TCP 自动控制
- **V1.1.0**：增加了自动拉偏测试
- **V1.1.1**：优化了远程控制，增加了拉偏测试的远程控制
- **V1.1.2**：通过增强的错误处理和 TCP 线程安全性提升偏转测试与数据采集性能
- **V1.1.5**：新增 GPP 三通道电源和 MU_N 多通道电源支持；新增声音报警、操作日志、版本管理与自动更新检测功能

## 🤝 贡献

欢迎提交问题和改进建议！

## 📄 许可证

本项目采用 [Mozilla Public License 2.0](LICENSE) 开源许可证。


**要求**：
- 对源代码的修改必须以 MPL 2.0 许可证发布
- 必须保留原始版权和许可证声明
- 如果修改了文件，必须说明修改内容

详细信息请查看 [LICENSE](LICENSE) 文件。

## 👥 作者

- FTFH3
- zhangzhenbonb666

## 📮 联系方式

如有问题，请联系项目维护者。

---

**注意**：本系统涉及电源控制，使用时请确保操作规范，注意安全！
