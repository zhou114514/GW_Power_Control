<<<<<<< HEAD
'''
@工程 ：UpperPc 
@文件 ：电源控制.py
@作者 ：FTFH3
@日期 ：2023/10/10 15:30 
@功能 ：
@方法 ：
=======
"""
方形电源控制模块。
>>>>>>> 3e78017 (initial commit)

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
<<<<<<< HEAD
'''
=======
"""
>>>>>>> 3e78017 (initial commit)
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

import re
import pandas as pd
import multiprocessing as mp
from .gpd3303s import GPD3303S

from .MyPlot import MyPlot
from .tool import Tool

<<<<<<< HEAD
TOTAL_SEC=20 #图上显示的时间时间长度
TIME_GAP=25 #采样间隔TIME_GAP个点取一个数字
POINT_NUM=int(100/25*TOTAL_SEC) #图上显示的点数
MAX_PLOT_FAILURES=1 #采集数据最大连续失败次数
=======
TOTAL_SEC = 20
TIME_GAP = 25
POINT_NUM = int(100 / TIME_GAP * TOTAL_SEC)
PLOT_VOLTAGE_KEY = "电压"
PLOT_CURRENT_KEY = "电流"
DATA_DIR = os.path.join(".", "电源采集数据")
>>>>>>> 3e78017 (initial commit)

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

    def __init__(self, name):
        super(SquarePower,self).__init__()
        self.name = name
        self.instances.append(self)
        self.setupUi(self)

        self.isConnected = False
        self.isOutput = False
        self.isListen = False

        self.StopFlag = True
        self.lagtime = 1
        self.ch1_safty = 100
        self.ch2_safty = 100
<<<<<<< HEAD
        self.start_time = None
=======
>>>>>>> 3e78017 (initial commit)
        self.GPD = GPD3303S()


        self.VsetCol = [self.line, self.CH1_V, self.CH2_V]
        self.IsetCol = [self.line, self.CH1_I, self.CH2_I]
        self.VoutCol = [self.line, self.CH1_V_print, self.CH2_V_print]
        self.IoutCol = [self.line, self.CH1_I_print, self.CH2_I_print]

<<<<<<< HEAD
        self.portcheck.clicked.connect(lambda: Tool.port_check(self.portchoose, type="square"))
=======
        self.portcheck.clicked.connect(lambda: Tool.port_check(self.portchoose))
>>>>>>> 3e78017 (initial commit)
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

<<<<<<< HEAD
        self.ch1_currentV = 0
        self.ch2_currentV = 0
        self.ch1_currentI = 0
        self.ch2_currentI = 0

        self.sigInfo.connect(self.show_msg)

        #初始化右侧绘图
        da = {"电压": [], "电流": []}
        self.channel1_layout = MyPlot(dataDict=da, dataLen=POINT_NUM)  #动态画图 通道1
        self.channel1.addWidget( self.channel1_layout)


        da = {"电压": [], "电流": []}
        self.channel2_layout = MyPlot(dataDict=da, dataLen=POINT_NUM)  #动态画图 通道2
=======
        self.sigInfo.connect(self.show_msg)

        # 初始化右侧图表
        da = {PLOT_VOLTAGE_KEY: [], PLOT_CURRENT_KEY: []}
        self.channel1_layout = MyPlot(dataDict=da, dataLen=POINT_NUM)
        self.channel1.addWidget( self.channel1_layout)


        da = {PLOT_VOLTAGE_KEY: [], PLOT_CURRENT_KEY: []}
        self.channel2_layout = MyPlot(dataDict=da, dataLen=POINT_NUM)
>>>>>>> 3e78017 (initial commit)
        self.channel2.addWidget( self.channel2_layout)

        self.plot_thread = threading.Thread(target=self.plot_callback)

<<<<<<< HEAD
        Tool.port_check(self.portchoose, type="square")

    def power_port_open(self):
=======
        Tool.port_check(self.portchoose)

    def power_port_open(self):
        re = self.port_open()
        if re[0]:
            QMessageBox.information(self, "提示", f"已连接 {self.portchoose.currentText()}\nCH1：{re[1]}V\nCH2：{re[2]}V")

    def port_open(self, show_error=True):
        if self.isConnected:
            self.sigInfo.emit(f"已连接{self.portchoose.currentText()}")
            if self.name == "方形电源":
                Tool.update_config_option("Serial", "power_supply_square1", self.portchoose.currentText())
            return [True, self.GPD.getVoltage(1), self.GPD.getVoltage(2)]
>>>>>>> 3e78017 (initial commit)
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
<<<<<<< HEAD
            QMessageBox.information(self, "提示", f"已连接{self.portchoose.currentText()}！\nCH1：{ch1_v}V\nCH2：{ch2_v}V")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"连接{self.portchoose.currentText()}失败，请检查端口是否正确！")
=======
            if self.name == "方形电源":
                Tool.update_config_option("Serial", "power_supply_square1", self.portchoose.currentText())
            return [True, ch1_v, ch2_v]
        except Exception as e:
            try:
                if getattr(self.GPD, "serial", None):
                    self.GPD.close()
            except Exception:
                pass
            if show_error:
                QMessageBox.warning(self, "错误", f"连接{self.portchoose.currentText()}失败，请检查端口是否正确！")
            return [False, None, None]

    def startup_port_open(self):
        return self.port_open(show_error=False)
>>>>>>> 3e78017 (initial commit)

    
    def power_port_close(self):
        # 断开电源
        self.GPD.close()
        self.sigInfo.emit(f"已断开{self.portchoose.currentText()}")
        self.isConnected = False

    
    def V_set(self, ch, voltage=None):
        # 设置电压
        if voltage is None:
<<<<<<< HEAD
            value = self.VsetCol[ch].text()
            if value == "":
                return
            voltage = float(value)
        self.GPD.setVoltage(ch, voltage)
        self.sigInfo.emit(f"已设置{ch}通道电压为{voltage}")
=======
            voltage = float(self.VsetCol[ch].text())
        self.GPD.setVoltage(ch, voltage)
        self.sigInfo.emit(f"已设置CH{ch}通道电压为{voltage}")
>>>>>>> 3e78017 (initial commit)

    
    def I_set(self, ch, current=None):
        # 设置电流
        if current is None:
<<<<<<< HEAD
            value = self.IsetCol[ch].text()
            if value == "":
                return
            current = float(value)
        self.GPD.setCurrent(ch, current)
        self.sigInfo.emit(f"已设置{ch}通道电流为{current}")
=======
            current = float(self.IsetCol[ch].text())
        self.GPD.setCurrent(ch, current)
        self.sigInfo.emit(f"已设置CH{ch}通道电流为{current}")
>>>>>>> 3e78017 (initial commit)


    def sendALLData(self):
        # 发送全部数据
<<<<<<< HEAD
        for i in range(1,3):
            value = self.VsetCol[i].text()
            if value == "":
                return
            self.V_set(i, float(value))
            value = self.IsetCol[i].text()
            if value == "":
                return
            self.I_set(i, float(value))
        self.sigInfo.emit(f"已发送全部数据")

    def V_get(self, ch):
        # 获取电压
        V = self.GPD.getVoltageOutput(ch)
        if ch == 2 and self.name == '方形电源2':
            V = V * -1
        # self.VoutCol[ch].clear()
        self.VoutCol[ch].setText("电压："+str(V))
=======
        for i in range(1, 3):
            self.V_set(i)
            self.I_set(i)
        self.sigInfo.emit("已发送全部数据")

    def V_get(self, ch):
        # 获取输出电压
        V = self.GPD.getVoltageOutput(ch)
        # self.VoutCol[ch].clear()
        self.VoutCol[ch].setText("电压：" + str(V))
>>>>>>> 3e78017 (initial commit)
        return V
    

    def I_get(self, ch):
<<<<<<< HEAD
        # 获取电流
        I = self.GPD.getCurrentOutput(ch)
        # self.IoutCol[ch].clear()
        self.IoutCol[ch].setText("电流："+str(I))
=======
        # 获取输出电流
        I = self.GPD.getCurrentOutput(ch)
        # self.IoutCol[ch].clear()
        self.IoutCol[ch].setText("电流：" + str(I))
>>>>>>> 3e78017 (initial commit)
        return I
    

    def checkALLData(self):
        # 检查全部数据
        data = [[]]
<<<<<<< HEAD
        for i in range(1,3):
=======
        for i in range(1, 3):
>>>>>>> 3e78017 (initial commit)
            V = self.V_get(i)
            I = self.I_get(i)
            # self.VoutCol[i].clear()
            # self.IoutCol[i].clear()
<<<<<<< HEAD
            self.VoutCol[i].setText("电压："+str(V))
            self.IoutCol[i].setText("电流："+str(I))
=======
            self.VoutCol[i].setText("电压：" + str(V))
            self.IoutCol[i].setText("电流：" + str(I))
>>>>>>> 3e78017 (initial commit)
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
        self.GPD.enableOutput()
<<<<<<< HEAD
        self.sigInfo.emit(f"已打开电源输出")
        time.sleep(1)
        self.isOutput = True
        self.start_time = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')[:-3] if self.start_time is None else self.start_time
=======
        self.sigInfo.emit("已打开电源输出")
        time.sleep(1)
        self.isOutput = True
>>>>>>> 3e78017 (initial commit)
        self.start_plot()
        # self.start_plot()


    def output_close(self):
        # 关闭输出
        if self.plot_thread.is_alive():
            self.StopFlag = True
            self.plot_thread.join()
        self.GPD.enableOutput(False)
<<<<<<< HEAD
        self.sigInfo.emit(f"已关闭电源输出")
        self.isOutput = False
        self.ch1_currentV = 0
        self.ch2_currentV = 0
        self.ch1_currentI = 0
        self.ch2_currentI = 0
        self.start_time = None


    def plot_callback(self):
        CH = [{"电压": 0, "电流": 0}, {"电压": 0, "电流": 0}, {"电压": 0, "电流": 0}]
=======
        self.sigInfo.emit("已关闭电源输出")
        self.isOutput = False


    def plot_callback(self):
        CH = [
            {PLOT_VOLTAGE_KEY: 0, PLOT_CURRENT_KEY: 0},
            {PLOT_VOLTAGE_KEY: 0, PLOT_CURRENT_KEY: 0},
            {PLOT_VOLTAGE_KEY: 0, PLOT_CURRENT_KEY: 0},
        ]
>>>>>>> 3e78017 (initial commit)
        safty = [self.ch1_safty, self.ch2_safty]
        fail_count = 0
        while not self.StopFlag:
            try:
<<<<<<< HEAD
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
=======
                for i in range(1,3):
                   CH[i][PLOT_VOLTAGE_KEY] = self.V_get(i)
                   CH[i][PLOT_CURRENT_KEY] = self.I_get(i)
                   if CH[i][PLOT_CURRENT_KEY] >= safty[i-1]:
                       self.GPD.enableOutput(False)
                       self.StopFlag = True
                       self.current_warn.emit(f"{self.name}", f"CH{i}", f"{CH[i][PLOT_CURRENT_KEY]}")

                fail_count = 0
                self.channel1_signal.emit(CH[1])
                self.channel2_signal.emit(CH[2])

                os.makedirs(DATA_DIR, exist_ok=True)
                csv_path = os.path.join(DATA_DIR, f"{self.name}_{self.start_time}.csv")
                if not os.path.exists(csv_path):
                    with open(csv_path, "w", encoding="gbk") as f:
                        f.write("时间,CH1电压,电流,CH2电压,电流\n")
                with open(csv_path, "a", encoding="gbk") as f:
                    f.write(
                        f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S.%f')[:-3]},"
                        f"{CH[1][PLOT_VOLTAGE_KEY]},{CH[1][PLOT_CURRENT_KEY]},"
                        f"{CH[2][PLOT_VOLTAGE_KEY]},{CH[2][PLOT_CURRENT_KEY]}\n"
                    )

                time.sleep(0.1)
            except Exception as e:
                fail_count += 1
                self.sigInfo.emit(f"采集数据异常({fail_count}/3): {e}")
                if fail_count >= 3:
                    self.sigInfo.emit("串口连续异常，已自动停止采集")
                    self.StopFlag = True
                    break
                time.sleep(1)
>>>>>>> 3e78017 (initial commit)

    def start_plot(self):
        # 启动动态画图
        self.StopFlag = False
<<<<<<< HEAD
        self.start_time = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')[:-3] if self.start_time is None else self.start_time
        if not self.plot_thread.is_alive():
            self.plot_thread = threading.Thread(target=self.plot_callback)
            self.plot_thread.start()
            self.sigInfo.emit(f"已开启采集")
        else:
            self.sigInfo.emit(f"采集已开启")
=======
        if not self.plot_thread.is_alive():
            self.start_time = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')[:-3]
            self.plot_thread = threading.Thread(target=self.plot_callback)
            self.plot_thread.start()
            self.sigInfo.emit("已开启采集")
        else:
            self.sigInfo.emit("采集已开启")
>>>>>>> 3e78017 (initial commit)


    def close_plot(self):
        # 关闭动态画图
        if self.plot_thread.is_alive():
            self.StopFlag = True
            self.plot_thread.join()
<<<<<<< HEAD
            self.sigInfo.emit(f"已关闭采集")
        else:
            self.sigInfo.emit(f"采集已关闭")
        self.start_time = None


    def checkplot(self):
        return self.plot_thread.is_alive()

    def save_data(self):
        return [[datetime.now().strftime('%Y-%m-%d_%H-%M-%S.%f')[:-3], self.ch1_currentV, self.ch1_currentI, self.ch2_currentV, self.ch2_currentI]]
=======
            self.sigInfo.emit("已关闭采集")
        else:
            self.sigInfo.emit("采集已关闭")

    def checkplot(self):
        return self.plot_thread.is_alive()
>>>>>>> 3e78017 (initial commit)
        

    @classmethod
    def get_instances(cls):
        return cls.instances
