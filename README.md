# 光学头电源控制系统

一个基于 PyQt5 开发的光学头电源控制管理系统，支持多路电源的集中控制、数据采集、实时监测和自动化测试。

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![PyQt5](https://img.shields.io/badge/PyQt5-5.15+-green.svg)
![License](https://img.shields.io/badge/License-MPL%202.0-brightgreen.svg)


## 📋 功能特性

### 核心功能
- **多路电源控制**：支持长条电源和方形电源的同时控制
  - 长条电源：单通道电压/电流控制
  - 方形电源：双通道电压/电流控制
- **串口通信**：自动检测和管理多个电源设备的串口连接
- **实时数据监测**：
  - 实时电压/电流显示
  - 动态曲线绘制
  - 数据采集间隔：100ms
- **数据管理**：
  - 自动保存采集数据为CSV格式
  - 支持FTP自动上传功能
  - 数据保存路径：`./电源采集数据/`

### 高级功能
- **TCP服务器**：支持远程控制和数据交互
- **电压拉偏测试**：
  - 36V → 45V → 42V 自动测试
  - 精度：0.1V步进
- **安全保护**：
  - 电流过载保护
  - 可配置的电流限制阈值
- **自动化操作**：
  - 自动连接串口
  - 自动输出控制
  - 批量数据采集

## 🚀 快速开始

### 环境要求

- Python 3.6+
- Windows 10/11
- 支持的电源型号：
  - GPD3303S（方形电源）
  - PSW系列（长条电源）

### 安装依赖

```bash
pip install PyQt5
pip install pandas
pip install bitstring
pip install pyserial
```

### 运行程序

```bash
python gxtdy.py
```

或直接运行已打包的可执行文件（如果有）。

## ⚙️ 配置说明

### Auto_config.ini 配置文件

#### TCP配置
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

#### 附加功能
```ini
[Additional]
power_add = False     # 是否启用电源添加功能
power_del = False     # 是否启用电源删除功能
```

## 📖 使用说明

### 手动操作流程

1. **连接电源**
   - 点击"刷新串口"按钮检测可用串口
   - 选择对应的串口
   - 点击"打开串口"连接电源

2. **设置参数**
   - 输入目标电压值（V）
   - 输入目标电流值（A）
   - 点击"发送"按钮设置参数
   - 可使用"发送全部"一次性设置所有通道

3. **启动输出**
   - 点击"开始输出"按钮启动电源
   - 系统自动开始数据采集
   - 实时曲线显示电压/电流变化

4. **停止输出**
   - 点击"停止输出"按钮关闭电源
   - 采集数据自动保存到CSV文件

### 注意事项

⚠️ **重要提示**：
1. 在发送或开始任何保存采集工作之前，请务必先打开串口，并输出电源，可使用按键控制或命令控制
2. 发送性能测试前后指令前，请检查数据采集是否停止，否则电源返回的信息会出错，导致软件报错，不能保存
3. 请根据实际设备配置合理的电流限制值，避免设备损坏

### 电压拉偏测试

长条电源支持自动电压拉偏功能：
- **降至36V**：从当前电压自动降至36V
- **升至45V**：从当前电压自动升至45V
- **回到42V**：从当前电压自动恢复到42V
- 步进精度：0.1V/秒

## 📁 项目结构

```
光学头电源控制/
├── gxtdy.py                    # 主程序入口
├── Auto_config.ini             # 配置文件
├── power.ico                   # 程序图标
├── 使用方法.txt                 # 使用说明
├── 更新内容.csv                 # 版本更新记录
├── Projects/
│   └── 电源控制/
│       ├── UpperPC.py          # 主窗口控制
│       ├── 长条电源控制.py       # 长条电源控制模块
│       ├── 方形电源控制.py       # 方形电源控制模块
│       ├── psw_xx_xx.py        # PSW电源驱动
│       ├── gpd3303s.py         # GPD3303S电源驱动
│       ├── MyPlot.py           # 数据绘图模块
│       ├── FTP.py              # FTP上传模块
│       ├── TCP.py              # TCP通信模块
│       ├── TCPServer.py        # TCP服务器
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
- **绘图**：matplotlib（通过MyPlot封装）
- **多线程**：threading, multiprocessing

### 核心模块

#### 1. 长条电源控制 (LongPower)
```python
from Projects.电源控制.长条电源控制 import LongPower

# 创建实例
power = LongPower("长条电源")

# 连接端口
power.port_open()

# 设置电压/电流
power.V_set(42.0)
power.I_set(3.5)

# 开启输出
power.output_open()
```

#### 2. 方形电源控制 (SquarePower)
```python
from Projects.电源控制.方形电源控制 import SquarePower

# 创建实例
power = SquarePower("方形电源1")

# 设置通道1
power.V_set(1, 5.0)  # 通道1设置5V
power.I_set(1, 1.0)  # 通道1设置1A
```

### 信号说明

- `sigInfo`：信息提示信号
- `start_signal`：启动信号
- `current_warn`：电流报警信号
- `volatge_signal`：电压数据更新信号
- `current_signal`：电流数据更新信号
- `dataUpSignal`：数据上传信号

## 📊 数据格式

### CSV数据格式

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

## 📝 更新日志

- **V1.0.3**：优化了使用体验，现在串口下拉栏会自动筛选电源使用的串口，点击链接时也会有弹窗提示是否成功
- **V1.0.4**：增加了自动上传电源数据的功能，现在每次测试时上下电后都会自动将电源数据上传到FTP
- **V1.0.5**：增加了TCP自动控制
- **V1.1.0**：增加了自动拉偏测试

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

## 📮 联系方式

如有问题，请联系项目维护者。

---

**注意**：本系统涉及电源控制，使用时请确保操作规范，注意安全！

