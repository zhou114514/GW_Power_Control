from ftplib import FTP
import os
import sys
import logging

if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(os.path.abspath(sys.executable))
else:
    application_path = os.path.dirname(os.path.abspath(sys.argv[0]))

class FTPClient:
    def __init__(self, host, user, password, path='/'):
        self.ftp = FTP(host)
        try:
            self.ftp.login(user, password)
            self.ftp.encoding = 'gbk'
            logging.info('登录成功')
        except:
            logging.error('登录失败')
        self.moveto_dir(path)

    def moveto_dir(self, src_dir):
        self.ftp.cwd(src_dir)

    def download_file(self, file_name, file):
        if not os.path.exists(os.path.join(application_path+"\\temp")):
            os.mkdir(os.path.join(application_path+"\\temp"))
        with open(os.path.join(application_path+"\\temp", f"{file_name}.zip"), 'wb') as f:
            self.ftp.retrbinary('RETR '+ file, f.write)

    def get_file_havename(self, file_name):
        files = self.ftp.nlst()  # 获取文件列表
        for file in files:
            if file_name in file:
                self.download_file(file_name, file)

    def get_filelist(self):
        files = self.ftp.nlst()  # 获取文件列表
        return files

    def make_dir(self, dir_name):
        self.ftp.mkd(dir_name)

    def check_ftp_directory_exists(self, directory):
        try:
            self.moveto_dir(directory)
            return True
        except:
            return False

    def upload_file(self, file_path):
        response = self.ftp.storbinary('STOR '+ os.path.basename(file_path), open(file_path, 'rb'))
        if response.startswith('226'):    
            # print(f"{file_path}上传成功")
            logging.info(response)
            return True
        else:
            # print(f"{file_path}上传失败")
            logging.info(response)
            return False
        
    def upload_dir(self, dir_path):
        # 上传目录
        try:
            if os.path.basename(dir_path) not in self.ftp.nlst():
                self.make_dir(os.path.basename(dir_path))
            self.moveto_dir(os.path.basename(dir_path))
            for root, dirs, files in os.walk(dir_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    self.upload_file(file_path)
            self.moveto_dir("..")
            return True
        except:
            self.moveto_dir("..")
            logging.info("上传失败")
            return False

    def close(self):
        self.ftp.quit()


if __name__ == '__main__':
    ftp_client = FTPClient('192.168.10.100', 'yab', 'qwer1234!!')
    ftp_client.moveto_dir("/地检源码数据")
    if "ZY3" not in ftp_client.get_filelist():
        ftp_client.make_dir("ZY3")
    ftp_client.moveto_dir("/ZY3")
    # ftp_client.upload_dir("C:\\Users\\Administrator\\Desktop\\新建文件夹 (2)")
    

    