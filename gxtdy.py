# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

# pyqtSignal 可以跨线程，不管是 QThread 还是 threading，
# 前提是槽函数属于图形界面类的成员函数。

import multiprocessing
import sys
import traceback

from PyQt5 import QtCore, QtWidgets

from Projects.电源控制.UpperPC import UpperPcWin
from Projects.电源控制.operation_logger import OperationLogger
from Projects.电源控制.tool import Tool


class QSSLoader:
    @staticmethod
    def read_qss_file(qss_file_name):
        with open(qss_file_name, "r", encoding="UTF-8") as file:
            return file.read()


def main():
    try:
        # 不加这一行时，高 DPI 环境下界面会显示过小。
        QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)

        app = QtWidgets.QApplication(sys.argv)
        operation_logger = OperationLogger(app)
        app.setProperty("operation_logger", operation_logger)
        app.installEventFilter(operation_logger)

        Tool.check_config()
        main_window = UpperPcWin()
        main_window.show()
        main_window.initUi()

        operation_logger.install_action_logging(main_window)
        operation_logger.install_widget_logging(main_window)
        sys.exit(app.exec_())
    except Exception:
        traceback.print_exc()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
