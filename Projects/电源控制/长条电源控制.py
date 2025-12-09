'''
@工程 ：UpperPc 
@文件 ：电源控制.py
@作者 ：FTFH3
@日期 ：2023/10/12 16:30
@功能 ：
@方法 ：

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
'''
from datetime import datetime
import threading,dill
import time,os,math
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from bitstring import *
# from Utility.Datebase.Database import DataBase
# from Utility.Function.FuncMng import FuncMng
from .长条电源_UI import Ui_Form

import pandas as pd
import multiprocessing as mp
from .psw_xx_xx import psw_xx_xx

from .MyPlot import MyPlot
from .tool import Tool

TOTAL_SEC=20 #图上显示的时间时间长度
TIME_GAP=25 #采样间隔TIME_GAP个点取一个数字
POINT_NUM=int(100/25*TOTAL_SEC) #图上显示的点数

class LongPower(QtWidgets.QWidget,Ui_Form):
    instances = []
    VsetCol = []
    IsetCol = []
    VoutCol = []
    IoutCol = []
    name = '11'
    sigInfo = pyqtSignal(str)
    start_signal = pyqtSignal([str, float, float])
    current_warn = pyqtSignal([str, str, str])
    volatge_signal = pyqtSignal(dict)
    current_signal = pyqtSignal(dict)
    dataUpSignal = pyqtSignal(str)

    def __init__(self, name):
        super(LongPower,self).__init__()
        self.name = name
        self.instances.append(self)
        self.setupUi(self)

        self.isConnected = False
        self.isOutput = False
        self.isListen = False
        self.findFlag = False
        self.found = False

        self.CurrentV = 0
        self.CurrentI = 0

        self.StopFlag = True
        self.pressNo = False
        self.lagtime = 1
        self.safty = 100
        self.psw = psw_xx_xx()

        self.btn_Control(False, False, False, False, False, False, False)

        self.portcheck.clicked.connect(lambda: Tool.port_check(self.portchoose))
        self.portopen.clicked.connect(self.power_port_open)
        self.portclose.clicked.connect(self.power_port_close)
        self.CH1_V_send.clicked.connect(lambda: self.V_set())
        self.CH1_I_send.clicked.connect(lambda: self.I_set())
        self.CH1_V_check.clicked.connect(self.V_get)
        self.CH1_I_check.clicked.connect(self.I_get)

        self.sendALL.clicked.connect(self.sendALLData)
        self.checkALL.clicked.connect(self.checkALLData)

        self.start_btn.clicked.connect(self.output_open)
        self.stop_btn.clicked.connect(self.output_close)

        self.start_listen.clicked.connect(self.start_plot)
        self.stop_listen.clicked.connect(self.close_plot)

        self.volatge_signal.connect(lambda x: self.volatge_layout.updateData(x))
        self.current_signal.connect(lambda x: self.current_layout.updateData(x))

        self.CH1_V.setText("42")
        self.CH1_I.setText("3.5")

        self.sigInfo.connect(self.show_msg)

        #初始化右侧绘图
        da = {"电压": []}
        self.volatge_layout = MyPlot(dataDict=da, dataLen=POINT_NUM)  #动态画图 通道1
        self.channel1.addWidget( self.volatge_layout)


        da = {"电流": []}
        self.current_layout = MyPlot(dataDict=da, dataLen=POINT_NUM)  #动态画图 通道2
        self.channel2.addWidget( self.current_layout)

        self.plot_thread = threading.Thread(target=self.plot_callback)

        Tool.port_check(self.portchoose)

        self.to36VTimer = QtCore.QTimer()
        self.to36VTimer.timeout.connect(self.to36)

        self.to45VTimer = QtCore.QTimer()
        self.to45VTimer.timeout.connect(self.to45)

        self.back42VTimer = QtCore.QTimer()
        self.back42VTimer.timeout.connect(self.back42)

        self.Btn_to36.clicked.connect(lambda: self.to36VTimer.start(1000))
        self.Btn_to36.clicked.connect(lambda: self.btn_Control(Btn_to45=False, Btn_back42=False))
        self.Btn_to45.clicked.connect(lambda: self.to45VTimer.start(1000))
        self.Btn_to45.clicked.connect(lambda: self.btn_Control(Btn_to36=False, Btn_back42=False))
        self.Btn_back42.clicked.connect(lambda: self.back42VTimer.start(1000))
        self.Btn_back42.clicked.connect(lambda: self.btn_Control(Btn_to36=False, Btn_to45=False))

    def btn_Control(self, start_btn=None, stop_btn=None, start_listen=None, stop_listen=None, Btn_to36=None, Btn_to45=None, Btn_back42=None):
        if start_btn is not None:
            self.start_btn.setEnabled(start_btn)
        if stop_btn is not None:
            self.stop_btn.setEnabled(stop_btn)
        if start_listen is not None:
            self.start_listen.setEnabled(start_listen)
        if stop_listen is not None:
            self.stop_listen.setEnabled(stop_listen)
        if Btn_to36 is not None:
            self.Btn_to36.setEnabled(Btn_to36)
        if Btn_to45 is not None:
            self.Btn_to45.setEnabled(Btn_to45)
        if Btn_back42 is not None:
            self.Btn_back42.setEnabled(Btn_back42)

    def to36(self):
        if math.isclose(self.CurrentV, 36, abs_tol=0.1) or self.CurrentV < 35.9:
            self.sigInfo.emit("已达到36V")
            self.to36VTimer.stop()
            self.btn_Control(Btn_to45=True, Btn_back42=True)
            QMessageBox.information(self, "提示", "已达到36V")
            return
        self.V_set(round(self.CurrentV, 1) - 0.1)

    def to45(self):
        if math.isclose(self.CurrentV, 45, abs_tol=0.1) or self.CurrentV > 45.1:
            self.sigInfo.emit("已达到45V")
            self.to45VTimer.stop()
            self.btn_Control(Btn_to36=True, Btn_back42=True)
            QMessageBox.information(self, "提示", "已达到45V")
            return
        self.V_set(round(self.CurrentV, 1) + 0.1)

    def back42(self):
        if math.isclose(self.CurrentV, 42, abs_tol=0.1) \
            or (self.CurrentV >= 41 and self.CurrentV <= 42 and (self.CurrentV + 0.1) > 42) \
            or (self.CurrentV <= 43 and self.CurrentV >= 42 and (self.CurrentV - 0.1) < 42):
            self.V_set(42)
            self.sigInfo.emit("已回到42V")
            self.back42VTimer.stop()
            self.btn_Control(Btn_to36=True, Btn_to45=True)
            QMessageBox.information(self, "提示", "已回到42V")
            return
        self.V_set((round(self.CurrentV, 1) - 0.1) if self.CurrentV > 42 else (round(self.CurrentV, 1) + 0.1))

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


    def power_port_open(self):
        re = self.port_open()
        if re[0]:
            self.btn_Control(start_btn=True, stop_btn=True, start_listen=True, stop_listen=False, Btn_to36=False, Btn_to45=False, Btn_back42=False)
            QMessageBox.information(self, "提示", f"已连接{self.portchoose.currentText()}")

    def port_open(self):
        if self.isConnected:
            self.sigInfo.emit(f"已连接{self.portchoose.currentText()}")
            return [True, ""]
        try:
            self.psw.open(self.portchoose.currentText())
            V = self.psw.getVoltage()
            self.powername.setText(f"{V}V")
            self.sigInfo.emit(f"已连接{self.portchoose.currentText()}")
            self.isConnected = True
            return [True, ""]
        except Exception as e:
            QMessageBox.warning(self, "错误", f"连接{self.portchoose.currentText()}失败，请检查端口是否正确！")
            return [False, ""]
    
    def power_port_close(self):
        # 断开电源
        self.psw.close()
        self.sigInfo.emit(f"已断开{self.portchoose.currentText()}")
        self.isConnected = False
        self.btn_Control(False, False, False, False, False, False, False)
    
    def V_set(self, voltage=None):
        # 设置电压
        if voltage is None:
            voltage = float(self.CH1_V.text())
        self.psw.setVoltage(voltage)
        self.sigInfo.emit(f"已设置CH1电压为{voltage}")

    
    def I_set(self, current=None):
        # 设置电流
        if current is None:
            current = float(self.CH1_I.text())
        self.psw.setCurrent(current)
        self.sigInfo.emit(f"已设置CH1电流为{current}")


    def sendALLData(self):
        # 发送全部数据
        self.psw.setVoltage(float(self.CH1_V.text()))
        self.psw.setCurrent(float(self.CH1_I.text()))
        self.sigInfo.emit(f"已发送全部数据")

    def V_get(self):
        # 获取设置电压
        V = self.psw.getVoltage()
        # self.VoutCol[ch].clear()
        self.CH1_V_print.setText("电压："+str(V))
        return V
    

    def I_get(self):
        # 获取设置电流
        I = self.psw.getCurrent()
        # self.IoutCol[ch].clear()
        self.CH1_I_print.setText("电流："+str(I))
        return I
    

    def checkALLData(self):
        # 检查全部数据
        V,I = self.psw.getVoltage(), self.psw.getCurrent()
        self.CH1_V_print.setText("电压：%.3f" % V)
        self.CH1_I_print.setText("电流：%.3f" % I)
        self.sigInfo.emit(f"已检查全部数据")
        return [["%.3f"%V, "%.3f"%I]]

    
    def output_open(self):
        # 打开输出
        if self.isConnected:
            self.found = False
            self.start_time = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')[:-3]
            self.findFlag = True
            # thread = threading.Thread(target=self.findThread, args=("综合测试终端",))
            # thread.start()
            self.sendALLData()
            self.start_signal.emit(self.name, self.V_get(), self.I_get())
            if self.pressNo:
                self.pressNo = False
                return
            self.start_plot()
            time.sleep(1)
            self.psw.enableOutput()
            self.sigInfo.emit(f"已打开电源输出")
            self.isOutput = True
            self.btn_Control(start_btn=False, stop_btn=True, Btn_to36=True, Btn_to45=True, Btn_back42=True)
        else:
            self.sigInfo.emit(f"请先连接电源")
            return
    
    
    def output_open_tcp(self):
        # 打开输出
        if self.isConnected:    
            self.found = False
            self.start_time = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')[:-3]
            self.findFlag = True
            # thread = threading.Thread(target=self.findThread, args=("综合测试终端",))
            # thread.start()
            self.sendALLData()
            # self.start_signal.emit(self.name, self.V_get(), self.I_get())
            # if self.pressNo:
            #     self.pressNo = False
            #     return
            self.start_plot()
            time.sleep(1)
            self.psw.enableOutput()
            self.sigInfo.emit(f"已打开电源输出")
            self.isOutput = True
            self.btn_Control(start_btn=False, stop_btn=True, start_listen=True, stop_listen=True, Btn_to36=True, Btn_to45=True, Btn_back42=True)
            return [True, ""]
        else:
            self.sigInfo.emit(f"请先连接电源")
            return [False, "Port not connected"]

    def output_close(self):
        # 关闭输出
        if self.found:
            self.found = False
            self.dataUpSignal.emit(f"./电源采集数据/{self.name}_{self.start_time}.csv")
        self.psw.enableOutput(False)
        self.sigInfo.emit(f"已关闭电源输出")
        self.isOutput = False
        time.sleep(1)
        if self.plot_thread.is_alive():
            self.StopFlag = True
            self.plot_thread.join()
        self.btn_Control(start_btn=True, stop_btn=True, Btn_to36=False, Btn_to45=False, Btn_back42=False)

    
    def output_close_tcp(self):
        # 关闭输出
        # if self.found:
        #     self.found = False  
        #     self.dataUpSignal.emit(f"./电源采集数据/{self.name}_{self.start_time}.csv")
        self.psw.enableOutput(False)
        self.sigInfo.emit(f"已关闭电源输出")
        self.isOutput = False
        time.sleep(1)
        if self.plot_thread.is_alive():
            self.StopFlag = True
            self.plot_thread.join()
        return [True, ""]


    def plot_callback(self):
        CH1_V = {"电压": 0}
        CH1_I = {"电流": 0}
        while not self.StopFlag:
            V, I = self.psw.getOutput()
            CH1_V["电压"] = V
            CH1_I["电流"] = I
            self.CurrentV = V
            self.CurrentI = I
            if I > self.safty:
                self.StopFlag = True
                self.current_warn.emit(f"{self.name}", f"CH1", f"{I}")
            # self.volatge_layout.updateData(CH1_V)
            # self.current_layout.updateData(CH1_I)
            self.volatge_signal.emit(CH1_V)
            self.current_signal.emit(CH1_I)
            # 创建一个CSV文件，保存采集的数据
            if not os.path.exists(f"./电源采集数据/"):
                os.mkdir(f"./电源采集数据/")
            if not os.path.exists(f"./电源采集数据/{self.name}_{self.start_time}.csv"):
                with open(f"./电源采集数据/{self.name}_{self.start_time}.csv", "w", encoding='gbk') as f:
                    f.write("时间,CH1电压,CH1电流\n")
            with open(f"./电源采集数据/{self.name}_{self.start_time}.csv", "a", encoding='gbk') as f:
                f.write(f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S.%f')[:-3]},{CH1_V['电压']},{CH1_I['电流']}\n")
            time.sleep(0.1)

    def get_value(self):
        return [self.CurrentV, self.CurrentI]

    def start_plot(self):
        # 启动动态画图
        self.StopFlag = False
        if not self.plot_thread.is_alive():
            self.start_time = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')[:-3]
            self.plot_thread = threading.Thread(target=self.plot_callback)
            self.plot_thread.start()
            self.sigInfo.emit(f"已开启采集")
        else:
            self.sigInfo.emit(f"采集已开启")
        self.btn_Control(start_listen=False, stop_listen=True, Btn_to36=True, Btn_to45=True, Btn_back42=True)

    def close_plot(self):
        # 关闭动态画图
        self.StopFlag = True
        if self.plot_thread.is_alive():
            self.plot_thread.join()
            self.sigInfo.emit(f"已关闭采集")
        else:
            self.sigInfo.emit(f"采集已关闭")
        self.btn_Control(start_listen=True, stop_listen=False, Btn_to36=False, Btn_to45=False, Btn_back42=False)


    def checkplot(self):
        return self.plot_thread.is_alive()
        

    @classmethod
    def get_instances(cls):
        return cls.instances
    
    def __del__(self):
        self.instances.remove(self)
