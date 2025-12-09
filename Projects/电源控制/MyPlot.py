import numpy as np
import pyqtgraph as pg

pg.setConfigOption('background', 'w')  # 白底黑线
pg.setConfigOption('foreground', 'k')

class MyPlot(pg.GraphicsLayoutWidget):
    dataDict = {}
    posDict = {}
    NowPlotNo = 0
    dataLen = 0

    def __init__(self, dataDict, dataLen=30):  # dataLen是显示的数据最大个数
        super(MyPlot, self).__init__()
        self.dataDict = {}

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

    def mousePressEvent(self, ev):
        return

    def mouseDoubleClickEvent(self, ev):
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