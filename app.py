import sys
import json
import socketio
import requests
from datetime import datetime
from urllib.parse import urlparse
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QPoint, QSettings
from PySide6.QtGui import QIcon, QFont, QAction, QColor, QPalette
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                              QLabel, QLineEdit, QPushButton, QTextEdit, QListWidget, 
                              QListWidgetItem, QSystemTrayIcon, QMenu, QDialog, QFormLayout,
                              QMessageBox, QCheckBox, QScrollArea, QFrame, QSizePolicy)

# ------------------------------
# Socket.IO 客户端
# ------------------------------
sio = socketio.Client()

class WhiteboardClient:
    def __init__(self):
        self.headers = {}
        self.base_url = ""
        self.board_id = ""
        self.secret_key = ""
        self.connected = False
        
    def setup(self, server, board_id, secret_key):
        self.board_id = board_id
        self.secret_key = secret_key
        self.headers = {
            'X-Board-ID': board_id,
            'X-Secret-Key': secret_key
        }
        
        # 解析服务器URL
        if not server.startswith(('http://', 'https://')):
            server = 'http://' + server
        
        parsed_url = urlparse(server)
        self.base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
    def connect_socket(self):
        try:
            if not self.base_url or not self.board_id or not self.secret_key:
                return False
                
            parsed_url = urlparse(self.base_url)
            connect_url = f"ws://{parsed_url.hostname}:{parsed_url.port or 5000}/socket.io/?board_id={self.board_id}&secret_key={self.secret_key}"
            sio.connect(connect_url)
            self.connected = True
            return True
        except Exception as e:
            print(f"连接失败: {e}")
            return False
            
    def disconnect_socket(self):
        if self.connected:
            sio.disconnect()
            self.connected = False
            
    def get_assignments(self, date=None, subject=None):
        try:
            params = {}
            if date:
                params['date'] = date
            if subject:
                params['subject'] = subject
                
            response = requests.get(
                f"{self.base_url}/api/whiteboard/assignments",
                headers=self.headers,
                params=params
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"success": False, "error": f"HTTP错误: {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def get_all_data(self, date=None):
        try:
            params = {}
            if date:
                params['date'] = date
                
            response = requests.get(
                f"{self.base_url}/api/whiteboard/all",
                headers=self.headers,
                params=params
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"success": False, "error": f"HTTP错误: {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def acknowledge_task(self, task_id):
        try:
            response = requests.post(
                f"{self.base_url}/api/whiteboard/tasks/{task_id}/acknowledge",
                headers=self.headers
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"success": False, "error": f"HTTP错误: {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def complete_task(self, task_id):
        try:
            response = requests.post(
                f"{self.base_url}/api/whiteboard/tasks/{task_id}/complete",
                headers=self.headers
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"success": False, "error": f"HTTP错误: {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def send_heartbeat_api(self):
        try:
            response = requests.post(
                f"{self.base_url}/api/whiteboard/heartbeat",
                headers=self.headers
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"success": False, "error": f"HTTP错误: {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

# ------------------------------
# MD3风格悬浮窗
# ------------------------------
class FloatingWindow(QWidget):
    def __init__(self, content, title="通知", timeout=10000, parent=None):
        super().__init__(parent)
        self.setup_ui(content, title)
        self.setup_behavior(timeout)
        
    def setup_ui(self, content, title):
        # 设置窗口属性
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("""
            QWidget {
                background-color: #f5f5f5;
                border-radius: 10px;
                border: 1px solid #e0e0e0;
            }
            QLabel {
                background-color: transparent;
                padding: 5px;
            }
            QLabel#title {
                font-weight: bold;
                color: #6200ea;
                font-size: 14px;
            }
            QPushButton {
                background-color: transparent;
                border: none;
                color: #666;
                font-size: 16px;
            }
            QPushButton:hover {
                color: #000;
            }
        """)
        
        # 创建布局
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)
        
        # 标题栏
        title_bar = QWidget()
        title_bar.setFixedHeight(30)
        title_bar_layout = QHBoxLayout(title_bar)
        title_bar_layout.setContentsMargins(5, 0, 5, 0)
        
        title_label = QLabel(title)
        title_label.setObjectName("title")
        title_bar_layout.addWidget(title_label)
        
        close_btn = QPushButton("×")
        close_btn.setFixedSize(20, 20)
        close_btn.clicked.connect(self.close)
        title_bar_layout.addWidget(close_btn)
        
        layout.addWidget(title_bar)
        
        # 内容
        content_label = QLabel(content)
        content_label.setWordWrap(True)
        content_label.setMinimumWidth(300)
        content_label.setMaximumWidth(400)
        layout.addWidget(content_label)
        
        self.setLayout(layout)
        self.adjustSize()
        
    def setup_behavior(self, timeout):
        # 设置超时自动关闭
        if timeout > 0:
            QTimer.singleShot(timeout, self.close)
            
        # 添加阴影效果
        self.setGraphicsEffect(self.create_shadow_effect())
        
    def create_shadow_effect(self):
        from PySide6.QtWidgets import QGraphicsDropShadowEffect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 150))
        shadow.setOffset(0, 0)
        return shadow
        
    def mousePressEvent(self, event):
        # 实现拖动功能
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            
    def mouseMoveEvent(self, event):
        # 实现拖动功能
        if event.buttons() == Qt.LeftButton and hasattr(self, 'drag_position'):
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

# ------------------------------
# 设置对话框
# ------------------------------
class SettingsDialog(QDialog):
    def __init__(self, client, parent=None):
        super().__init__(parent)
        self.client = client
        self.setup_ui()
        self.load_settings()
        
    def setup_ui(self):
        self.setWindowTitle("白板客户端设置")
        self.setFixedSize(400, 300)
        
        layout = QFormLayout()
        
        self.server_edit = QLineEdit()
        self.board_id_edit = QLineEdit()
        self.secret_key_edit = QLineEdit()
        self.secret_key_edit.setEchoMode(QLineEdit.Password)
        
        layout.addRow("服务器地址:", self.server_edit)
        layout.addRow("白板ID:", self.board_id_edit)
        layout.addRow("白板密钥:", self.secret_key_edit)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        self.save_btn = QPushButton("保存")
        self.save_btn.clicked.connect(self.save_settings)
        self.test_btn = QPushButton("测试连接")
        self.test_btn.clicked.connect(self.test_connection)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(self.test_btn)
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addRow(button_layout)
        
        self.setLayout(layout)
        
    def load_settings(self):
        settings = QSettings("WhiteboardClient", "Config")
        self.server_edit.setText(settings.value("server", ""))
        self.board_id_edit.setText(settings.value("board_id", ""))
        self.secret_key_edit.setText(settings.value("secret_key", ""))
        
    def save_settings(self):
        server = self.server_edit.text().strip()
        board_id = self.board_id_edit.text().strip()
        secret_key = self.secret_key_edit.text().strip()
        
        if not server or not board_id or not secret_key:
            QMessageBox.warning(self, "输入错误", "请填写所有字段")
            return
            
        settings = QSettings("WhiteboardClient", "Config")
        settings.setValue("server", server)
        settings.setValue("board_id", board_id)
        settings.setValue("secret_key", secret_key)
        
        self.client.setup(server, board_id, secret_key)
        QMessageBox.information(self, "成功", "设置已保存")
        self.accept()
        
    def test_connection(self):
        server = self.server_edit.text().strip()
        board_id = self.board_id_edit.text().strip()
        secret_key = self.secret_key_edit.text().strip()
        
        if not server or not board_id or not secret_key:
            QMessageBox.warning(self, "输入错误", "请填写所有字段")
            return
            
        # 测试API连接
        try:
            test_client = WhiteboardClient()
            test_client.setup(server, board_id, secret_key)
            result = test_client.send_heartbeat_api()
            
            if result.get("success"):
                QMessageBox.information(self, "连接成功", "服务器连接测试成功")
            else:
                QMessageBox.warning(self, "连接失败", f"服务器连接测试失败: {result.get('error', '未知错误')}")
        except Exception as e:
            QMessageBox.critical(self, "连接错误", f"连接过程中发生错误: {str(e)}")

# ------------------------------
# 主应用和系统托盘
# ------------------------------
class WhiteboardApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.client = WhiteboardClient()
        self.tray_icon = None
        self.floating_windows = []
        
        # 设置应用样式
        self.apply_md3_style()
        
        # 加载设置
        self.load_settings()
        
        # 设置Socket.IO事件处理
        self.setup_socket_events()
        
    def apply_md3_style(self):
        # 设置MD3风格样式表
        self.app.setStyle("Fusion")
        
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(245, 245, 245))
        palette.setColor(QPalette.WindowText, QColor(33, 33, 33))
        palette.setColor(QPalette.Base, QColor(255, 255, 255))
        palette.setColor(QPalette.AlternateBase, QColor(245, 245, 245))
        palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 255))
        palette.setColor(QPalette.ToolTipText, QColor(33, 33, 33))
        palette.setColor(QPalette.Text, QColor(33, 33, 33))
        palette.setColor(QPalette.Button, QColor(240, 240, 240))
        palette.setColor(QPalette.ButtonText, QColor(33, 33, 33))
        palette.setColor(QPalette.BrightText, Qt.red)
        palette.setColor(QPalette.Highlight, QColor(98, 0, 234))
        palette.setColor(QPalette.HighlightedText, Qt.white)
        
        self.app.setPalette(palette)
        
        self.app.setStyleSheet("""
            QMainWindow, QDialog {
                background-color: #f5f5f5;
            }
            QPushButton {
                background-color: #e0e0e0;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #d5d5d5;
            }
            QPushButton:pressed {
                background-color: #c2c2c2;
            }
            QPushButton:focus {
                outline: none;
            }
            QLineEdit, QTextEdit {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 8px;
                background-color: white;
            }
            QLineEdit:focus, QTextEdit:focus {
                border: 2px solid #6200ea;
            }
            QLabel {
                color: #212121;
            }
            QListWidget {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                background-color: white;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #f0f0f0;
            }
            QListWidget::item:selected {
                background-color: #e8f0fe;
            }
            QMenu {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
            }
            QMenu::item {
                padding: 8px 16px;
            }
            QMenu::item:selected {
                background-color: #e8f0fe;
            }
        """)
        
    def load_settings(self):
        settings = QSettings("WhiteboardClient", "Config")
        server = settings.value("server", "")
        board_id = settings.value("board_id", "")
        secret_key = settings.value("secret_key", "")
        
        if server and board_id and secret_key:
            self.client.setup(server, board_id, secret_key)
            
    def setup_socket_events(self):
        @sio.event
        def connect():
            print(f"【{datetime.now().strftime('%H:%M:%S')}】Socket.IO 连接成功！")
            
        @sio.event
        def connect_error(data):
            print(f"【{datetime.now().strftime('%H:%M:%S')}】连接失败：{data}")
            
        @sio.event
        def disconnect():
            print(f"【{datetime.now().strftime('%H:%M:%S')}】连接已关闭")
            
        @sio.on('connected')
        def on_connected(data):
            print(f"【认证结果】状态：{data['status']} | 消息：{data['message']}")
            
        @sio.on('new_task')
        def on_new_task(task):
            content = f"标题：{task['title']}\n优先级：{task['priority']}\n描述：{task.get('description', '无')}"
            self.show_floating_window(content, "新任务")
            
        @sio.on('delete_task')
        def on_delete_task(data):
            task_id = data.get('task_id')
            self.show_floating_window(f"任务 {task_id} 已被删除", "任务删除")
            
        @sio.on('delete_assignment')
        def on_delete_assignment(data):
            self.show_floating_window("作业已被删除", "作业删除")
            
        @sio.on('delete_announcement')
        def on_delete_announcement(data):
            self.show_floating_window("公告已被删除", "公告删除")
            
        @sio.on('new_announcement')
        def on_new_announcement(ann):
            content = f"标题：{ann['title']}\n长期有效：{'是' if ann.get('is_long_term', False) else '否'}\n内容：{ann['content']}"
            self.show_floating_window(content, "新公告")
            
        @sio.on('new_assignment')
        def on_new_assignment(ass):
            content = f"标题：{ass['title']}（{ass['subject']}）\n截止时间：{ass['due_date']}\n描述：{ass['description']}"
            self.show_floating_window(content, "新作业")
            
        @sio.on('update_assignment')
        def on_update_assignment(ass):
            content = f"标题：{ass['title']}（{ass['subject']}）\n截止时间：{ass['due_date']}\n描述：{ass['description']}"
            self.show_floating_window(content, "作业更新")
            
    def show_floating_window(self, content, title="通知"):
        # 获取屏幕尺寸
        screen_geometry = self.app.primaryScreen().geometry()
        
        # 计算新窗口位置（右上角）
        x = screen_geometry.width() - 350
        y = 50 + len(self.floating_windows) * 50  # 稍微错开位置
        
        # 创建悬浮窗
        window = FloatingWindow(content, title)
        window.move(x, y)
        window.show()
        
        # 存储引用以防止垃圾回收
        self.floating_windows.append(window)
        
        # 窗口关闭时从列表中移除
        window.destroyed.connect(lambda: self.floating_windows.remove(window) if window in self.floating_windows else None)
        
    def setup_tray_icon(self):
        # 创建系统托盘图标
        self.tray_icon = QSystemTrayIcon()
        
        # 创建托盘图标菜单
        tray_menu = QMenu()
        
        settings_action = QAction("设置", self.app)
        settings_action.triggered.connect(self.show_settings)
        tray_menu.addAction(settings_action)
        
        connect_action = QAction("连接", self.app)
        connect_action.triggered.connect(self.connect_client)
        tray_menu.addAction(connect_action)
        
        disconnect_action = QAction("断开连接", self.app)
        disconnect_action.triggered.connect(self.disconnect_client)
        tray_menu.addAction(disconnect_action)
        
        tray_menu.addSeparator()
        
        exit_action = QAction("退出", self.app)
        exit_action.triggered.connect(self.app.quit)
        tray_menu.addAction(exit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        
        # 设置托盘图标（这里使用一个简单的替代图标）
        self.tray_icon.setIcon(self.app.style().standardIcon(self.app.style().SP_ComputerIcon))
        self.tray_icon.setToolTip("白板客户端")
        self.tray_icon.show()
        
        # 托盘图标点击事件
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        
    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_settings()
            
    def show_settings(self):
        dialog = SettingsDialog(self.client)
        if dialog.exec():
            # 设置已保存，尝试重新连接
            self.disconnect_client()
            self.connect_client()
            
    def connect_client(self):
        if self.client.connect_socket():
            self.tray_icon.showMessage("连接成功", "已成功连接到白板服务器", QSystemTrayIcon.Information, 2000)
        else:
            self.tray_icon.showMessage("连接失败", "无法连接到白板服务器，请检查设置", QSystemTrayIcon.Critical, 3000)
            
    def disconnect_client(self):
        self.client.disconnect_socket()
        self.tray_icon.showMessage("已断开", "已断开与白板服务器的连接", QSystemTrayIcon.Information, 2000)
        
    def run(self):
        # 设置系统托盘
        self.setup_tray_icon()
        
        # 尝试自动连接
        if self.client.board_id and self.client.secret_key:
            self.connect_client()
            
        # 运行应用
        sys.exit(self.app.exec())

# ------------------------------
# 主函数
# ------------------------------
if __name__ == "__main__":
    app = WhiteboardApp()
    app.run()