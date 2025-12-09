# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import binascii
import pandas as pd
# C:\Python\Python36\Scripts\pyinstaller.exe -F --noconsole --onefile -p D:\Coding\python\Pyserial-Demo-master\venv\Lib\site-packages pyserial_demo_2.py
import os.path

# grandfaPath=os.path.abspath(os.path.dirname(os.getcwd()) + os.path.sep + "..")
# sys.path.append(grandfaPath) #需要加入爷爷目录，否则无法导入其他包
from Utility.MainWindow.MainWindow import Ui_MainWindow

from .方形电源控制 import SquarePower
from .长条电源控制 import LongPower
# from .TCP import TCP
from .TCPServer import TCPServer
from .tool import *
from .FTP import FTPClient
import json

VERSION = "Unknown" if not os.path.exists("更新内容.csv") or \
    pd.read_csv("更新内容.csv", header=None, index_col=None).iloc[-1, 0] is None \
    else pd.read_csv("更新内容.csv", header=None, index_col=None).iloc[-1, 0]

class UpperPcWin(QtWidgets.QMainWindow,Ui_MainWindow): #主窗口只负责处理左侧按钮弹出窗口的逻辑

    leftBtnDict = {} #左侧按钮
    bindBtnWidget={} #右侧页面
    rightPageDict = {}
    portObjs={}
    istestData=False #是否测试数据
    # myWidgetObj=None #必须在show以后运行
    def __init__(self):
        super(UpperPcWin, self).__init__()
        self.setupUi(self) #必须放在show之后
        self.setWindowTitle(f"光学头电源控制{VERSION}")
        # self.ftp = FTPClient("192.168.10.100", "yab", "qwer1234!!")

        # self.initData()

    def initUi(self):  #子页面的需要的ContextInfo通过名称联系起来
        self.label.setText(VERSION)
        self.label.clicked.connect(self.showAbout)

        #删除所有左侧按钮
        self.leftlayout = QGridLayout()

        cfg = Tool.read_config("Additional")
        if cfg["power_add"] == "True":
            self.addBTN()
        if cfg["power_del"] == "True":
            self.delBTN()

        self.power_control_obj5 = LongPower("长条电源")
        self.power_control_obj5.current_warn.connect(self.CurrentWarning)
        self.power_control_obj5.start_signal.connect(self.start_info)
        self.AddSubWin(self.power_control_obj5)
        self.power_control_obj5.dataUpSignal.connect(self.update_data)

        self.power_control_obj1 = SquarePower("方形电源1")
        self.power_control_obj1.current_warn.connect(self.CurrentWarning)
        self.AddSubWin(self.power_control_obj1)

        self.power_control_obj2 = SquarePower("方形电源2")
        self.power_control_obj2.current_warn.connect(self.CurrentWarning)
        self.AddSubWin(self.power_control_obj2)

        subwin_obj = SquarePower.get_instances()

        # self.tcp = TCP("TCP")

        server = TCPServer()
        server.start()
        

        cfg = Tool.read_config("Serial")
        for i in range(len(subwin_obj)):
            if Tool.check_incombox(subwin_obj[i].portchoose, cfg[f"power_supply_square{i+1}"]):
                subwin_obj[i].portchoose.setCurrentText(cfg[f"power_supply_square{i+1}"])
            else:
                subwin_obj[i].portchoose.setCurrentText("COM1")
                print("未找到串口配置，使用默认配置")
        if Tool.check_incombox(self.power_control_obj5.portchoose, cfg["power_supply_long"]):
            self.power_control_obj5.portchoose.setCurrentText(cfg["power_supply_long"])
        else:
            self.power_control_obj5.portchoose.setCurrentText("COM1")
            print("未找到串口配置，使用默认配置")
        if cfg["auto_connect"] == "True":
            for i in range(len(subwin_obj)):
                subwin_obj[i].portopen.click()
            self.power_control_obj5.portopen.click()
        if cfg["auto_output"] == "True":
            for i in range(len(subwin_obj)):
                subwin_obj[i].start_btn.click()
            self.power_control_obj5.start_btn.click()
        cfg = Tool.read_config("Safty")
        for i in range(len(subwin_obj)):
            subwin_obj[i].ch1_safty = float(cfg[f"current_limit{i+1}_ch1"])
            subwin_obj[i].ch2_safty = float(cfg[f"current_limit{i+1}_ch2"])
            print(f"当前限位{i+1}：{subwin_obj[i].ch1_safty}")
            print(f"当前限位{i+1}：{subwin_obj[i].ch2_safty}")
        self.power_control_obj5.safty = float(cfg["current_limit5_ch1"])
        print(f"当前限位5：{self.power_control_obj5.safty}")

    def showAbout(self):
        # 读取 CSV 文件
        df = pd.read_csv("更新内容.csv", header=None, names=["版本号", "更新内容"])
        # 将 DataFrame 转换为 HTML 表格字符串
        html_table = df.to_html(index=False, border=1)
        # 创建关于窗口
        aboutWin = QtWidgets.QDialog(self)
        aboutWin.setWindowTitle("关于")
        aboutWin.resize(400, 300)
        aboutWin.setStyleSheet("background-color: #FFFFFF;color: #000000;font: 12pt \"微软雅黑\";")
        # 创建 QTextEdit 控件
        aboutText = QtWidgets.QTextEdit(aboutWin)
        aboutText.setReadOnly(True)
        aboutText.setHtml(html_table)  # 设置 HTML 内容
        # 使用布局管理器
        layout = QtWidgets.QVBoxLayout(aboutWin)
        layout.addWidget(aboutText)  # 将 QTextEdit 添加到布局中
        # 设置布局的边距（可选）
        layout.setContentsMargins(10, 10, 10, 10)
        # 显示窗口
        aboutWin.show()

    def update_data(self, filename):
        # 上传电源记录
        json_data = json.load(open((os.path.expanduser("~")+"\\AppData\\Local\\YabCom\\common\\config\\terminal_recent_projects.json"), 'r', encoding='utf-8'))
        print(json_data)
        project = json_data[0]["Name"]
        number = json_data[0]["Numbers"]
        if not self.ftp.check_ftp_directory_exists(f"/组网星/01 测试数据/02 每日历史数据/正样{number}/{datetime.datetime.now().strftime('%Y%m%d')}/电源数据"):
            self.ftp.make_dir(f"/组网星/01 测试数据/02 每日历史数据/正样{number}/{datetime.datetime.now().strftime('%Y%m%d')}/电源数据")
        self.ftp.moveto_dir(f"/组网星/01 测试数据/02 每日历史数据/正样{number}/{datetime.datetime.now().strftime('%Y%m%d')}/电源数据")
        self.ftp.upload_file(filename)
        pass

    def CurrentWarning(self, str1, str2, str3):
        QtWidgets.QMessageBox.warning(self, f"{str1}警告", f"电流过高，请检查电源电流是否过高，当前{str2}电流为{str3}A")

    def start_info(self, name, v, i):
        reply = QtWidgets.QMessageBox.question(self,
                                               f'{name}',
                                               f"当前设置电压{v}V,电流{i}A是否正确？",
                                               QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                                               QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            self.power_control_obj5.pressNo = False
        else:
            self.power_control_obj5.pressNo = True


    def addBTN(self):
        AddBtnCustom = QtWidgets.QPushButton(self.frame_left)
        AddBtnCustom.setStyleSheet("font: 12pt \"微软雅黑\";")
        AddBtnCustom.setObjectName("addBtn")
        n=self.leftlayout.count()
        self.leftlayout.addWidget(AddBtnCustom, n, 0)
        self.frame_left.setLayout(self.leftlayout)
        AddBtnCustom.setText("addBtn")
        AddBtnCustom.clicked.connect(lambda: self.AddSubWin(SquarePower(f"方形电源{SquarePower.get_instances().__len__()+1}")))

    def delBTN(self):
        DelBtnCustom = QtWidgets.QPushButton(self.frame_left)
        DelBtnCustom.setStyleSheet("font: 12pt \"微软雅黑\";")
        DelBtnCustom.setObjectName("delBtn")
        n=self.leftlayout.count()
        self.leftlayout.addWidget(DelBtnCustom, n, 0)
        self.frame_left.setLayout(self.leftlayout)
        DelBtnCustom.setText("delBtn")
        DelBtnCustom.clicked.connect(lambda: self.DelSubWin(SquarePower.get_instances()[-1]))

    def AddSubWin(self,widgetObj):
        #增加左侧按钮
        # self.leftlayout=QGridLayout()
        BtnCustom = QtWidgets.QPushButton(self.frame_left)
        BtnCustom.setStyleSheet("font: 12pt \"微软雅黑\";")
        BtnCustom.setCheckable(True)
        BtnCustom.setObjectName("Btn"+widgetObj.name)
        n=self.leftlayout.count()
        self.leftlayout.addWidget(BtnCustom, n, 0)
        self.frame_left.setLayout(self.leftlayout) #这个必须动态加入才能自动布局

        BtnCustom.setText(widgetObj.name)#自定义页面的名字

        #增加右侧stackwidhet的页面
        page_custom = QtWidgets.QWidget()
        page_custom.setObjectName("Page"+widgetObj.name)
        self.gridLayout_custom = QtWidgets.QGridLayout(page_custom)
        self.gridLayout_custom.setObjectName("gridLayout_custom")
        self.gridLayout_custom.setContentsMargins(1, 1, 1, 1)

        self.gridLayout_custom.addWidget(widgetObj,1,1,1,1)

        self.stackedWidget.addWidget(page_custom) #添加到右侧stackedWidget

        self.bindBtnWidget[BtnCustom.objectName()] = page_custom.objectName()
        self.leftBtnDict [BtnCustom.objectName()] = BtnCustom
        self.rightPageDict[BtnCustom.objectName() ]=page_custom

        #绑定页面与按钮
        BtnCustom.clicked.connect( lambda: self.leftBtnCallback(BtnCustom.objectName()) )

    def DelSubWin(self,widgetObj):
        #删除左侧按钮
        BtnCustom=self.leftBtnDict["Btn"+widgetObj.name]
        self.leftlayout.removeWidget(BtnCustom)
        BtnCustom.deleteLater()
        BtnCustom.setParent(None)

        #删除右侧stackedWidget的页面
        page_custom=self.rightPageDict["Btn"+widgetObj.name]
        self.stackedWidget.removeWidget(page_custom)
        page_custom.deleteLater()
        page_custom.setParent(None)

        #删除按钮与页面的绑定
        del self.leftBtnDict["Btn"+widgetObj.name]
        del self.rightPageDict["Btn"+widgetObj.name]
        del self.bindBtnWidget[BtnCustom.objectName()]

        #删除页面的对象
        if widgetObj:
            del SquarePower.get_instances()[-1]

    def leftBtnCallback(self,BtnobjectName):

        for k, v in self.leftBtnDict.items():
            if k==BtnobjectName:
                self.stackedWidget.setCurrentWidget(self.rightPageDict[k] )
                self.leftBtnDict[k].setChecked(True)

            else:
                self.leftBtnDict[k].setChecked(False)


    def CreateDbEngine(self):
        #todo 创建数据库引擎，并创建访问锁
        pass

    def closeEvent(self, event):
        """
        重写closeEvent方法，实现dialog窗体关闭时执行一些代码
        :param event: close()触发的事件
        :return: None
        """
        reply = QtWidgets.QMessageBox.question(self,
                                               '本程序',
                                               "是否要退出程序？",
                                               QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                                               QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:

            event.accept()

            os._exit(0)

        else:
            event.ignore()
