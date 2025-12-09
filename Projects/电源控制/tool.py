from PyQt5.QtCore import pyqtSignal
import serial
import serial.tools.list_ports
import time,os,sys
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

class Tool():

    def port_check(combox):
        # 检测所有存在的串口，将信息存储在字典中
        print("开始检测串口")
        Com_Dict.clear()
        port_list = list(serial.tools.list_ports.comports())
        combox.clear()
        for port in port_list:
            if "USB 串行设备" in port[1]:
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
            config.add_section("Serial")
            config.set("Serial", "power_supply_square1", "COM")
            config.set("Serial", "power_supply_square2", "COM")
            config.set("Serial", "power_supply_square3", "COM")
            config.set("Serial", "power_supply_square4", "COM")
            config.set("Serial", "power_supply_long", "COM")
            config.set("Serial", "auto_connect", "False")
            config.set("Serial", "auto_output", "False")
            config.add_section("Additional")
            config.set("Additional", "power_add", "False")
            config.set("Additional", "power_del", "False")
            config.add_section("Safty")
            config.set("Safty", "current_limit1_ch1", "100")
            config.set("Safty", "current_limit1_ch2", "100")
            config.set("Safty", "current_limit2_ch1", "100")
            config.set("Safty", "current_limit2_ch2", "100")
            config.set("Safty", "current_limit3_ch1", "100")
            config.set("Safty", "current_limit3_ch2", "100")
            config.set("Safty", "current_limit4_ch1", "100")
            config.set("Safty", "current_limit4_ch2", "100")
            config.set("Safty", "current_limit5_ch1", "100")
            with open(config_path, "w", encoding="utf-8") as f:
                config.write(f)
            return False
        else:
            return True
        
    def read_config(get_key):
        # 读取配置文件
        config_path = root_path + "\\Auto_config.ini"
        config = configparser.ConfigParser()
        config.read(config_path)
        return dict(config.items(get_key))
    
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