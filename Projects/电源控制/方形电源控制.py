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

import re
import pandas as pd
import multiprocessing as mp
from .gpd3303s import GPD3303S

from .MyPlot import MyPlot
from .tool import Tool

TOTAL_SEC=20 #图上显示的时间时间长度
TIME_GAP=25 #采样间隔TIME_GAP个点取一个数字
POINT_NUM=int(100/25*TOTAL_SEC) #图上显示的点数

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
        self.GPD = GPD3303S()


        self.VsetCol = [self.line, self.CH1_V, self.CH2_V]
        self.IsetCol = [self.line, self.CH1_I, self.CH2_I]
        self.VoutCol = [self.line, self.CH1_V_print, self.CH2_V_print]
        self.IoutCol = [self.line, self.CH1_I_print, self.CH2_I_print]

        self.portcheck.clicked.connect(lambda: Tool.port_check(self.portchoose))
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

        self.sigInfo.connect(self.show_msg)

        #初始化右侧绘图
        da = {"电压": [], "电流": []}
        self.channel1_layout = MyPlot(dataDict=da, dataLen=POINT_NUM)  #动态画图 通道1
        self.channel1.addWidget( self.channel1_layout)


        da = {"电压": [], "电流": []}
        self.channel2_layout = MyPlot(dataDict=da, dataLen=POINT_NUM)  #动态画图 通道2
        self.channel2.addWidget( self.channel2_layout)

        self.plot_thread = threading.Thread(target=self.plot_callback)

        Tool.port_check(self.portchoose)

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
            QMessageBox.information(self, "提示", f"已连接{self.portchoose.currentText()}！\nCH1：{ch1_v}V\nCH2：{ch2_v}V")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"连接{self.portchoose.currentText()}失败，请检查端口是否正确！")

    
    def power_port_close(self):
        # 断开电源
        self.GPD.close()
        self.sigInfo.emit(f"已断开{self.portchoose.currentText()}")
        self.isConnected = False

    
    def V_set(self, ch, voltage=None):
        # 设置电压
        if voltage is None:
            voltage = float(self.VsetCol[ch].text())
        self.GPD.setVoltage(ch, voltage)
        self.sigInfo.emit(f"已设置{ch}通道电压为{voltage}")

    
    def I_set(self, ch, current=None):
        # 设置电流
        if current is None:
            current = float(self.IsetCol[ch].text())
        self.GPD.setCurrent(ch, current)
        self.sigInfo.emit(f"已设置{ch}通道电流为{current}")


    def sendALLData(self):
        # 发送全部数据
        for i in range(1,3):
            self.V_set(i)
            self.I_set(i)
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
        self.GPD.enableOutput()
        self.sigInfo.emit(f"已打开电源输出")
        time.sleep(1)
        self.isOutput = True
        self.start_plot()
        # self.start_plot()


    def output_close(self):
        # 关闭输出
        if self.plot_thread.is_alive():
            self.StopFlag = True
            self.plot_thread.join()
        self.GPD.enableOutput(False)
        self.sigInfo.emit(f"已关闭电源输出")
        self.isOutput = False


    def plot_callback(self):
        CH = [{"电压": 0, "电流": 0}, {"电压": 0, "电流": 0}, {"电压": 0, "电流": 0}]
        safty = [self.ch1_safty, self.ch2_safty]
        while not self.StopFlag:
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
            # 创建一个CSV文件，保存采集的数据
            if not os.path.exists(f"./电源采集数据/"):
                os.mkdir(f"./电源采集数据/")
            if not os.path.exists(f"./电源采集数据/{self.name}.csv"):
                with open(f"./电源采集数据/{self.name}_{time.strftime('%Y-%m-%d', time.localtime(time.time()))}.csv", "w", encoding='gbk') as f:
                    f.write("时间,CH1电压,电流,CH2电压,电流\n")
            with open(f"./电源采集数据/{self.name}_{time.strftime('%Y-%m-%d', time.localtime(time.time()))}.csv", "a", encoding='gbk') as f:
                f.write(f"{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S.%f')[:-3]},{CH[1]['电压']},{CH[1]['电流']},{CH[2]['电压']},{CH[2]['电流']}\n")
            # 采集间隔
            time.sleep(0.1)

    def start_plot(self):
        # 启动动态画图
        self.StopFlag = False
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


    def checkplot(self):
        return self.plot_thread.is_alive()
        

    @classmethod
    def get_instances(cls):
        return cls.instances
