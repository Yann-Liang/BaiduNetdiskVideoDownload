import json
import os
import sys

import time
import re

import requests
import subprocess

cur_sep = os.path.sep
#生成资源文件目录访问路径
def resource_path(relative_path):
    #是否Bundle Resource
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

#访问res文件夹下aria2c.exe的程序
aria2c_path = resource_path(os.path.join("res", "aria2" + cur_sep + "aria2c.exe"))

def to_timestamp(t: str = None):
    return time.strptime(t, '%Y-%m-%d %H:%M:%S') if t else int(time.time())

class BaiduPanToken:
    def __init__(self, bduss=None, storage_path='./token.json', log_function=None):
        self.bduss = bduss
        self.refresh_token = None
        self.access_token = None
        self.expires = None
        self.storage_path = storage_path
        # 保存日志记录函数的引用
        self.log_function = log_function
        self.load_token()

    def log(self, message):
        if self.log_function:
            self.log_function(message)

    def get_token(self):
        if not self.is_valid():
            self.refresh()
            self.save_token()
        return self.access_token

    def is_valid(self):
        now = to_timestamp()
        return (not not self.access_token) and self.expires and now < self.expires

    def load_token(self):
        if not self.storage_path:
            return
        if os.path.exists(self.storage_path):
            with open(self.storage_path, 'r') as file:
                token_json = json.load(file)
                if not self.bduss:
                    self.bduss = token_json.get('bduss')
                if not self.refresh_token:
                    self.refresh_token = token_json.get('refresh_token')
                if not self.access_token:
                    self.access_token = token_json.get('access_token')
                if not self.expires:
                    self.expires = token_json.get('expires')
        else:
            self.get_token()
        self.log("百度Token获取成功!")

    def save_token(self):
        if not self.storage_path:
            return
        token_json = {}
        if os.path.exists(self.storage_path):
            with open(self.storage_path, 'r') as f1:
                token_json = json.load(f1)
        token_json.update({
            'bduss': self.bduss,
            'refresh_token': self.refresh_token,
            'access_token': self.access_token,
            'expires': self.expires
        })
        with open(self.storage_path, 'w') as f2:
            json.dump(token_json, f2, indent=2)

    def refresh(self):
        if not self.bduss:
            raise Exception('BDUSS不能为空')
        if not self.refresh_token:
            client_id = 'iYCeC9g08h5vuP9UqvPHKKSVrKFXGa1v'
            client_secret = 'jXiFMOPVPCWlO2M5CwWQzffpNPaGTRBG'
            url = 'https://openapi.baidu.com/oauth/2.0/device/code' \
                  '?response_type=device_code' \
                  '&client_id=iYCeC9g08h5vuP9UqvPHKKSVrKFXGa1v' \
                  '&scope=basic,netdisk'
            data = requests.get(url, headers={
                'User-Agent': 'pan.baidu.com'
            }).json()
            device_code = data['device_code']
            requests.get(
                f'https://openapi.baidu.com/device?code={data["user_code"]}&display=page&redirect_uri=&force_login=',
                cookies={
                    'BDUSS': self.bduss
                })
            now = to_timestamp()
            resp = requests.get(
                f'https://openapi.baidu.com/oauth/2.0/token?grant_type=device_token&code={device_code}&client_id={client_id}&client_secret={client_secret}')
            resp.raise_for_status()
            token_info = resp.json()
            if 'error_description' in token_info:
                raise Exception(token_info['error_description'])
            self.refresh_token = token_info.get('refresh_token')
            self.access_token = token_info.get('access_token')
            self.expires = now + token_info.get('expires_in')
        else:
            client_id = 'iYCeC9g08h5vuP9UqvPHKKSVrKFXGa1v'
            client_secret = 'jXiFMOPVPCWlO2M5CwWQzffpNPaGTRBG'
            now = to_timestamp()
            token_info = requests.get('https://openapi.baidu.com/oauth/2.0/token', params={
                'grant_type': 'refresh_token',
                'refresh_token': self.refresh_token,
                'client_id': client_id,
                'client_secret': client_secret,
            }).json()
            self.refresh_token = token_info.get('refresh_token')
            self.access_token = token_info.get('access_token')
            self.expires = now + token_info.get('expires_in')


class File:
    def __init__(self, auth, file_info, log_function=None):
        self._auth = auth
        self._ua = 'netdisk'
        # 保存日志记录函数的引用
        self.log_function = log_function
        for k, v in file_info.items():
            setattr(self, k, v)

    def log(self, message):
        if self.log_function:
            self.log_function(message)

    def __str__(self):
        return self.server_filename

    def list(self, dir=None, log_function=None):
        # 保存日志记录函数的引用
        self.log_function = log_function
        if dir is None:
            dir = self.path
        if self.isdir != 1:
            self.log(f"文件不能展开,文件名: {self.server_filename}")
            raise Exception('文件不能展开')
        resp = requests.get('https://pan.baidu.com/rest/2.0/xpan/file', params={
            'method': 'list',
            'dir': dir,
            'access_token': self._auth.get_token(),
        })
        resp.raise_for_status()
        return [File(self._auth, i, self.log_function) for i in resp.json()['list']]

    def get_unlimited_speed_download_url(self):
        # 隐藏api, 不限速, 不稳定
        if self.isdir == 1:
            raise Exception('不能下载文件夹')
        resp = requests.get('https://pan.baidu.com/api/filemetas', params={
            'target': f'["{self.path}"]',
            'dlink': 1,
            'web': 5,
            'origin': 'dlna',
            'access_token': self._auth.get_token(),
        }, headers={
            'User-Agent': self._ua,
        })
        resp.raise_for_status()
        return f"{resp.json()['info'][0]['dlink']}&access_token={self._auth.get_token()}"

    def cmd_aria2(self, download_path, log_signal):
        try:
            download_url = self.get_unlimited_speed_download_url()
        except Exception as e:
            log_signal.emit(f"获取不限速下载链接失败: {e}")
            return
        command = f'{aria2c_path} -x16 "{download_url}" -d "{download_path}" -o "{self.server_filename}" --header="User-Agent: {self._ua}"'
        reg = r'Redirecting to http'
        # 启动子进程
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # 将 stderr 合并到 stdout
            text=True,  # 确保输出为文本而不是字节
            bufsize=1,  # 行缓冲
            shell=True  # 如果命令是字符串形式，使用 shell=True
        )

        # 实时输出
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                if len(re.findall(reg, output)) == 0:
                    # 打印输出日志
                    log_signal.emit(output)

        # 等待进程结束并获取返回码
        process.poll()


    def all_download_by_aria2(self, download_path, log_signal):
        if self.isdir == 1:
            os.chdir(download_path)
            if not os.path.exists(self.server_filename):
                os.mkdir(self.server_filename)
                log_signal.emit(f"创建文件夹: {download_path}")
            download_path += cur_sep + self.server_filename;
            for i in self.list(log_function=self.log_function):
                i.all_download_by_aria2(download_path, log_signal)
        else:
            log_signal.emit(f"开始下载: {self.server_filename}")
            try:
                if not os.path.exists(self.server_filename):
                    self.cmd_aria2(download_path, log_signal)
            except Exception as e:
                log_signal.emit(f"下载失败: {e}")

class BaiduPan:
    def __init__(self, auth: BaiduPanToken, log_function=None):
        self.auth = auth
        self.root = File(auth, {'isdir': 1, 'path': '/', 'server_filename': 'root'}, log_function)
