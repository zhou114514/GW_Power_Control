from PyQt5.QtCore import pyqtSignal
import serial
import serial.tools.list_ports
import time,os,sys,json,copy
import configparser

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import openpyxl
import datetime
import pygetwindow as gw



Com_Dict = {}
# print(sys.argv)
import os
# 获取文件路径的根目录
root_path = ""

if getattr(sys, 'frozen', False):
    root_path = os.path.dirname(os.path.abspath(sys.executable))
else:
    root_path = os.path.dirname(os.path.abspath(sys.argv[0]))

POWER_CONFIG_PATH = os.path.join(root_path, "power_config.json")

DEFAULT_POWER_CONFIG = {
    "serial": {
        "auto_connect": False,
        "auto_output": False,
    },
    "devices": [
        {
            "id": "long1",
            "name": "长条电源",
            "type": "long",
            "port": "COM",
            "default_voltage": 42,
            "default_current": 3.5,
            "current_limit": 100,
            "remote": True,
        }
    ],
}

_power_device_registry = {}

class Tool():

    def port_check(combox, type:str="long"):
        # 检测所有存在的串口，将信息存储在字典中
        print("开始检测串口")
        Com_Dict.clear()
        port_list = list(serial.tools.list_ports.comports())
        combox.clear()
        for port in port_list:
            if type == "long":
                if "USB 串行设备" in port[1]:
                    Com_Dict["%s" % port[0]] = "%s" % port[1]
                    combox.addItem(port[0])
            else:
                if "USB Serial Port" in port[1]:
                    Com_Dict["%s" % port[0]] = "%s" % port[1]
                    combox.addItem(port[0])
        if len(Com_Dict) == 0:
            print("无串口")
            return False
        else:
            combox.setCurrentIndex(0)
            print("串口列表：", Com_Dict)
            return True

    # 串口信息
    def port_imf(combox):
        # 显示选定的串口的详细信息
        imf_s = combox.currentText()
        if imf_s != "":
            print(Com_Dict[combox.currentText()])

    
    def check_incombox(combox, incombox):
        for i in range(combox.count()):
            if combox.itemText(i) == incombox:
                return True
        return False
    

    def check_config():
        # 检测配置文件是否存在，不存在则创建
        config_path = root_path + "\\Auto_config.ini"
        if not os.path.exists(config_path):
            config = configparser.ConfigParser()
            config.add_section("TCP")
            config.set("TCP", "ip", "127.0.0.1")
            config.set("TCP", "port", "4070")
            config.set("TCP", "auto_connect", "True")
            config.add_section("Additional")
            config.set("Additional", "power_add", "False")
            config.set("Additional", "power_del", "False")
            with open(config_path, "w", encoding="utf-8") as f:
                config.write(f)
        Tool.check_power_config()
        return os.path.exists(config_path)

    def check_power_config():
        """检测电源 JSON 配置文件，不存在则创建默认配置"""
        if not os.path.exists(POWER_CONFIG_PATH):
            default = copy.deepcopy(DEFAULT_POWER_CONFIG)
            default["scenario"] = "gxt_only"
            with open(POWER_CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(default, f, ensure_ascii=False, indent=2)
            return False
        return True

    def read_power_config_raw():
        """读取电源 JSON 原始配置（含 scenario 字段）"""
        Tool.check_power_config()
        with open(POWER_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_power_config(cfg):
        """保存电源 JSON 配置"""
        with open(POWER_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)

    def need_power_scenario_setup():
        """是否尚未选择使用场景（首次启动需弹出设置）"""
        cfg = Tool.read_power_config_raw()
        return not cfg.get("scenario")

    def register_power_device(device_id, instance):
        if device_id:
            _power_device_registry[str(device_id)] = instance

    def unregister_power_device(device_id):
        _power_device_registry.pop(str(device_id), None)

    def get_power_device(device_id):
        return _power_device_registry.get(str(device_id))

    def _normalize_device(dev):
        power_type = dev.get("type", "long")
        normalized = {
            "id": str(dev["id"]),
            "name": dev.get("name", str(dev["id"])),
            "type": power_type,
            "port": dev.get("port", "COM1"),
            "remote": bool(dev.get("remote", power_type == "long")),
        }
        if power_type == "long":
            normalized["default_voltage"] = float(dev.get("default_voltage", 42))
            normalized["default_current"] = float(dev.get("default_current", 3.5))
            normalized["current_limit"] = float(dev.get("current_limit", 100))
        elif power_type == "square":
            ch1 = dev.get("ch1", {})
            ch2 = dev.get("ch2", {})
            normalized["ch1"] = {
                "voltage": float(ch1.get("voltage", 5)),
                "current": float(ch1.get("current", 1)),
            }
            normalized["ch2"] = {
                "voltage": float(ch2.get("voltage", 12)),
                "current": float(ch2.get("current", 0.5)),
            }
            normalized["current_limit_ch1"] = float(dev.get("current_limit_ch1", 100))
            normalized["current_limit_ch2"] = float(dev.get("current_limit_ch2", 100))
        else:
            raise ValueError(f"未知电源类型: {power_type}")
        return normalized
        
    def read_config(get_key):
        # 读取配置文件
        config_path = root_path + "\\Auto_config.ini"
        config = configparser.ConfigParser()
        config.read(config_path)
        return dict(config.items(get_key))

    def read_power_config():
        """读取电源 JSON 配置（每台电源的类型、限压限流、远程索引 id）"""
        cfg = Tool.read_power_config_raw()
        serial_cfg = cfg.get("serial", {})
        devices = []
        seen_ids = set()
        for dev in cfg.get("devices", []):
            if "id" not in dev:
                raise ValueError("电源配置缺少 id 字段")
            normalized = Tool._normalize_device(dev)
            if normalized["id"] in seen_ids:
                raise ValueError(f"重复的电源 id: {normalized['id']}")
            seen_ids.add(normalized["id"])
            devices.append(normalized)
        if not devices:
            raise ValueError("电源配置 devices 列表不能为空")
        return {
            "serial": {
                "auto_connect": bool(serial_cfg.get("auto_connect", False)),
                "auto_output": bool(serial_cfg.get("auto_output", False)),
            },
            "devices": devices,
        }
    
    def init_execl_list():
        # 获取execl文件列表
        data_dict = {}
        file_path = root_path + "\采集表格\采集表格.txt"
        with open(file_path, 'r', encoding='utf-8') as file:
            for line in file:
            # 去掉行末的换行符，并以制表符分割
                key_value = line.strip().split(':')
                # 确保每行有两个部分
                if len(key_value) == 2:
                    key, value = key_value
                    data_dict[key] = value

        return data_dict
    
    def check_window_contains_keyword(keyword):
        try:
            # 获取所有打开的窗口标题
            windows = gw.getAllTitles()
            # print(windows)
            # 检查是否有窗口标题包含指定的关键词
            for title in windows:
                if keyword in title:
                    return title
            return None
        except Exception as e:
            print(e)
            return None
    

class execl_file():
    def __init__(self):
        self.file_path = root_path + "\采集表格"
        self.sheet = None
        self.workbook = None
        self.startrow = 2  # 从第2行开始填充数据

    def read_execl(self, sheet_name):
        # 读取execl文件
        input_file = self.file_path + "\\" + sheet_name + ".xlsx"
        # print(input_file)
        if not os.path.exists(input_file):
            print("文件不存在")
            return False
        self.workbook = openpyxl.load_workbook(input_file)
        # 选择活动工作表
        self.sheet = self.workbook.active
        return True

    def write_execl(self, data):
        # 写入execl文件
        if self.sheet is None:
            print("请先读取execl文件")
            return False
        for row_index, row_data in enumerate(data, self.startrow):
            for col_index, value in enumerate(row_data, start=2):  # 从第2列开始填充
                self.sheet.cell(row=row_index, column=col_index, value=value)
            self.startrow = row_index + 1  # 记录最新写入的行数

    def save_execl(self, sheet_name):
        # 保存execl文件
        if self.sheet is None:
            print("请先读取execl文件")
            return False
        if not os.path.exists(f"./电源采集数据/"):
            os.mkdir(f"./电源采集数据/")
        self.workbook.save(root_path + "\电源采集数据" + "\\" + sheet_name + datetime.datetime.now().strftime("%Y%m%d%H%M%S") + ".xlsx")
        self.startrow = 2  # 重置写入行数
        print("保存成功")