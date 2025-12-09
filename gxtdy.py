# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

#pyqtSignal 可以跨现场，不管是QThread还是threading，前提是槽函数属于图形界面类子函数
import multiprocessing
import sys
from PyQt5 import QtWidgets, QtCore
from Projects.电源控制.UpperPC import UpperPcWin

from Projects.电源控制.tool import Tool


# for files in os.listdir(r"D:\Coding\python\UpperPcnew\Confiles\九江U转台"):  # 不仅仅是文件，当前目录下的文件夹也会被认为遍历到
#     if os.path.isdir(r"D:\Coding\python\UpperPcnew\Confiles\九江U转台"+"\\"+files ):


class QSSLoader:
    def __init__(self):
        pass
    @staticmethod
    def read_qss_file(qss_file_name):
        with open(qss_file_name, 'r',  encoding='UTF-8') as file:
            return file.read()
def main():

    try:
        import os
        #不加这一行就会界面很小198
        QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)

        app = QtWidgets.QApplication(sys.argv)

        Tool.check_config()
        mainWind = UpperPcWin()

        mainWind.show()
        mainWind.initUi() #show以后才能加载子页面

        sys.exit(app.exec_())
    except Exception as e:
        print(e)

if __name__ == '__main__':

    multiprocessing.freeze_support()
    main()
