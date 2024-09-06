import sys
import os

from PyQt5.QtGui import QTextCursor
from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QLineEdit, QPushButton,
                             QTreeWidget, QTextEdit, QGridLayout,
                             QTreeWidgetItem, QFileDialog)

from PyQt5.QtCore import Qt, QThread, pyqtSignal


sys.path.append('./')
from baidu_download import BaiduPanToken, BaiduPan

class DownloaderThread(QThread):
    log_signal = pyqtSignal(str)
    done_signal = pyqtSignal(str)

    def __init__(self, download_path, file):
        super().__init__()
        self.download_path = download_path
        self.file = file

    def run(self):
        try:
            self.file.all_download_by_aria2(self.download_path, self.log_signal)
        except Exception as e:
            self.log_signal.emit(f"下载失败: {e}")
        finally:
            self.done_signal.emit(f"下载完成: {self.file.server_filename}")

class DownloaderApp(QWidget):
    def __init__(self):
        super().__init__()
        self.token = None
        self.online_file_tree = None
        self.initUI()

    def initUI(self):
        # 创建布局
        grid = QGridLayout()
        self.setLayout(grid)

        # BUSS 输入框和按钮
        bduss_label = QLabel('BDUSS:')
        self.bduss_input = QLineEdit(self)
        confirm_btn = QPushButton('确定', self)
        confirm_btn.clicked.connect(self.on_confirm)

        grid.addWidget(bduss_label, 0, 0)
        grid.addWidget(self.bduss_input, 0, 1)
        grid.addWidget(confirm_btn, 0, 2)

        # 下载路径选择功能
        path_label = QLabel('下载路径:')
        self.path_input = QLineEdit(self)
        path_btn = QPushButton('选择路径', self)
        path_btn.clicked.connect(self.select_path)

        grid.addWidget(path_label, 1, 0)
        grid.addWidget(self.path_input, 1, 1)
        grid.addWidget(path_btn, 1, 2)

        # 在线目录树
        self.tree = QTreeWidget(self)
        self.tree.setHeaderLabels(['Name'])
        self.tree.itemExpanded.connect(self.on_item_expanded)

        grid.addWidget(self.tree, 2, 0, 1, 3)

        # 确认下载按钮
        download_btn = QPushButton('确认下载', self)
        download_btn.clicked.connect(self.on_download)

        grid.addWidget(download_btn, 3, 0, 1, 3)

        # 日志框
        self.log_output = QTextEdit(self)
        self.log_output.setReadOnly(True)

        grid.addWidget(self.log_output, 4, 0, 1, 3)

        # 设置窗口
        self.setGeometry(300, 300, 800, 600)
        self.setWindowTitle('百度网盘视频下载器')
        self.show()

    def populate_tree(self):
        try:
            self.online_file_tree = BaiduPan(self.token, log_function=self.log_message)
            directory_data = self.online_file_tree.root.list(log_function=self.log_message)
            self.add_items(self.tree.invisibleRootItem(), directory_data)
            self.log_message("目录树加载完成")
        except Exception as e:
            self.log_message(f"加载目录树失败: {e}")

    def add_items(self, parent, elements):
        for element in elements:
            item = QTreeWidgetItem(parent)
            item.setText(0, element.server_filename)
            if element.isdir == 1:
                # 添加一个虚拟子节点，表示这个目录还未被展开过
                QTreeWidgetItem(item).setText(0, '加载中...')
                item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)

            item.setData(0, Qt.UserRole, element)

    def on_item_expanded(self, item):
        # 检查这个目录是否已经被加载过
        if item.child(0).text(0) == '加载中...':
            item.takeChildren()  # 移除虚拟子节点
            file = item.data(0, Qt.UserRole)
            self.load_directory(item, file)

    def load_directory(self, item, file):
        try:
            if file.isdir == 1:
                file_list = file.list(log_function=self.log_message)
                self.add_items(item, file_list)
            else:
                self.add_items(item, file)
            self.log_message(f"目录 {file.server_filename} 加载完成")
        except Exception as e:
            self.log_message(f"加载目录 {file.server_filename} 失败: {e}")

    def on_confirm(self):
        bduss_value = self.bduss_input.text()
        if bduss_value:
            try:
                self.token = BaiduPanToken(bduss_value, log_function=self.log_message)
                if self.token.is_valid():
                    self.log_message("BDUSS有效")
                    self.log_message(f"BDUSS: {bduss_value}")
                    self.populate_tree()
                else:
                    self.log_message("BDUSS无效")
            except Exception as e:
                self.log_message(f"获取Token失败: {e}")
        else:
            self.log_message("BDUSS不能为空")

    def select_path(self):
        path = QFileDialog.getExistingDirectory(self, "选择下载路径")
        path = os.path.normpath(path)
        if path:
            self.path_input.setText(path)
            self.log_message(f"下载路径已选择: {path}")

    def on_download(self):
        bduss_value = self.bduss_input.text()
        download_path = self.path_input.text()

        if not bduss_value:
            self.log_message("错误: BDUSS 不能为空。")
            return

        if not download_path:
            self.log_message("错误: 下载路径未选择。")
            return

        selected_items = self.tree.selectedItems()
        if not selected_items:
            self.log_message("错误: 未选择任何文件或目录。")
            return

        file = selected_items[0].data(0, Qt.UserRole)

        self.log_message(f"确认下载: BDUSS={bduss_value}, 路径={download_path}, 文件={file.server_filename}")

        # 创建下载线程并启动
        self.download_thread = DownloaderThread(download_path, file)
        self.download_thread.log_signal.connect(self.log_message)
        self.download_thread.done_signal.connect(self.log_message)
        self.download_thread.start()


    def log_message(self, message):
        self.log_output.append(message)
        self.log_output.moveCursor(QTextCursor.End)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = DownloaderApp()
    sys.exit(app.exec_())