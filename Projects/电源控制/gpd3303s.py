"""
This is an interface module for DC Power Supply GPD-3303S manufactured by Good
Will Instrument Co., Ltd.
"""

import serial
import sys

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
        def readline(self, eol=b'\r'):
            """
            重写 io.RawIOBase.readline 方法，该方法无法处理'\r'分隔符。
            """
            leneol = len(eol)
            ret = b''
            while True:
                c = self.read(1)
                if c:
                    ret += c
                    if ret[-leneol:] == eol:
                        break
                else:
                    break

            return ret

class GPD3303S(object):
    def __init__(self):
        self.__baudRate = 9600 # 9600 bps
        self.__parityBit = 'N' # None
        self.__dataBit = 8
        self.__stopBit = 1
        self.__dataFlowControl = None
        self.eol = b'\r'
        self.serial = None

    def open(self, port, readTimeOut = 1, writeTimeOut = 1):
        self.serial = MySerial(port         = port,
                               baudrate     = self.__baudRate,
                               bytesize     = self.__dataBit,
                               parity       = self.__parityBit,
                               stopbits     = self.__stopBit,
                               timeout      = readTimeOut,
                               writeTimeout = writeTimeOut,
                               dsrdtr       = self.__dataFlowControl)
        
        err = self.getError()
        if err != b'No Error.':
            raise RuntimeError(err)

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

    def isValidChannel(self, channel):
        """
        检查通道号是否有效。只能是1或2。
        """
        if not (channel == 1 or channel == 2):
            raise RuntimeError('Invalid channel number: %d was given.' % channel)

        return True

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

    def setCurrent(self, channel, current):
        """
        ISET<X>:<NR2>
        """
        self.isValidChannel(channel)
        self.serial.write(b'ISET%d:%.3f\n' % (channel, current))

        err = self.getError()
        if err != b'No Error.':
            raise RuntimeError(err)
        
    def getCurrent(self, channel):
        """
        ISET<X>?
        """
        self.isValidChannel(channel)
        self.serial.write(b'ISET%d?\n' % channel)
        ret = self.serial.readline(eol=self.eol)

        err = self.getError()
        if err != b'No Error.':
            raise RuntimeError(err)

        return float(ret[:-len(self.eol)].replace(b'A', b''))

    def setVoltage(self, channel, voltage):
        """
        VSET<X>:<NR2>
        """
        self.isValidChannel(channel)
        self.serial.write(b'VSET%d:%.3f\n' % (channel, voltage))

        err = self.getError()
        if err != b'No Error.':
            raise RuntimeError(err)
        
    def getVoltage(self, channel):
        """
        VSET<X>?
        """
        self.isValidChannel(channel)
        self.serial.write(b'VSET%d?\n' % channel)
        ret = self.serial.readline(eol=self.eol)

        err = self.getError()
        if err != b'No Error.':
            raise RuntimeError(err)

        return float(ret[:-len(self.eol)].replace(b'V', b''))

    def getCurrentOutput(self, channel):
        """
        IOUT<X>?
        """
        self.isValidChannel(channel)
        self.serial.write(b'IOUT%d?\n' % channel)
        ret = self.serial.readline(eol=self.eol)

        err = self.getError()
        if err != b'No Error.':
            raise RuntimeError(err)

        return float(ret[:-len(self.eol)].replace(b'A', b''))

    def getVoltageOutput(self, channel):
        """
        VOUT<X>?
        """
        self.isValidChannel(channel)
        self.serial.write(b'VOUT%d?\n' % channel)
        ret = self.serial.readline(eol=self.eol)

        err = self.getError()
        if err != b'No Error.':
            raise RuntimeError(err)

        return float(ret[:-len(self.eol)].replace(b'V', b''))

    def enableOutput(self, enable = True):
        """
        OUT<Boolean>
        """
        self.serial.write(b'OUT%d\n' % int(enable))

        err = self.getError()
        if err != b'No Error.':
            raise RuntimeError(err)
        
    def getError(self):
        """
        ERR?
        """
        self.serial.write(b'ERR?\n')
        ret = self.serial.readline(eol=self.eol)
        if ret != b'':
            return ret[:-len(self.eol)]
        else:
            raise RuntimeError('Cannot read error message')
        

    def setDelimiter(self, eol = b'\r\n'):
        """
        Must call this method for new-firmware (2.0 or above?) instruments.
        Because the delimiter setting has been changed. 
        """
        self.eol = eol



