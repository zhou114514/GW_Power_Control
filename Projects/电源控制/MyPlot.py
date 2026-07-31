import numpy as np
import pyqtgraph as pg
from PyQt5 import QtCore

pg.setConfigOption('background', 'w')  # 白底黑线
pg.setConfigOption('foreground', 'k')

RESIZE_MARGIN = 12     # 底边可拖拽调高的热区高度(px)
MIN_PLOT_HEIGHT = 120
MAX_PLOT_HEIGHT = 2000

class MyPlot(pg.GraphicsLayoutWidget):
    dataDict = {}
    posDict = {}
    NowPlotNo = 0
    dataLen = 0

    def __init__(self, dataDict, dataLen=30):  # dataLen是显示的数据最大个数
        super(MyPlot, self).__init__()
        self.dataDict = {}

        self._resizing = False
        self._resize_start_global_y = 0
        self._resize_start_height = 0
        self.setMinimumHeight(MIN_PLOT_HEIGHT)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)

        self.dataLen = dataLen
        for k, v in dataDict.items():
            self.posDict[k] = 0
            if type(v) == list:
                self.dataDict[k] = np.array(v)
            elif type(v) == np.ndarray:
                self.dataDict[k] = v

        self.plot1 = self.addPlot()
        key = list(self.dataDict.keys())[self.NowPlotNo]
        self.plot1.setTitle(key,**{"font-family": "微软雅黑", 'font-size': '12pt'})

        self.curve = self.plot1.plot(self.dataDict[key] , pen=pg.mkPen({'color': (0, 0, 255) , 'width': 4}))

        pass

    def _in_resize_zone(self, ev):
        return ev.y() >= self.height() - RESIZE_MARGIN

    def mousePressEvent(self, ev):
        if ev.button() == QtCore.Qt.LeftButton and self._in_resize_zone(ev):
            self._resizing = True
            self._resize_start_global_y = ev.globalY()
            self._resize_start_height = self.height()
            ev.accept()
        return

    def mouseMoveEvent(self, ev):
        if self._resizing:
            new_height = self._resize_start_height + ev.globalY() - self._resize_start_global_y
            new_height = max(MIN_PLOT_HEIGHT, min(MAX_PLOT_HEIGHT, new_height))
            self.setFixedHeight(new_height)
            ev.accept()
            return
        if self._in_resize_zone(ev):
            self.setCursor(QtCore.Qt.SizeVerCursor)
        else:
            self.unsetCursor()
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        if self._resizing:
            self._resizing = False
            ev.accept()
            return
        super().mouseReleaseEvent(ev)

    def mouseDoubleClickEvent(self, ev):
        if self._in_resize_zone(ev):
            return
        self.NowPlotNo = (self.NowPlotNo + 1) % len(self.dataDict)
        key = list(self.dataDict.keys())[self.NowPlotNo]
        self.plot1.setTitle(key,**{"font-family": "微软雅黑", 'font-size': '20pt'})

        data1 = self.dataDict[key]
        self.curve.setData(data1)
        self.posDict[key] = 0
        self.curve.setPos(self.posDict[key], 0)

    def updateData(self, dataAddDict):
        for k, v in dataAddDict.items():
            if len(self.dataDict[k]) < self.dataLen:
                self.dataDict[k] = np.append(self.dataDict[k], v)
            else:
                self.dataDict[k][:-1] = self.dataDict[k][1:]
                self.dataDict[k][-1] = v
                self.posDict[k] += 1

        key = list(self.dataDict.keys())[self.NowPlotNo]
        data1 = self.dataDict[key]
        self.curve.setData(data1)
        self.curve.setPos(self.posDict[key], 0)
        self.plot1.autoRange()