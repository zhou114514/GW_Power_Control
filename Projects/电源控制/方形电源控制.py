'''
@工程 ：UpperPc 
@文件 ：电源控制.py
@作者 ：FTFH3
@日期 ：2023/10/10 15:30 
@功能 ：
@方法 ：

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
'''
from datetime import datetime
import threading,dill
import time,os
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from bitstring import *
# from Utility.Datebase.Database import DataBase
# from Utility.Function.FuncMng import FuncMng
from .方形电源_UI import Ui_Form
from PyQt5.QtCore import pyqtSignal

import re
import pandas as pd
import multiprocessing as mp
from .gpd3303s import GPD3303S

from .MyPlot import MyPlot
from .tool import Tool

TOTAL_SEC=20 #图上显示的时间时间长度
TIME_GAP=25 #采样间隔TIME_GAP个点取一个数字
POINT_NUM=int(100/25*TOTAL_SEC) #图上显示的点数
MAX_PLOT_FAILURES=1 #采集数据最大连续失败次数

class SquarePower(QtWidgets.QWidget,Ui_Form):
    instances = []
    VsetCol = []
    IsetCol = []
    VoutCol = []
    IoutCol = []
    name = '11'
    sigInfo = pyqtSignal(str)
    current_warn = pyqtSignal([str, str, str])
    channel1_signal = pyqtSignal(dict)
    channel2_signal = pyqtSignal(dict)
    dataUpSignal = pyqtSignal(str)
    _tcp_invoke_signal = pyqtSignal()

    def __init__(self, name, device_id=None, ch1_voltage=5.0, ch1_current=1.0, ch2_voltage=12.0, ch2_current=0.5, remote_enabled=False):
        super(SquarePower,self).__init__()
        self.name = name
        self.device_id = device_id
        self.remote_enabled = remote_enabled
        self.instances.append(self)
        if device_id:
            Tool.register_power_device(device_id, self)
        self.setupUi(self)

        self.isConnected = False
        self.isOutput = False
        self.isListen = False

        self.StopFlag = True
        self.lagtime = 1
        self.ch1_safty = 100
        self.ch2_safty = 100
        self.start_time = None
        self.GPD = GPD3303S()
        self._tracking_mode = 'independent'  # 缓存追踪模式：independent/series/parallel


        self.VsetCol = [self.line, self.CH1_V, self.CH2_V]
        self.IsetCol = [self.line, self.CH1_I, self.CH2_I]
        self.VoutCol = [self.line, self.CH1_V_print, self.CH2_V_print]
        self.IoutCol = [self.line, self.CH1_I_print, self.CH2_I_print]

        self.portcheck.clicked.connect(lambda: Tool.port_check(self.portchoose, type="square"))
        self.portopen.clicked.connect(self.power_port_open)
        self.portclose.clicked.connect(self.power_port_close)
        self.CH1_V_send.clicked.connect(lambda: self.V_set(1))
        self.CH2_V_send.clicked.connect(lambda: self.V_set(2))
        self.CH1_I_send.clicked.connect(lambda: self.I_set(1))
        self.CH2_I_send.clicked.connect(lambda: self.I_set(2))
        self.CH1_V_check.clicked.connect(lambda: self.V_get(1))
        self.CH2_V_check.clicked.connect(lambda: self.V_get(2))
        self.CH1_I_check.clicked.connect(lambda: self.I_get(1))
        self.CH2_I_check.clicked.connect(lambda: self.I_get(2))

        self.sendALL.clicked.connect(self.sendALLData)
        self.checkALL.clicked.connect(self.checkALLData)

        self.start_btn.clicked.connect(self.output_open)
        self.stop_btn.clicked.connect(self.output_close)

        self.start_listen.clicked.connect(self.start_plot)
        self.stop_listen.clicked.connect(self.close_plot)

        self.channel1_signal.connect(lambda x: self.channel1_layout.updateData(x))
        self.channel2_signal.connect(lambda x: self.channel2_layout.updateData(x))

        self.ch1_currentV = 0
        self.ch2_currentV = 0
        self.ch1_currentI = 0
        self.ch2_currentI = 0

        self.sigInfo.connect(self.show_msg)

        self.CH1_V.setText(str(ch1_voltage))
        self.CH1_I.setText(str(ch1_current))
        self.CH2_V.setText(str(ch2_voltage))
        self.CH2_I.setText(str(ch2_current))

        #初始化右侧绘图
        da = {"电压": [], "电流": []}
        self.channel1_layout = MyPlot(dataDict=da, dataLen=POINT_NUM)  #动态画图 通道1
        self.channel1.addWidget( self.channel1_layout)


        da = {"电压": [], "电流": []}
        self.channel2_layout = MyPlot(dataDict=da, dataLen=POINT_NUM)  #动态画图 通道2
        self.channel2.addWidget( self.channel2_layout)

        self.plot_thread = threading.Thread(target=self.plot_callback)

        Tool.port_check(self.portchoose, type="square")

        # TCP线程安全调用机制：确保串口操作在Qt主线程中执行
        self._tcp_invoke_lock = threading.Lock()
        self._tcp_op_event = threading.Event()
        self._tcp_op_func = None
        self._tcp_op_result = None
        self._tcp_invoke_signal.connect(self._on_tcp_invoke)

    def _on_tcp_invoke(self):
        """槽函数：在Qt主线程中执行TCP请求的操作"""
        if self._tcp_op_func:
            try:
                self._tcp_op_result = self._tcp_op_func()
            except Exception as e:
                self._tcp_op_result = [False, str(e)]
            self._tcp_op_event.set()

    def _invoke_in_main_thread(self, func, timeout=30):
        """从后台线程安全调用需要在主线程执行的函数，阻塞等待结果"""
        with self._tcp_invoke_lock:
            self._tcp_op_event.clear()
            self._tcp_op_func = func
            self._tcp_invoke_signal.emit()
            if self._tcp_op_event.wait(timeout=timeout):
                return self._tcp_op_result
            return [False, "Operation timed out"]

    def invoke_tcp_power_on(self):
        return self._invoke_in_main_thread(self.output_open_tcp)

    def invoke_tcp_power_off(self):
        return self._invoke_in_main_thread(self.output_close_tcp)

    def output_open_tcp(self):
        """供后台线程调用的上电接口（注入预设参数后上电，无确认弹窗）"""
        if not self.isConnected:
            return [False, "Port not connected"]
        self.sendALLData()
        self.GPD.enableOutput()
        self.sigInfo.emit(f"已打开电源输出")
        time.sleep(1)
        self.isOutput = True
        self.start_time = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')[:-3] if self.start_time is None else self.start_time
        self.start_plot()
        return [True, ""]

    def output_close_tcp(self):
        """供后台线程调用的下电接口"""
        if self.plot_thread.is_alive():
            self.StopFlag = True
            self.plot_thread.join()
        self.GPD.enableOutput(False)
        self.sigInfo.emit(f"已关闭电源输出")
        self.isOutput = False
        self.ch1_currentV = 0
        self.ch2_currentV = 0
        self.ch1_currentI = 0
        self.ch2_currentI = 0
        self.start_time = None
        return [True, ""]

    _TRACKING_MODE_NAMES = {
        'independent': '独立',
        'series': '串联',
        'parallel': '并联',
    }

    def _refresh_tracking_mode(self):
        """读取并缓存电源追踪模式，更新界面提示。未连接时静默跳过。"""
        if not self.isConnected:
            return
        try:
            self._tracking_mode = self.GPD.getTrackingMode()
            mode_str = self._TRACKING_MODE_NAMES.get(self._tracking_mode, self._tracking_mode)
            self.sigInfo.emit(f"追踪模式：{mode_str}")
            if self._tracking_mode != 'independent':
                self.sigInfo.emit("注意：非独立模式 — CH2设置将自动跟随CH1")
                self.CH2_name.setText("CH2（非独立=CH1）")
            else:
                # 恢复 CH2 标签
                try:
                    ch2_v = self.GPD.getVoltage(2)
                    self.CH2_name.setText(f"CH2：{ch2_v}V")
                except Exception:
                    pass
        except Exception as e:
            self.sigInfo.emit(f"读取追踪模式失败：{e}")
            self._tracking_mode = 'independent'

    def _effective_ch(self, ch):
        """并联模式下将 CH2 请求重定向至 CH1，同时记录日志。"""
        if self._tracking_mode != 'independent' and ch == 2:
            self.sigInfo.emit("非独立模式：CH2指令自动重定向至CH1")
            return 1
        return ch

    def power_port_open(self):
        try:
            # 连接电源
            self.GPD.open(self.portchoose.currentText())
            ch1_v = self.GPD.getVoltage(1)
            ch2_v = self.GPD.getVoltage(2)
            self.powername.setText(f"{ch1_v}V+{ch2_v}V")
            self.CH1_name.setText(f"CH1：{ch1_v}V")
            self.CH2_name.setText(f"CH2：{ch2_v}V")
            self.sigInfo.emit(f"已连接{self.portchoose.currentText()}")
            self.isConnected = True
            Tool.save_device_port(self.device_id, self.portchoose.currentText())
            self._refresh_tracking_mode()
            QMessageBox.information(self, "提示", f"已连接{self.portchoose.currentText()}！\nCH1：{ch1_v}V\nCH2：{ch2_v}V")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"连接{self.portchoose.currentText()}失败，请检查端口是否正确！")

    
    def power_port_close(self):
        # 断开电源
        self.GPD.close()
        self.sigInfo.emit(f"已断开{self.portchoose.currentText()}")
        self.isConnected = False

    
    def V_set(self, ch, voltage=None):
        # 设置电压（并联模式下 CH2 自动重定向至 CH1）
        if voltage is None:
            value = self.VsetCol[ch].text()
            if value == "":
                return
            voltage = float(value)
        actual_ch = self._effective_ch(ch)
        self.GPD.setVoltage(actual_ch, voltage)
        self.sigInfo.emit(f"已设置CH{ch}电压为{voltage}")
        # 非独立模式：同步 CH1/CH2 输入框显示
        if self._tracking_mode != 'independent':
            self.VsetCol[1].setText(str(voltage))
            self.VsetCol[2].setText(str(voltage))

    def I_set(self, ch, current=None):
        # 设置电流（并联模式下 CH2 自动重定向至 CH1）
        if current is None:
            value = self.IsetCol[ch].text()
            if value == "":
                return
            current = float(value)
        actual_ch = self._effective_ch(ch)
        self.GPD.setCurrent(actual_ch, current)
        self.sigInfo.emit(f"已设置CH{ch}电流为{current}")
        # 非独立模式：同步 CH1/CH2 输入框显示
        if self._tracking_mode != 'independent':
            self.IsetCol[1].setText(str(current))
            self.IsetCol[2].setText(str(current))

    def sendALLData(self):
        """发送全部预设参数。非独立模式下刷新追踪状态后只发送 CH1，CH2 自动跟随。"""
        self._refresh_tracking_mode()
        if self._tracking_mode != 'independent':
            v_text = self.VsetCol[1].text()
            i_text = self.IsetCol[1].text()
            if v_text == "" or i_text == "":
                return
            self.GPD.setVoltage(1, float(v_text))
            self.GPD.setCurrent(1, float(i_text))
            # 同步 CH2 输入框，使界面保持一致
            self.VsetCol[2].setText(v_text)
            self.IsetCol[2].setText(i_text)
            self.sigInfo.emit(f"非独立模式：已设置CH1 {v_text}V/{i_text}A（CH2自动同步）")
        else:
            for ch in range(1, 3):
                v_text = self.VsetCol[ch].text()
                if v_text == "":
                    return
                self.V_set(ch, float(v_text))
                i_text = self.IsetCol[ch].text()
                if i_text == "":
                    return
                self.I_set(ch, float(i_text))
            self.sigInfo.emit(f"已发送全部数据")

    def V_get(self, ch):
        # 获取电压
        V = self.GPD.getVoltageOutput(ch)
        if ch == 2 and self.name == '方形电源2':
            V = V * -1
        # self.VoutCol[ch].clear()
        self.VoutCol[ch].setText("电压："+str(V))
        return V
    

    def I_get(self, ch):
        # 获取电流
        I = self.GPD.getCurrentOutput(ch)
        # self.IoutCol[ch].clear()
        self.IoutCol[ch].setText("电流："+str(I))
        return I
    

    def checkALLData(self):
        # 检查全部数据
        data = [[]]
        for i in range(1,3):
            V = self.V_get(i)
            I = self.I_get(i)
            # self.VoutCol[i].clear()
            # self.IoutCol[i].clear()
            self.VoutCol[i].setText("电压："+str(V))
            self.IoutCol[i].setText("电流："+str(I))
            data[0].append(str(V))
            data[0].append(str(I))
        return data
    
    def findThread(self, name):
        # print("开始监看")
        self.sigInfo.emit("开始监看")
        while self.findFlag:
            if Tool.check_window_contains_keyword(name):
                self.sigInfo.emit("找到终端")
                # print("找到终端")
                self.found = True
                self.findFlag = False
                break
            time.sleep(1)

    def show_msg(self, info):
        # 显示提示
        self.msg.moveCursor(QTextCursor.End)
        self.msg.insertPlainText(f"{info}\n")

    def output_open(self):
        # 打开输出
        if not self.isConnected:
            self.sigInfo.emit(f"请先连接电源")
            return
        self.sendALLData()
        self.GPD.enableOutput()
        self.sigInfo.emit(f"已打开电源输出")
        time.sleep(1)
        self.isOutput = True
        self.start_time = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')[:-3] if self.start_time is None else self.start_time
        self.start_plot()


    def output_close(self):
        # 关闭输出
        if self.plot_thread.is_alive():
            self.StopFlag = True
            self.plot_thread.join()
        self.GPD.enableOutput(False)
        self.sigInfo.emit(f"已关闭电源输出")
        self.isOutput = False
        self.ch1_currentV = 0
        self.ch2_currentV = 0
        self.ch1_currentI = 0
        self.ch2_currentI = 0
        self.start_time = None


    def plot_callback(self):
        CH = [{"电压": 0, "电流": 0}, {"电压": 0, "电流": 0}, {"电压": 0, "电流": 0}]
        safty = [self.ch1_safty, self.ch2_safty]
        fail_count = 0
        while not self.StopFlag:
            try:
                fail_count = 0
                for i in range(1,3):
                    CH[i]["电压"] = self.V_get(i)
                    CH[i]["电流"] = self.I_get(i)
                    if CH[i]["电流"] >= safty[i-1]:
                        self.GPD.enableOutput(False)
                        self.StopFlag = True
                        self.current_warn.emit(f"{self.name}", f"CH{i}", f"{CH[i]["电流"]}")
                # self.channel1_layout.updateData(CH[1])
                # self.channel2_layout.updateData(CH[2])
                self.channel1_signal.emit(CH[1])
                self.channel2_signal.emit(CH[2])
                self.ch1_currentV = CH[1]["电压"]
                self.ch2_currentV = CH[2]["电压"]
                self.ch1_currentI = CH[1]["电流"]
                self.ch2_currentI = CH[2]["电流"]
                # 创建一个CSV文件，保存采集的数据
                if not os.path.exists(f"./电源采集数据/"):
                    os.mkdir(f"./电源采集数据/")
                try:
                    if not os.path.exists(f"./电源采集数据/{self.name}_{self.start_time}.csv"):
                        with open(f"./电源采集数据/{self.name}_{self.start_time}.csv", "w", encoding='gbk') as f:
                            f.write("时间,CH1电压,电流,CH2电压,电流\n")
                    with open(f"./电源采集数据/{self.name}_{self.start_time}.csv", "a", encoding='gbk') as f:
                        f.write(f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S.%f')[:-3]},{CH[1]['电压']},{CH[1]['电流']},{CH[2]['电压']},{CH[2]['电流']}\n")
                except PermissionError as e:   # 文件被占用
                    self.sigInfo.emit(f"文件被占用，无法写入数据: {e}")
                    time.sleep(1)
                    continue
            except Exception as e:
                fail_count += 1
                self.sigInfo.emit(f"采集数据异常({fail_count}/{MAX_PLOT_FAILURES}): {e}")
                if fail_count >= MAX_PLOT_FAILURES:
                    self.sigInfo.emit("串口连续异常，已自动停止采集")
                    self.StopFlag = True
                    self.power_port_close()
                    break
            # 采集间隔
            time.sleep(0.1)

    def start_plot(self):
        # 启动动态画图
        self.StopFlag = False
        self.start_time = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')[:-3] if self.start_time is None else self.start_time
        if not self.plot_thread.is_alive():
            self.plot_thread = threading.Thread(target=self.plot_callback)
            self.plot_thread.start()
            self.sigInfo.emit(f"已开启采集")
        else:
            self.sigInfo.emit(f"采集已开启")


    def close_plot(self):
        # 关闭动态画图
        if self.plot_thread.is_alive():
            self.StopFlag = True
            self.plot_thread.join()
            self.sigInfo.emit(f"已关闭采集")
        else:
            self.sigInfo.emit(f"采集已关闭")
        self.start_time = None


    def checkplot(self):
        return self.plot_thread.is_alive()

    def save_data(self):
        return [[datetime.now().strftime('%Y-%m-%d_%H-%M-%S.%f')[:-3], self.ch1_currentV, self.ch1_currentI, self.ch2_currentV, self.ch2_currentI]]
        

    @classmethod
    def get_instances(cls):
        return cls.instances
