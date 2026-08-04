# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import threading
import pandas as pd
import os.path

from Utility.MainWindow.MainWindow import Ui_MainWindow

from .方形电源控制 import SquarePower
from .长条电源控制 import LongPower
from .TCPServer import TCPServer
from .power_settings import PowerSettingsDialog
from .tool import *
from .FTP import FTPClient
import json
import sys

VERSION = "Unknown" if not os.path.exists("更新内容.csv") or \
    pd.read_csv("更新内容.csv", header=None, index_col=None).iloc[-1, 0] is None \
    else pd.read_csv("更新内容.csv", header=None, index_col=None).iloc[-1, 0]

# 仅突出「顺序上下电」按钮；其余控件使用 PyQt5 / 系统默认样式
_SEQ_BTN_STYLE = """
    QPushButton#seq_on_btn {
        background-color: #2e7d32;
        color: white;
        font: 11pt "微软雅黑";
        padding: 6px;
    }
    QPushButton#seq_on_btn:hover {
        background-color: #388e3c;
    }
    QPushButton#seq_on_btn:pressed {
        background-color: #1b5e20;
    }
    QPushButton#seq_on_btn:disabled {
        background-color: #a5d6a7;
        color: #f5f5f5;
    }
    QPushButton#seq_off_btn {
        background-color: #c62828;
        color: white;
        font: 11pt "微软雅黑";
        padding: 6px;
    }
    QPushButton#seq_off_btn:hover {
        background-color: #d32f2f;
    }
    QPushButton#seq_off_btn:pressed {
        background-color: #b71c1c;
    }
    QPushButton#seq_off_btn:disabled {
        background-color: #ef9a9a;
        color: #f5f5f5;
    }
"""


class UpperPcWin(QtWidgets.QMainWindow, Ui_MainWindow):
    """主窗口：管理左侧导航与右侧电源页面切换"""

    _seq_ui_signal = pyqtSignal(bool, bool, str)  # is_power_on, success, error_message

    leftBtnDict = {}
    bindBtnWidget = {}
    rightPageDict = {}
    portObjs = {}
    istestData = False

    def __init__(self):
        super(UpperPcWin, self).__init__()
        self.setupUi(self)
        self.setWindowTitle(f"光学头电源控制{VERSION}")
        self._seq_ui_signal.connect(self._on_seq_finished)

    def initUi(self):
        """初始化左侧三区布局，然后加载设备与 TCP 服务"""
        self.label.setText(VERSION)
        self.label.clicked.connect(self.showAbout)

        # ── 顶部固定区：版本号 + 设置按钮 ─────────────────────────
        top_frame = QtWidgets.QFrame()
        top_layout = QtWidgets.QVBoxLayout(top_frame)
        top_layout.setContentsMargins(6, 8, 6, 6)
        top_layout.setSpacing(6)
        top_layout.addWidget(self.label)

        self.settings_btn = QtWidgets.QPushButton("电源设置")
        self.settings_btn.setObjectName("settings_btn")
        self.settings_btn.setStyleSheet("font: 12pt \"微软雅黑\";")
        self.settings_btn.clicked.connect(self.show_power_settings)
        top_layout.addWidget(self.settings_btn)

        # ── 分隔线 ─────────────────────────────────────────────────
        sep1 = QtWidgets.QFrame()
        sep1.setFrameShape(QtWidgets.QFrame.HLine)
        sep1.setFrameShadow(QtWidgets.QFrame.Sunken)

        # ── 中间弹性区：设备切换按钮（可滚动）─────────────────────
        self.device_btn_widget = QtWidgets.QWidget()
        self.device_btn_widget.setObjectName("device_btn_widget")
        self.device_btn_layout = QtWidgets.QVBoxLayout(self.device_btn_widget)
        self.device_btn_layout.setContentsMargins(6, 6, 6, 6)
        self.device_btn_layout.setSpacing(4)
        self.device_btn_layout.setAlignment(Qt.AlignTop)

        device_scroll = QtWidgets.QScrollArea()
        device_scroll.setWidget(self.device_btn_widget)
        device_scroll.setWidgetResizable(True)
        device_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        device_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # ── 分隔线 ─────────────────────────────────────────────────
        sep2 = QtWidgets.QFrame()
        sep2.setFrameShape(QtWidgets.QFrame.HLine)
        sep2.setFrameShadow(QtWidgets.QFrame.Sunken)

        # ── 底部固定区：顺序上下电（远离切换按钮，防止误触）───────
        bottom_frame = QtWidgets.QFrame()
        bottom_layout = QtWidgets.QVBoxLayout(bottom_frame)
        bottom_layout.setContentsMargins(6, 6, 6, 8)
        bottom_layout.setSpacing(6)

        self.seq_on_btn = QtWidgets.QPushButton("顺序上电")
        self.seq_on_btn.setObjectName("seq_on_btn")
        self.seq_on_btn.setStyleSheet(_SEQ_BTN_STYLE)
        self.seq_on_btn.clicked.connect(self._seq_power_on)
        bottom_layout.addWidget(self.seq_on_btn)

        self.seq_off_btn = QtWidgets.QPushButton("顺序下电")
        self.seq_off_btn.setObjectName("seq_off_btn")
        self.seq_off_btn.setStyleSheet(_SEQ_BTN_STYLE)
        self.seq_off_btn.clicked.connect(self._seq_power_off)
        bottom_layout.addWidget(self.seq_off_btn)

        # ── 组装主布局（默认控件样式，仅上下电按钮着色）────────────
        main_layout = QtWidgets.QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(top_frame)
        main_layout.addWidget(sep1)
        main_layout.addWidget(device_scroll, 1)
        main_layout.addWidget(sep2)
        main_layout.addWidget(bottom_frame)

        self.frame_left.setLayout(main_layout)

        cfg = Tool.read_config("Additional")
        if cfg["power_add"] == "True":
            self.addBTN()
        if cfg["power_del"] == "True":
            self.delBTN()

        self._load_devices_and_tcp()

    # ──────────────────────────────────────────────────────────────
    # 设备与 TCP 加载（供首次加载和热重载共用）
    # ──────────────────────────────────────────────────────────────

    def _load_devices_and_tcp(self):
        """读取 power_config，创建电源实例，启动 TCP 服务"""
        power_cfg = Tool.read_power_config()
        self.power_objs = []

        for dev in power_cfg["devices"]:
            if dev["type"] == "long":
                obj = LongPower(
                    dev["name"],
                    default_voltage=dev["default_voltage"],
                    default_current=dev["default_current"],
                    device_id=dev["id"],
                    remote_enabled=dev["remote"],
                )
                obj.safty = dev["current_limit"]
                obj.current_warn.connect(self.CurrentWarning)
                obj.start_signal.connect(self.start_info)
                obj.dataUpSignal.connect(self.update_data)
            elif dev["type"] == "square":
                obj = SquarePower(
                    dev["name"],
                    device_id=dev["id"],
                    ch1_voltage=dev["ch1"]["voltage"],
                    ch1_current=dev["ch1"]["current"],
                    ch2_voltage=dev["ch2"]["voltage"],
                    ch2_current=dev["ch2"]["current"],
                    remote_enabled=dev["remote"],
                )
                obj.ch1_safty = dev["current_limit_ch1"]
                obj.ch2_safty = dev["current_limit_ch2"]
                obj.current_warn.connect(self.CurrentWarning)
            else:
                print(f"跳过未知电源类型: {dev['type']}")
                continue

            self.AddSubWin(obj)
            self.power_objs.append(obj)
            if Tool.check_incombox(obj.portchoose, dev["port"]):
                obj.portchoose.setCurrentText(dev["port"])
            else:
                obj.portchoose.setCurrentText("COM1")
                print(f"未找到串口 {dev['port']}（{dev['id']}），使用默认 COM1")
            print(f"电源 [{dev['id']}] {dev['name']} 已加载，类型={dev['type']}")

        self.tcp_server = TCPServer.from_config()
        if self.tcp_server.auto_connect:
            self.tcp_server.start()
        else:
            print("TCP 远程服务未启动（Auto_config.ini [TCP] auto_connect = False）")

        serial_cfg = power_cfg["serial"]
        if serial_cfg["auto_connect"]:
            for obj in self.power_objs:
                obj.portopen.click()
        if serial_cfg["auto_output"]:
            for obj in self.power_objs:
                obj.start_btn.click()

    # ──────────────────────────────────────────────────────────────
    # 热重载：停止现有资源，重新加载配置
    # ──────────────────────────────────────────────────────────────

    def reloadUi(self):
        """停止所有电源与 TCP 服务，清理 UI 元素，重新加载当前配置"""
        # 1. 停止 TCP 服务：先关闭 socket 让 accept() 自然退出，再等线程结束
        if hasattr(self, 'tcp_server') and self.tcp_server.isRunning():
            self.tcp_server.close_tcp_server()
            if not self.tcp_server.wait(3000):
                self.tcp_server.terminate()
                self.tcp_server.wait(1000)

        # 2. 停止数据采集线程并关闭串口
        for obj in getattr(self, 'power_objs', []):
            try:
                if hasattr(obj, 'close_plot'):
                    obj.close_plot()
            except Exception:
                pass
            try:
                if getattr(obj, 'isConnected', False):
                    obj.power_port_close()
            except Exception:
                pass
            device_id = getattr(obj, 'device_id', None)
            if device_id:
                Tool.unregister_power_device(device_id)

        # 清理电源实例列表，避免重复加载时列表膨胀
        LongPower.instances.clear()
        SquarePower.instances.clear()
        self.power_objs = []

        # 3. 清除左侧设备按钮和右侧 stackedWidget 页面
        for btn in list(self.leftBtnDict.values()):
            self.device_btn_layout.removeWidget(btn)
            btn.deleteLater()
        for page in list(self.rightPageDict.values()):
            self.stackedWidget.removeWidget(page)
            page.deleteLater()

        self.leftBtnDict.clear()
        self.rightPageDict.clear()
        self.bindBtnWidget.clear()

        # 4. 重新加载设备与 TCP
        self._load_devices_and_tcp()

    # ──────────────────────────────────────────────────────────────
    # 顺序上下电
    # ──────────────────────────────────────────────────────────────

    @staticmethod
    def _format_seq_error_zh(error_message):
        """将顺序上下电错误信息转为中文提示"""
        if error_message.startswith("Device not found:"):
            dev_id = error_message.split(":", 1)[1].strip()
            return f"设备 {dev_id} 未注册"
        if error_message.startswith("Remote disabled:"):
            dev_id = error_message.split(":", 1)[1].strip()
            return f"设备 {dev_id} 未启用远程控制"
        if error_message.startswith("No power-on interface:"):
            dev_id = error_message.split(":", 1)[1].strip()
            return f"设备 {dev_id} 不支持上电接口"
        if error_message.startswith("No power-off interface:"):
            dev_id = error_message.split(":", 1)[1].strip()
            return f"设备 {dev_id} 不支持下电接口"
        if ": " in error_message:
            dev_id, detail = error_message.split(": ", 1)
            detail_map = {
                "Port not connected": "串口未连接",
                "Operation timed out": "操作超时",
            }
            return f"设备 {dev_id} 操作失败：{detail_map.get(detail, detail)}"
        return error_message

    def _on_seq_finished(self, is_power_on, success, error_message):
        """顺序上下电完成后的 UI 回调（主线程）"""
        btn = self.seq_on_btn if is_power_on else self.seq_off_btn
        btn.setEnabled(True)
        if not success:
            title = "顺序上电失败" if is_power_on else "顺序下电失败"
            QtWidgets.QMessageBox.warning(
                self, title, self._format_seq_error_zh(error_message)
            )

    def _run_seq_power(self, is_power_on):
        """在后台线程执行顺序上下电，遇错立即停止"""
        if is_power_on:
            sequence, _ = Tool.read_power_sequences()
        else:
            _, sequence = Tool.read_power_sequences()
        if not sequence:
            hint = (
                "尚未配置顺序上电列表，请在「电源设置」中设置 power_on_sequence。"
                if is_power_on else
                "尚未配置顺序下电列表，请在「电源设置」中设置 power_off_sequence。"
            )
            QtWidgets.QMessageBox.information(self, "提示", hint)
            return
        btn = self.seq_on_btn if is_power_on else self.seq_off_btn
        btn.setEnabled(False)

        def _do():
            ok, err = Tool.exec_power_sequence(
                sequence, power_on=is_power_on, check_remote=False
            )
            label = "顺序上电" if is_power_on else "顺序下电"
            if not ok:
                print(f"[{label}] 已停止: {err}")
            self._seq_ui_signal.emit(is_power_on, ok, err or "")

        threading.Thread(target=_do, daemon=True).start()

    def _seq_power_on(self):
        """一键顺序上电：按 power_on_sequence 顺序依次调用各电源的上电接口"""
        self._run_seq_power(True)

    def _seq_power_off(self):
        """一键顺序下电：按 power_off_sequence 顺序依次调用各电源的下电接口"""
        self._run_seq_power(False)

    # ──────────────────────────────────────────────────────────────
    # 设置与关于
    # ──────────────────────────────────────────────────────────────

    def show_power_settings(self):
        """打开电源设置弹窗，保存后直接热重载，无需手动重启"""
        dlg = PowerSettingsDialog(self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            self.reloadUi()

    def showAbout(self):
        df = pd.read_csv("更新内容.csv", header=None, names=["版本号", "更新内容"])
        html_table = df.to_html(index=False, border=1)
        aboutWin = QtWidgets.QDialog(self)
        aboutWin.setWindowTitle("关于")
        aboutWin.resize(400, 300)
        aboutWin.setStyleSheet("background-color: #FFFFFF;color: #000000;font: 12pt \"微软雅黑\";")
        aboutText = QtWidgets.QTextEdit(aboutWin)
        aboutText.setReadOnly(True)
        aboutText.setHtml(html_table)
        layout = QtWidgets.QVBoxLayout(aboutWin)
        layout.addWidget(aboutText)
        layout.setContentsMargins(10, 10, 10, 10)
        aboutWin.show()

    # ──────────────────────────────────────────────────────────────
    # 电源数据上传（FTP，可选）
    # ──────────────────────────────────────────────────────────────

    def update_data(self, filename):
        json_data = json.load(open((os.path.expanduser("~") + "\\AppData\\Local\\YabCom\\common\\config\\terminal_recent_projects.json"), 'r', encoding='utf-8'))
        print(json_data)
        project = json_data[0]["Name"]
        number = json_data[0]["Numbers"]
        if not self.ftp.check_ftp_directory_exists(f"/组网星/01 测试数据/02 每日历史数据/正样{number}/{datetime.datetime.now().strftime('%Y%m%d')}/电源数据"):
            self.ftp.make_dir(f"/组网星/01 测试数据/02 每日历史数据/正样{number}/{datetime.datetime.now().strftime('%Y%m%d')}/电源数据")
        self.ftp.moveto_dir(f"/组网星/01 测试数据/02 每日历史数据/正样{number}/{datetime.datetime.now().strftime('%Y%m%d')}/电源数据")
        self.ftp.upload_file(filename)

    # ──────────────────────────────────────────────────────────────
    # 电流过高警告与输出确认
    # ──────────────────────────────────────────────────────────────

    def CurrentWarning(self, str1, str2, str3):
        QtWidgets.QMessageBox.warning(self, f"{str1}警告", f"电流过高，请检查电源电流是否过高，当前{str2}电流为{str3}A")

    def start_info_square(self, name, v1, i1, v2, i2):
        sender = self.sender()
        reply = QtWidgets.QMessageBox.question(
            self,
            f'{name}',
            f"当前设置是否正确？\nCH1：{v1}V / {i1}A\nCH2：{v2}V / {i2}A",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if sender:
            sender.pressNo = reply != QtWidgets.QMessageBox.Yes

    def start_info(self, name, v, i):
        sender = self.sender()
        reply = QtWidgets.QMessageBox.question(
            self,
            f'{name}',
            f"当前设置电压{v}V,电流{i}A是否正确？",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if sender:
            sender.pressNo = reply != QtWidgets.QMessageBox.Yes

    # ──────────────────────────────────────────────────────────────
    # 调试用：动态增删电源（需 Additional 配置开启）
    # ──────────────────────────────────────────────────────────────

    def addBTN(self):
        AddBtnCustom = QtWidgets.QPushButton(self.device_btn_widget)
        AddBtnCustom.setStyleSheet("font: 12pt \"微软雅黑\";")
        AddBtnCustom.setObjectName("addBtn")
        self.device_btn_layout.addWidget(AddBtnCustom)
        AddBtnCustom.setText("addBtn")
        AddBtnCustom.clicked.connect(
            lambda: self.AddSubWin(SquarePower(f"方形电源{SquarePower.get_instances().__len__() + 1}"))
        )

    def delBTN(self):
        DelBtnCustom = QtWidgets.QPushButton(self.device_btn_widget)
        DelBtnCustom.setStyleSheet("font: 12pt \"微软雅黑\";")
        DelBtnCustom.setObjectName("delBtn")
        self.device_btn_layout.addWidget(DelBtnCustom)
        DelBtnCustom.setText("delBtn")
        DelBtnCustom.clicked.connect(
            lambda: self.DelSubWin(SquarePower.get_instances()[-1])
        )

    # ──────────────────────────────────────────────────────────────
    # 子页面管理：添加 / 删除 / 切换
    # ──────────────────────────────────────────────────────────────

    def AddSubWin(self, widgetObj):
        """在左侧设备切换区添加按钮，右侧 stackedWidget 添加对应页面"""
        BtnCustom = QtWidgets.QPushButton(self.device_btn_widget)
        BtnCustom.setCheckable(True)
        BtnCustom.setObjectName("Btn" + widgetObj.name)
        BtnCustom.setStyleSheet("font: 12pt \"微软雅黑\";")
        BtnCustom.setText(widgetObj.name)
        self.device_btn_layout.addWidget(BtnCustom)

        page_custom = QtWidgets.QWidget()
        page_custom.setObjectName("Page" + widgetObj.name)
        grid = QtWidgets.QGridLayout(page_custom)
        grid.setObjectName("gridLayout_custom")
        grid.setContentsMargins(1, 1, 1, 1)
        grid.addWidget(widgetObj, 1, 1, 1, 1)

        self.stackedWidget.addWidget(page_custom)

        self.bindBtnWidget[BtnCustom.objectName()] = page_custom.objectName()
        self.leftBtnDict[BtnCustom.objectName()] = BtnCustom
        self.rightPageDict[BtnCustom.objectName()] = page_custom

        BtnCustom.clicked.connect(lambda: self.leftBtnCallback(BtnCustom.objectName()))

        if isinstance(widgetObj, SquarePower):
            widgetObj.start_signal.connect(self.start_info_square)

    def DelSubWin(self, widgetObj):
        """从左侧与右侧移除指定电源的按钮和页面"""
        key = "Btn" + widgetObj.name

        BtnCustom = self.leftBtnDict[key]
        self.device_btn_layout.removeWidget(BtnCustom)
        BtnCustom.deleteLater()
        BtnCustom.setParent(None)

        page_custom = self.rightPageDict[key]
        self.stackedWidget.removeWidget(page_custom)
        page_custom.deleteLater()
        page_custom.setParent(None)

        del self.leftBtnDict[key]
        del self.rightPageDict[key]
        del self.bindBtnWidget[key]

        if widgetObj:
            del SquarePower.get_instances()[-1]

    def leftBtnCallback(self, BtnobjectName):
        """切换右侧显示页面，并更新左侧按钮选中状态"""
        for k, v in self.leftBtnDict.items():
            if k == BtnobjectName:
                self.stackedWidget.setCurrentWidget(self.rightPageDict[k])
                self.leftBtnDict[k].setChecked(True)
            else:
                self.leftBtnDict[k].setChecked(False)

    # ──────────────────────────────────────────────────────────────
    # 窗口关闭
    # ──────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        reply = QtWidgets.QMessageBox.question(
            self,
            '本程序',
            "是否要退出程序？",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if reply == QtWidgets.QMessageBox.Yes:
            event.accept()
            os._exit(0)
        else:
            event.ignore()
