"""
This is an interface module for DC Power Supply GPD-3303S manufactured by Good
Will Instrument Co., Ltd.
"""

import serial
import sys
import time
import threading

class MySerial(serial.Serial):
    """
    Wrapper for Serial
    """
    try:
        import io
    except ImportError:
        # serial.Serial inherits serial.FileLike
        pass
    else:
        pass

class psw_xx_xx(object):
    def __init__(self):
        self.__baudRate = 9600 # 9600 bps
        self.__parityBit = 'N' # None
        self.__dataBit = 8
        self.__stopBit = 1
        self.__dataFlowControl = None
        self.eol = b'\r'
        self.serial = None
        self.voltage = 0
        self.current = 0
        self.lock = threading.Lock()

    def open(self, port, readTimeOut = 1, writeTimeOut = 1):
        self.serial = MySerial(port         = port,
                               baudrate     = self.__baudRate,
                               bytesize     = self.__dataBit,
                               parity       = self.__parityBit,
                               stopbits     = self.__stopBit,
                               timeout      = readTimeOut,
                               writeTimeout = writeTimeOut,
                               dsrdtr       = self.__dataFlowControl)
        
        # err = self.getError()
        # if err != b'+0,"No error"':
        #     raise RuntimeError(err)

        # 检查分隔符是否正确设置。
        # 默认情况下，\r 是分隔符，但较新的 GPD3303S 使用 \r\n 作为分隔符。
        self.setTimeout(0.1)
        ret = self.serial.read(1)
        self.setTimeout(readTimeOut)
        
        if ret == b'\n':
            self.setDelimiter(b'\r\n')
    
    def close(self):
        self.serial.close()

    def setTimeout(self, timeout):
        if hasattr(self.serial, 'setTimeout') and \
           callable(getattr(self.serial, 'setTimeout')):
            # pySerial <= v2.7
            self.serial.setTimeout(timeout)
        else:
            # pySerial v3
            self.serial.timeout = timeout

    def isValidFloat(self, value):
        """
        检查给定的浮点数是否有效。允许三位以下有效数字。
        """
        if value < 0:
            raise RuntimeError('Invalid float value: %f was given.' % value)
        
        str = "%f" % value
        position = str.find(".")
        maxDigits = 5
        if 0 <= position and position <= maxDigits : # found
            str = str[0:maxDigits + 1]
        else: # not found
            str = str[0:maxDigits]

        if float(str) != value:
            sys.stderr.write('Invalid float value: %f was given.' % value)
            return False
        
        return True

    def setCurrent(self, current):
        """
        APPLy self.voltage,current
        """
        if self.voltage == 0:
            self.voltage = self.getVoltage()
        with self.lock:
            self.serial.write(b'APPLy %.3f,%.3f\n' % (self.voltage, current))
            self.serial.flush()
            self.current = current

        # err = self.getError()
        # if err != b'+0,"No error"':
        #     raise RuntimeError(err)
        
    def getCurrent(self):
        """
        APPLy?
        """
        with self.lock:
            self.serial.write(b'APPLy?\n')
            self.serial.flush()
            # time.sleep(1)
            ret = self.serial.readline()

        # err = self.getError()
        # if err != b'+0,"No error"':
        #     raise RuntimeError(err)

        # print(ret)
            return float(ret.decode().split(',')[1])

    def setVoltage(self, voltage):
        """
        APPLy voltage,self.current
        """
        if self.current == 0:
            self.current = self.getCurrent()
        with self.lock:
            self.serial.write(b'APPLy %.3f,%.3f\n' % (voltage, self.current))
            self.serial.flush()
            self.voltage = voltage

        # err = self.getError()
        # if err != b'+0,"No error"':
        #     raise RuntimeError(err)
        
    def getVoltage(self):
        """
        APPLy?
        """
        with self.lock:
            self.serial.write(b'APPLy?\n')
            self.serial.flush()
            ret = self.serial.readline()

            # err = self.getError()
            # if err != b'+0,"No error"':
            #     raise RuntimeError(err)

            return float(ret.decode().split(',')[0])

    def getCurrentOutput(self):
        """
        MEASure[:SCALar]:CURRent[:DC]?
        """
        with self.lock:
            self.serial.write(b'MEASure:CURRent?\r\n')
            self.serial.flush()
            ret = self.serial.readline()

            # err = self.getError()
            # if err != b'+0,"No error"':
            #     raise RuntimeError(err)

            return float(ret.decode())


    def getVoltageOutput(self):
        """
        MEASure[:SCALar]:VOLTage[:DC]? 
        """
        with self.lock:
            self.serial.write(b'MEASure:VOLTage?\n')
            self.serial.flush()
            ret = self.serial.readline()

            # err = self.getError()
            # if err != b'+0,"No error"':
            #     raise RuntimeError(err)

            return float(ret.decode())
    

    def getOutput(self):
        """
        MEASure[:SCALar]:VOLTage[:DC]?\n
        MEASure[:SCALar]:CURRent[:DC]?\n
        """
        # ntime = time.time()
        with self.lock:
            ret = {"电压":0, "电流":0}
            self.serial.write(b'MEASure:VOLTage?\n')
            v = self.serial.readline()
            self.serial.write(b'MEASure:CURRent?\n')
            i = self.serial.readline()
            # print(time.time() - ntime)

            ret["电压"], ret["电流"] = float(v.decode()), float(i.decode())

            # err = self.getError()
            # if err != b'+0,"No error"':
            #     raise RuntimeError(err)

            return [ret["电压"], ret["电流"]]


    def enableOutput(self, enable = True):
        """
        OUTPut <bool>
        """
        with self.lock:
            self.serial.write(b'OUTPut %d\n' % int(enable))

        # err = self.getError()
        # if err != b'+0,"No error"':
        #     raise RuntimeError(err)
        
    def getError(self):
        """
        SYSTem:ERRor?
        """
        with self.lock:
            self.serial.write(b'SYSTem:ERRor?\r\n')
            ret = self.serial.readline()
            if ret != b'':
                return ret[:-len(self.eol)]
            else:
                return b'+0,"No error"'
            

    def setDelimiter(self, eol = b'\r\n'):
        """
        Must call this method for new-firmware (2.0 or above?) instruments.
        Because the delimiter setting has been changed. 
        """
        self.eol = eol


if __name__ == '__main__':
    psw = psw_xx_xx()
    psw.open('COM32')
    v, i = psw.getOutput()
    print(v, i)
    psw.close()



