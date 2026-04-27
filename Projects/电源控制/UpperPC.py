# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import binascii
import pandas as pd
from PyQt5 import QtGui
# C:\Python\Python36\Scripts\pyinstaller.exe -F --noconsole --onefile -p D:\Coding\python\Pyserial-Demo-master\venv\Lib\site-packages pyserial_demo_2.py
import os.path

from Utility.MainWindow.MainWindow import Ui_MainWindow

from .方形电源控制 import SquarePower
from .长条电源控制 import LongPower
from .GPP电源控制 import GPPPower
from .MU_N电源控制 import MUNPower
# from .TCP import TCP
from .TCPServer import TCPServer
from .tool import *
from .FTP import FTPClient
from .alarm_player import AlarmPlayer
from .update_checker import UpdateCheckThread
from .update_installer import launch_update_installer
from .version_control import get_about_html, get_current_version
import configparser
import json

VERSION = get_current_version()

class AddPowerDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(AddPowerDialog, self).__init__(parent)
        self.setWindowTitle("添加电源")
        self.setModal(True)
        self.resize(340, 200)

        layout = QtWidgets.QVBoxLayout(self)
        self.form_layout = QtWidgets.QFormLayout()
        self.form_layout.setLabelAlignment(QtCore.Qt.AlignRight)

        self.power_type = QtWidgets.QComboBox(self)
        self.power_type.addItems(["GPW", "PSW", "GPP", "MU_N"])
        self.form_layout.addRow("电源类型：", self.power_type)

        self.power_name = QtWidgets.QLineEdit(self)
        self.power_name.setPlaceholderText("请输入电源名称")
        self.form_layout.addRow("电源名称：", self.power_name)

        self.channel_count_label = QtWidgets.QLabel("通道数：", self)
        self.channel_count = QtWidgets.QSpinBox(self)
        self.channel_count.setRange(2, 10)
        self.channel_count.setValue(3)
        self.form_layout.addRow(self.channel_count_label, self.channel_count)
        layout.addLayout(self.form_layout)

        button_box = QtWidgets.QDialogButtonBox(self)
        self.confirm_button = button_box.addButton("确认", QtWidgets.QDialogButtonBox.AcceptRole)
        button_box.addButton("取消", QtWidgets.QDialogButtonBox.RejectRole)
        self.confirm_button.clicked.connect(self._accept_if_valid)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        self.power_type.currentTextChanged.connect(self._update_dynamic_fields)
        self._update_dynamic_fields()

    def _accept_if_valid(self):
        if not self.get_power_name():
            QtWidgets.QMessageBox.warning(self, "提示", "请输入电源名称")
            return
        self.accept()

    def get_power_type(self):
        return self.power_type.currentText()

    def get_power_name(self):
        return self.power_name.text().strip()

    def get_channel_count(self):
        return self.channel_count.value()

    def _update_dynamic_fields(self):
        is_mun = self.get_power_type() == "MU_N"
        self.channel_count_label.setVisible(is_mun)
        self.channel_count.setVisible(is_mun)


class UpperPcWin(QtWidgets.QMainWindow,Ui_MainWindow):  # 主窗口只负责处理左侧按钮弹出窗口的逻辑
    leftBtnDict = {}  # 左侧按钮
    bindBtnWidget={}  # 右侧页面
    rightPageDict = {}
    portObjs={}
    istestData=False  # 是否测试数据
    # myWidgetObj=None  # 必须在 show 以后运行
    def __init__(self):
        super(UpperPcWin, self).__init__()
        self.setupUi(self)  # 必须放在 show 之后
        self.added_power_widgets = {}  # {name: widget_obj}
        self.initial_button_name = None
        self.startup_square_notified = False
        self.startup_long_notified = False
        self.startup_gpp_notified = False
        self.startup_auto_output_done = False
        self.version_about_dialog = None
        self.update_check_thread = None
        self.is_updating = False
        self.alarm_player = AlarmPlayer()
        self.adjustStartupWindow()
        self.setWindowTitle(f"[SRC] 光学头电源控制 {VERSION}")
        # self.ftp = FTPClient("192.168.10.100", "yab", "qwer1234!!")

        # self.initData()

    def initUi(self):  # 子页面需要的 ContextInfo 通过名称联系起来
        self.label.setText(VERSION)
        self.label.clicked.connect(self.openVersionAboutDialog)

        # 删除所有左侧按钮
        self.leftlayout = QGridLayout()

        self.addBTN()
        self.delBTN()
        cfg = Tool.read_config("Additional")

        self.power_control_obj5 = LongPower("长条电源")
        self.power_control_obj5.current_warn.connect(self.CurrentWarning)
        self.power_control_obj5.start_signal.connect(self.start_info)
        self.AddSubWin(self.power_control_obj5)
        self.power_control_obj5.dataUpSignal.connect(self.update_data)

        self.power_control_obj1 = SquarePower("方形电源")
        self.power_control_obj1.current_warn.connect(self.CurrentWarning)
        self.AddSubWin(self.power_control_obj1)

        self.power_control_obj_gpp = GPPPower("GPP")
        self.power_control_obj_gpp.current_warn.connect(self.CurrentWarning)
        self.AddSubWin(self.power_control_obj_gpp)

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
        gpp_resource = cfg.get("power_supply_gpp", "").strip()
        if gpp_resource and Tool.check_incombox(self.power_control_obj_gpp.portchoose, gpp_resource):
            self.power_control_obj_gpp.portchoose.setCurrentText(gpp_resource)
        elif self.power_control_obj_gpp.portchoose.count() > 0:
            self.power_control_obj_gpp.portchoose.setCurrentIndex(0)
        else:
            print("未找到 GPP 可用设备")
        self.startup_square_widgets = list(subwin_obj)
        self.startup_auto_connect = (cfg["auto_connect"] == "True")
        self.startup_auto_output = (cfg["auto_output"] == "True")
        cfg = Tool.read_config("Safty")
        for i in range(len(subwin_obj)):
            subwin_obj[i].ch1_safty = float(cfg[f"current_limit{i+1}_ch1"])
            subwin_obj[i].ch2_safty = float(cfg[f"current_limit{i+1}_ch2"])
            print(f"square safety ch1[{i+1}] = {subwin_obj[i].ch1_safty}")
            print(f"square safety ch2[{i+1}] = {subwin_obj[i].ch2_safty}")
        self.power_control_obj5.safty = float(cfg["current_limit5_ch1"])
        print(f"long safety = {self.power_control_obj5.safty}")
        self.power_control_obj_gpp.ch1_safty = float(cfg.get("current_limit_gpp_ch1", "100"))
        self.power_control_obj_gpp.ch2_safty = float(cfg.get("current_limit_gpp_ch2", "100"))
        print(f"gpp safety ch1 = {self.power_control_obj_gpp.ch1_safty}")
        print(f"gpp safety ch2 = {self.power_control_obj_gpp.ch2_safty}")

        self.loadPersistedAddedPowers()
        self.adjustStartupWindow()
        # QtCore.QTimer.singleShot(1000, self.runStartupDetection)
        # QtCore.QTimer.singleShot(1500, self.checkUpdateOnStartup)

    def getConfigPath(self):
        return os.path.join(root_path, "Auto_config.ini")

    def getPowerButtonStyle(self):
        return (
            "QPushButton {"
            "font: 12pt \"微软雅黑\";"
            "color: #1f2d3d;"
            "background-color: #eef3f8;"
            "border: 1px solid #b8c6d6;"
            "border-left: 6px solid #90a4b8;"
            "border-radius: 8px;"
            "padding: 10px 14px;"
            "text-align: left;"
            "min-height: 44px;"
            "}"
            "QPushButton:hover {"
            "background-color: #dfeaf7;"
            "border-color: #5f8fc7;"
            "}"
            "QPushButton:pressed {"
            "background-color: #0b5cab;"
            "color: #ffffff;"
            "border-color: #084785;"
            "}"
            "QPushButton:checked {"
            "font: 75 12pt \"微软雅黑\";"
            "color: #ffffff;"
            "background-color: #0f6bdc;"
            "border: 1px solid #084785;"
            "border-left: 10px solid #ffd34d;"
            "}"
        )

    def getComboPorts(self, combox):
        ports = []
        for i in range(combox.count()):
            port = combox.itemText(i).strip()
            if port and port not in ports:
                ports.append(port)
        return ports

    def getStartupCandidatePorts(self, widget_obj, config_port="", excluded_ports=None):
        ports = self.getComboPorts(widget_obj.portchoose)
        excluded_ports = excluded_ports or set()
        candidates = []

        for port in [str(config_port).strip(), widget_obj.portchoose.currentText().strip()]:
            if port and port in ports and port not in excluded_ports and port not in candidates:
                candidates.append(port)

        if len(ports) == 1:
            only_port = ports[0]
            if only_port not in excluded_ports and only_port not in candidates:
                candidates.append(only_port)

        return candidates

    def detectWidgetOnStartup(self, widget_obj, config_port="", keep_connected=False, excluded_ports=None):
        ports = self.getStartupCandidatePorts(widget_obj, config_port=config_port, excluded_ports=excluded_ports)
        original_port = widget_obj.portchoose.currentText().strip()

        for port in ports:
            widget_obj.portchoose.setCurrentText(port)
            result = widget_obj.startup_port_open()
            success = bool(result and result[0])
            if not success:
                continue

            if not keep_connected:
                widget_obj.power_port_close()
                widget_obj.portchoose.setCurrentText(port)
            return True, port

        available_ports = self.getComboPorts(widget_obj.portchoose)
        if original_port and Tool.check_incombox(widget_obj.portchoose, original_port):
            widget_obj.portchoose.setCurrentText(original_port)
        elif available_ports:
            widget_obj.portchoose.setCurrentText(available_ports[0])
        return False, None

    def detectStartupPowers(self, square_widgets, keep_connected=False):
        serial_cfg = Tool.read_config("Serial")
        occupied_ports = set()
        square_detected = False
        selected_button_name = "Btn" + self.power_control_obj5.name
        if square_widgets:
            square_detected, square_port = self.detectWidgetOnStartup(
                square_widgets[0],
                config_port=serial_cfg.get("power_supply_square1", ""),
                keep_connected=keep_connected,
                excluded_ports=occupied_ports
            )
        if square_detected and not self.startup_square_notified:
            QtWidgets.QMessageBox.information(self, "提示", f"已检测到方形电源：{square_port}")
            self.startup_square_notified = True
        if square_detected:
            selected_button_name = "Btn" + square_widgets[0].name
            occupied_ports.add(square_port)

        long_detected, long_port = self.detectWidgetOnStartup(
            self.power_control_obj5,
            config_port=serial_cfg.get("power_supply_long", ""),
            keep_connected=keep_connected,
            excluded_ports=occupied_ports
        )
        if long_detected and not self.startup_long_notified:
            QtWidgets.QMessageBox.information(self, "提示", f"已检测到长条电源：{long_port}")
            self.startup_long_notified = True
        if long_detected:
            occupied_ports.add(long_port)

        gpp_detected, gpp_port = self.detectWidgetOnStartup(
            self.power_control_obj_gpp,
            config_port=serial_cfg.get("power_supply_gpp", ""),
            keep_connected=keep_connected,
            excluded_ports=occupied_ports
        )
        if gpp_detected and not self.startup_gpp_notified:
            QtWidgets.QMessageBox.information(self, "提示", f"已检测到GPP电源：{gpp_port}")
            self.startup_gpp_notified = True
        if gpp_detected and not square_detected and not long_detected:
            selected_button_name = "Btn" + self.power_control_obj_gpp.name

        if not square_detected and not long_detected and not gpp_detected:
            QtWidgets.QMessageBox.information(self, "提示", "未检测到电源设备")

        return selected_button_name, square_detected, long_detected, gpp_detected

    def runStartupDetection(self):
        self.initial_button_name, square_detected, long_detected, gpp_detected = self.detectStartupPowers(
            self.startup_square_widgets,
            keep_connected=self.startup_auto_connect
        )

        if self.startup_auto_output and not self.startup_auto_output_done:
            for widget_obj in self.startup_square_widgets:
                if widget_obj.isConnected:
                    widget_obj.start_btn.click()
            if self.power_control_obj5.isConnected:
                self.power_control_obj5.start_btn.click()
            if self.power_control_obj_gpp.isConnected:
                self.power_control_obj_gpp.start_btn.click()
            self.startup_auto_output_done = True

        if square_detected and self.initial_button_name and self.initial_button_name in self.leftBtnDict:
            self.leftBtnCallback(self.initial_button_name)
        elif gpp_detected and ("Btn" + self.power_control_obj_gpp.name) in self.leftBtnDict:
            self.leftBtnCallback("Btn" + self.power_control_obj_gpp.name)
        elif ("Btn" + self.power_control_obj5.name) in self.leftBtnDict:
            self.leftBtnCallback("Btn" + self.power_control_obj5.name)

    def loadPersistedAddedPowers(self):
        config = configparser.ConfigParser()
        config.read(self.getConfigPath(), encoding="utf-8")

        raw_items = "[]"
        if config.has_section("CustomPower"):
            raw_items = config.get("CustomPower", "items", fallback="[]")

        try:
            power_items = json.loads(raw_items)
        except Exception:
            power_items = []

        for item in power_items:
            if not isinstance(item, dict):
                continue

            power_type = item.get("type")
            power_name = str(item.get("name", "")).strip()
            if power_type not in ["GPW", "PSW", "GPP", "MU_N"] or not power_name:
                continue
            if self.power_name_exists(power_name):
                continue

            widget_obj = self.create_power_widget(
                power_type,
                power_name,
                channel_count=item.get("channels"),
            )
            self.AddSubWin(widget_obj)
            self.added_power_widgets[power_name] = widget_obj

    def savePersistedAddedPowers(self):
        config = configparser.ConfigParser()
        config.read(self.getConfigPath(), encoding="utf-8")

        if not config.has_section("CustomPower"):
            config.add_section("CustomPower")

        power_items = []
        for widget_obj in self.added_power_widgets.values():
            item = {"name": widget_obj.name}
            if isinstance(widget_obj, LongPower):
                item["type"] = "PSW"
            elif isinstance(widget_obj, GPPPower):
                item["type"] = "GPP"
            elif isinstance(widget_obj, MUNPower):
                item["type"] = "MU_N"
                item["channels"] = widget_obj.channel_count
            else:
                item["type"] = "GPW"
            power_items.append(item)

        for section_name in list(config.sections()):
            if section_name.startswith("MU_N_LIMITS:"):
                config.remove_section(section_name)

        config.set("CustomPower", "items", json.dumps(power_items, ensure_ascii=False))
        for widget_obj in self.added_power_widgets.values():
            if not isinstance(widget_obj, MUNPower):
                continue
            section_name = f"MU_N_LIMITS:{widget_obj.name}"
            if not config.has_section(section_name):
                config.add_section(section_name)
            for option, value in widget_obj.export_limit_settings().items():
                config.set(section_name, option, value)
        with open(self.getConfigPath(), "w", encoding="utf-8") as f:
            config.write(f)

    def adjustStartupWindow(self):
        screen = QtWidgets.QApplication.primaryScreen()
        if screen is None:
            return

        available = screen.availableGeometry()
        width_margin = 24
        height_margin = 24
        target_width = min(self.width(), max(available.width() - width_margin, 0))
        target_height = min(self.height(), max(available.height() - height_margin, 0))

        if target_width > 0 and target_height > 0:
            self.resize(target_width, target_height)

        x = available.x() + max((available.width() - self.width()) // 2, 0)
        y = available.y() + max((available.height() - self.height()) // 2, 0)
        self.move(x, y)

    def showAbout(self):
        # 读取 CSV 文件
        df = pd.read_csv("更新内容.csv", header=None, names=["version", "notes"])
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
        # 设置布局边距
        layout.setContentsMargins(10, 10, 10, 10)
        # 显示窗口
        aboutWin.show()

    def showVersionAbout(self):
        aboutWin = QtWidgets.QDialog(self)
        aboutWin.setWindowTitle("关于")
        aboutWin.resize(520, 360)
        aboutWin.setStyleSheet("background-color: #FFFFFF;color: #000000;font: 12pt \"微软雅黑\";")

        aboutText = QtWidgets.QTextEdit(aboutWin)
        aboutText.setReadOnly(True)
        aboutText.setHtml(get_about_html())

        layout = QtWidgets.QVBoxLayout(aboutWin)
        layout.addWidget(aboutText)
        layout.setContentsMargins(10, 10, 10, 10)
        aboutWin.show()

    def openVersionAboutDialog(self):
        if self.version_about_dialog is not None:
            self.version_about_dialog.show()
            self.version_about_dialog.raise_()
            self.version_about_dialog.activateWindow()
            return

        aboutWin = QtWidgets.QDialog(self)
        self.version_about_dialog = aboutWin
        aboutWin.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        aboutWin.destroyed.connect(self._clearVersionAboutDialog)
        aboutWin.setWindowTitle("关于")
        aboutWin.resize(400, 300)
        aboutWin.setStyleSheet("background-color: #FFFFFF;color: #000000;font: 12pt \"微软雅黑\";")

        aboutText = QtWidgets.QTextEdit(aboutWin)
        aboutText.setReadOnly(True)
        aboutText.setHtml(get_about_html())

        layout = QtWidgets.QVBoxLayout(aboutWin)
        layout.addWidget(aboutText)
        layout.setContentsMargins(10, 10, 10, 10)
        aboutWin.show()

    def _clearVersionAboutDialog(self, *args):
        self.version_about_dialog = None

    def checkUpdateOnStartup(self):
        try:
            cfg = Tool.read_config("Update")
        except Exception as e:
            print(f"读取更新配置失败: {e}")
            return

        if cfg.get("enabled", "False") != "True":
            return
        if cfg.get("check_on_startup", "True") != "True":
            return

        manifest_url = cfg.get("manifest_url", "").strip()
        if not manifest_url:
            print("manifest_url is empty, skip update check")
            return

        if self.update_check_thread is not None and self.update_check_thread.isRunning():
            return

        try:
            timeout = int(cfg.get("request_timeout", "3"))
        except Exception:
            timeout = 3

        self.update_check_thread = UpdateCheckThread(VERSION, manifest_url, timeout, self)
        self.update_check_thread.update_checked.connect(self._handleUpdateCheckResult)
        self.update_check_thread.finished.connect(self._clearUpdateCheckThread)
        self.update_check_thread.start()

    def _openUpdateDownload(self, download_url):
        if download_url.startswith("http://") or download_url.startswith("https://") or download_url.startswith("file://"):
            QtGui.QDesktopServices.openUrl(QtCore.QUrl(download_url))
            return

        local_path = os.path.abspath(download_url)
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(local_path))

    def _clearUpdateCheckThread(self):
        self.update_check_thread = None

    def _handleUpdateCheckResult(self, result):
        if not result.success:
            print(f"更新检测失败: {result.error_message}")
            return

        if not result.has_update:
            print(f"当前已是最新版本: {VERSION}")
            return

        message = f"检测到新版本：{result.latest_version}\n当前版本：{VERSION}"
        if result.release_notes:
            message += f"\n\n更新内容：\n{result.release_notes}"

        if result.download_url:
            buttons = QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel
            reply = QtWidgets.QMessageBox.question(
                self,
                "发现新版本",
                message + "\n\n点击“确定”后将自动下载、替换并重启程序。",
                buttons,
                QtWidgets.QMessageBox.Ok
            )
            if reply == QtWidgets.QMessageBox.Ok:
                self._startAutoUpdate(result.download_url)
            return

        QtWidgets.QMessageBox.information(self, "发现新版本", message)

    def _startAutoUpdate(self, download_url):
        try:
            launch_update_installer(download_url)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "更新失败", f"启动自动更新失败：{e}")
            return

        self.is_updating = True
        QtWidgets.QMessageBox.information(self, "开始更新", "已开始自动更新，程序将关闭并在更新完成后自动重启。")
        self.close()

    def update_data(self, filename):
        # 上传电源记录
        if not hasattr(self, "ftp"):
            print("FTP 未初始化，跳过上传")
            return

        json_data = json.load(open((os.path.expanduser("~")+"\\AppData\\Local\\YabCom\\common\\config\\terminal_recent_projects.json"), 'r', encoding='utf-8'))
        print(json_data)
        number = json_data[0]["Numbers"]
        ftp_dir = (
            f"/组网星01测试数据/02 每日历史数据/"
            f"正样{number}/{datetime.datetime.now().strftime('%Y%m%d')}/电源数据"
        )
        if not self.ftp.check_ftp_directory_exists(ftp_dir):
            self.ftp.make_dir(ftp_dir)
        self.ftp.moveto_dir(ftp_dir)
        self.ftp.upload_file(filename)

    def CurrentWarning(self, str1, str2, str3):
        self.alarm_player.play_warning()
        QtWidgets.QMessageBox.warning(self, f"{str1}警告", f"电流过高，请检查电源电流是否过高，当前{str2}电流为{str3}A")

    def VoltageWarning(self, str1, str2, str3):
        self.alarm_player.play_warning()
        QtWidgets.QMessageBox.warning(self, f"{str1}告警", f"电压过高，请检查电源电压是否过高，当前{str2}电压为{str3}V")

    def start_info(self, name, v, i):
        reply = QtWidgets.QMessageBox.question(self,
                                               f'{name}',
                                               f"当前设置电压{v}V，电流{i}A，是否正确？",
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
        AddBtnCustom.setText("添加电源")
        AddBtnCustom.clicked.connect(self.openAddPowerDialog)

    def delBTN(self):
        DelBtnCustom = QtWidgets.QPushButton(self.frame_left)
        DelBtnCustom.setStyleSheet("font: 12pt \"微软雅黑\";")
        DelBtnCustom.setObjectName("delBtn")
        n=self.leftlayout.count()
        self.leftlayout.addWidget(DelBtnCustom, n, 0)
        self.frame_left.setLayout(self.leftlayout)
        DelBtnCustom.setText("删除电源")
        DelBtnCustom.clicked.connect(self.openDeletePowerDialog)

    def openAddPowerDialog(self):
        add_dialog = AddPowerDialog(self)
        if add_dialog.exec_() != QtWidgets.QDialog.Accepted:
            return

        power_type = add_dialog.get_power_type()
        power_name = add_dialog.get_power_name()
        channel_count = add_dialog.get_channel_count() if power_type == "MU_N" else None

        if self.power_name_exists(power_name):
            QtWidgets.QMessageBox.warning(self, "提示", f"电源名称“{power_name}”已存在，请重新命名")
            return

        widget_obj = self.create_power_widget(power_type, power_name, channel_count=channel_count)
        self.AddSubWin(widget_obj)
        self.added_power_widgets[power_name] = widget_obj
        self.savePersistedAddedPowers()
        self.leftBtnCallback("Btn" + widget_obj.name)

    def power_name_exists(self, power_name):
        return ("Btn" + power_name) in self.leftBtnDict

    def create_power_widget(self, power_type, power_name, channel_count=None):
        if power_type == "PSW":
            widget_obj = LongPower(power_name)
            widget_obj.current_warn.connect(self.CurrentWarning)
            widget_obj.start_signal.connect(self.start_info)
            widget_obj.dataUpSignal.connect(self.update_data)
            return widget_obj
        if power_type == "GPP":
            widget_obj = GPPPower(power_name)
            widget_obj.current_warn.connect(self.CurrentWarning)
            return widget_obj
        if power_type == "MU_N":
            widget_obj = MUNPower(
                power_name,
                channel_count=channel_count or 3,
            )
            widget_obj.current_warn.connect(self.CurrentWarning)
            widget_obj.voltage_warn.connect(self.VoltageWarning)
            widget_obj.structure_changed.connect(self.savePersistedAddedPowers)
            return widget_obj

        widget_obj = SquarePower(power_name)
        widget_obj.current_warn.connect(self.CurrentWarning)
        return widget_obj

    def removeLastAddedPower(self):
        if not self.added_power_widgets:
            QtWidgets.QMessageBox.information(self, "提示", "当前没有可删除的新增电源")
            return
        last_name = next(reversed(self.added_power_widgets))
        self.DelSubWin(self.added_power_widgets[last_name])

    def openDeletePowerDialog(self):
        if not self.added_power_widgets:
            QtWidgets.QMessageBox.information(self, "提示", "当前没有可删除的新增电源")
            return

        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("删除电源")
        dialog.setModal(True)
        dialog.resize(300, 130)

        layout = QtWidgets.QVBoxLayout(dialog)
        form = QtWidgets.QFormLayout()
        form.setLabelAlignment(QtCore.Qt.AlignRight)

        combo = QtWidgets.QComboBox(dialog)
        for name in self.added_power_widgets:
            combo.addItem(name)
        form.addRow("选择要删除的电源：", combo)
        layout.addLayout(form)

        button_box = QtWidgets.QDialogButtonBox(dialog)
        confirm_btn = button_box.addButton("删除", QtWidgets.QDialogButtonBox.AcceptRole)
        confirm_btn.setStyleSheet("color: #c0392b;")
        button_box.addButton("取消", QtWidgets.QDialogButtonBox.RejectRole)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return

        selected_name = combo.currentText()
        if selected_name not in self.added_power_widgets:
            return

        reply = QtWidgets.QMessageBox.question(
            self,
            "确认删除",
            f'确定要删除电源"{selected_name}"吗？',
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if reply == QtWidgets.QMessageBox.Yes:
            self.DelSubWin(self.added_power_widgets[selected_name])

    def showPowerContextMenu(self, widgetObj, button, pos):
        menu = QtWidgets.QMenu(button)
        delete_action = menu.addAction("删除电源")
        operation_logger = QtWidgets.QApplication.instance().property("operation_logger")
        if operation_logger is not None:
            operation_logger.track_action(delete_action)

        if widgetObj not in self.added_power_widgets.values():
            delete_action.setEnabled(False)
        else:
            delete_action.triggered.connect(lambda: self.DelSubWin(widgetObj))

        menu.exec_(button.mapToGlobal(pos))

    def AddSubWin(self,widgetObj, show_controls=True):
        # 增加左侧按钮
        # self.leftlayout=QGridLayout()
        BtnCustom = QtWidgets.QPushButton(self.frame_left)
        BtnCustom.setStyleSheet(self.getPowerButtonStyle())
        BtnCustom.setCheckable(True)
        BtnCustom.setObjectName("Btn"+widgetObj.name)
        n=self.leftlayout.count()
        self.leftlayout.addWidget(BtnCustom, n, 0)
        self.frame_left.setLayout(self.leftlayout)  # 这个必须动态加入才能自动布局

        BtnCustom.setText(widgetObj.name)  # 自定义页面名称
        BtnCustom.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        BtnCustom.customContextMenuRequested.connect(
            lambda pos, obj=widgetObj, btn=BtnCustom: self.showPowerContextMenu(obj, btn, pos)
        )

        # 增加右侧 stackedWidget 的页面
        page_custom = QtWidgets.QWidget()
        page_custom.setObjectName("Page"+widgetObj.name)
        self.gridLayout_custom = QtWidgets.QGridLayout(page_custom)
        self.gridLayout_custom.setObjectName("gridLayout_custom")
        self.gridLayout_custom.setContentsMargins(1, 1, 1, 1)

        if show_controls:
            widgetObj.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
            if isinstance(widgetObj, (SquarePower, LongPower)):
                self.gridLayout_custom.setContentsMargins(0, 0, 0, 0)
                self.gridLayout_custom.addWidget(widgetObj, 0, 0, 1, 1)
            else:
                scroll_area = QtWidgets.QScrollArea(page_custom)
                scroll_area.setObjectName("Scroll"+widgetObj.name)
                scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
                scroll_area.setWidgetResizable(True)
                scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
                scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
                scroll_area.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
                if isinstance(widgetObj, MUNPower):
                    widgetObj.setMinimumHeight(0)
                else:
                    widgetObj.adjustSize()
                    widgetObj.setMinimumSize(widgetObj.sizeHint())
                scroll_area.setWidget(widgetObj)
                self.gridLayout_custom.addWidget(scroll_area, 1, 1, 1, 1)

        self.stackedWidget.addWidget(page_custom)  # 添加到右侧 stackedWidget

        self.bindBtnWidget[BtnCustom.objectName()] = page_custom.objectName()
        self.leftBtnDict [BtnCustom.objectName()] = BtnCustom
        self.rightPageDict[BtnCustom.objectName() ]=page_custom

        # 绑定页面与按钮
        BtnCustom.clicked.connect( lambda: self.leftBtnCallback(BtnCustom.objectName()) )

    def DelSubWin(self,widgetObj):
        # 删除左侧按钮
        BtnCustom=self.leftBtnDict["Btn"+widgetObj.name]
        self.leftlayout.removeWidget(BtnCustom)
        BtnCustom.deleteLater()
        BtnCustom.setParent(None)

        # 删除右侧 stackedWidget 的页面
        page_custom=self.rightPageDict["Btn"+widgetObj.name]
        self.stackedWidget.removeWidget(page_custom)
        page_custom.deleteLater()
        page_custom.setParent(None)

        # 删除按钮与页面的绑定
        del self.leftBtnDict["Btn"+widgetObj.name]
        del self.rightPageDict["Btn"+widgetObj.name]
        del self.bindBtnWidget[BtnCustom.objectName()]

        # 删除页面对应对象
        if widgetObj:
            if widgetObj in self.added_power_widgets.values():
                self.added_power_widgets.pop(widgetObj.name, None)
            if isinstance(widgetObj, SquarePower) and widgetObj in SquarePower.get_instances():
                SquarePower.get_instances().remove(widgetObj)
            if isinstance(widgetObj, LongPower) and widgetObj in LongPower.get_instances():
                LongPower.get_instances().remove(widgetObj)
            if isinstance(widgetObj, GPPPower) and widgetObj in GPPPower.get_instances():
                GPPPower.get_instances().remove(widgetObj)
            if isinstance(widgetObj, MUNPower) and widgetObj in MUNPower.get_instances():
                MUNPower.get_instances().remove(widgetObj)
            self.savePersistedAddedPowers()

        if self.leftBtnDict:
            self.leftBtnCallback(next(iter(self.leftBtnDict)))

    def leftBtnCallback(self,BtnobjectName):

        for k, v in self.leftBtnDict.items():
            if k==BtnobjectName:
                self.stackedWidget.setCurrentWidget(self.rightPageDict[k] )
                self.leftBtnDict[k].setChecked(True)

            else:
                self.leftBtnDict[k].setChecked(False)

    def CreateDbEngine(self):
        # TODO: 创建数据库引擎，并创建访问锁
        pass

    def closeEvent(self, event):
        if self.is_updating:
            event.accept()
            os._exit(0)
            return

        reply = QtWidgets.QMessageBox.question(
            self,
            "退出确认",
            "是否退出程序？",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if reply == QtWidgets.QMessageBox.Yes:
            event.accept()
            os._exit(0)
        else:
            event.ignore()

