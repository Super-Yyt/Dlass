import sys
import json
import socketio
import requests
from datetime import datetime
from urllib.parse import urlparse
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QPoint, QSettings, QSize, Signal
from PySide6.QtGui import QIcon, QFont, QAction, QColor, QPalette, QPixmap, QPainter
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                              QLabel, QLineEdit, QPushButton, QTextEdit, QListWidget, 
                              QListWidgetItem, QSystemTrayIcon, QMenu, QDialog, QFormLayout,
                              QMessageBox, QCheckBox, QScrollArea, QFrame, QSizePolicy,
                              QComboBox, QGroupBox, QSpinBox, QToolButton, QButtonGroup,
                              QRadioButton, QTabWidget, QGridLayout)

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
    closed = Signal(str, str)  # 参数: item_type, item_id
    
    def __init__(self, content, title="通知", timeout=10000, item_type="", item_id="", app=None):
        super().__init__(None)  # 不设置父对象
        self.item_type = item_type
        self.item_id = item_id
        self.app = app  # 保存对应用的引用
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
                padding: 5px;
            }
            QPushButton:hover {
                color: #000;
            }
            QPushButton#actionBtn {
                background-color: #e0e0e0;
                border-radius: 4px;
                padding: 5px 10px;
                margin: 2px;
                font-size: 12px;
            }
            QPushButton#actionBtn:hover {
                background-color: #d0d0d0;
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
        
        # 如果是任务，添加操作按钮
        if self.item_type == "task" and self.item_id:
            button_layout = QHBoxLayout()
            
            ack_btn = QPushButton("确认任务")
            ack_btn.setObjectName("actionBtn")
            ack_btn.clicked.connect(self.acknowledge_task)
            
            complete_btn = QPushButton("完成任务")
            complete_btn.setObjectName("actionBtn")
            complete_btn.clicked.connect(self.complete_task)
            
            button_layout.addWidget(ack_btn)
            button_layout.addWidget(complete_btn)
            layout.addLayout(button_layout)
        
        self.setLayout(layout)
        self.adjustSize()
        
    def setup_behavior(self, timeout):
        # 设置超时自动关闭（如果timeout>0）
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
            
    def acknowledge_task(self):
        # 发送确认任务请求
        if self.app and hasattr(self.app, 'client'):
            result = self.app.client.acknowledge_task(self.item_id)
            if result.get('success'):
                # 修改：确认任务时不关闭窗口，只显示消息
                QMessageBox.information(self, "成功", f"任务 {self.item_id} 已确认")
                # 不关闭窗口，让用户可以选择完成任务
            else:
                QMessageBox.warning(self, "错误", f"确认任务失败: {result.get('error', '未知错误')}")
                
    def complete_task(self):
        # 发送完成任务请求
        if self.app and hasattr(self.app, 'client'):
            result = self.app.client.complete_task(self.item_id)
            if result.get('success'):
                QMessageBox.information(self, "成功", f"任务 {self.item_id} 已完成")
                self.close()  # 完成任务后关闭窗口
            else:
                QMessageBox.warning(self, "错误", f"完成任务失败: {result.get('error', '未知错误')}")
                
    def update_content(self, content, title):
        # 更新标题
        title_label = self.findChild(QLabel, "title")
        if title_label:
            title_label.setText(title)
        
        # 更新内容
        content_label = self.layout().itemAt(1).widget()  # 内容标签是布局中的第二个元素
        if content_label and isinstance(content_label, QLabel):
            content_label.setText(content)
            content_label.setWordWrap(True)
        
        # 调整窗口大小以适应新内容
        self.adjustSize()

    def closeEvent(self, event):
        self.closed.emit(self.item_type, self.item_id)
        super().closeEvent(event)

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
        self.setFixedSize(500, 450)
        
        layout = QVBoxLayout()
        
        # 服务器设置
        server_group = QGroupBox("服务器设置")
        server_layout = QFormLayout()
        
        self.server_edit = QLineEdit()
        self.board_id_edit = QLineEdit()
        self.secret_key_edit = QLineEdit()
        self.secret_key_edit.setEchoMode(QLineEdit.Password)
        
        server_layout.addRow("服务器地址:", self.server_edit)
        server_layout.addRow("白板ID:", self.board_id_edit)
        server_layout.addRow("白板密钥:", self.secret_key_edit)
        
        server_group.setLayout(server_layout)
        layout.addWidget(server_group)
        
        # 悬浮窗设置
        floating_group = QGroupBox("悬浮窗设置")
        floating_layout = QFormLayout()
        
        # 层级选择
        self.level_combo = QComboBox()
        self.level_combo.addItems(["桌面级", "总是最前", "全屏时不显示"])
        
        # 显示时长
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(5, 120)
        self.timeout_spin.setSuffix(" 秒")
        
        # 无限制显示选项
        self.unlimited_check = QCheckBox("无限制显示悬浮窗")
        self.unlimited_check.stateChanged.connect(self.on_unlimited_changed)
        
        floating_layout.addRow("悬浮层级:", self.level_combo)
        floating_layout.addRow("显示时长:", self.timeout_spin)
        floating_layout.addRow("", self.unlimited_check)
        
        floating_group.setLayout(floating_layout)
        layout.addWidget(floating_group)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        self.save_btn = QPushButton("保存")
        self.save_btn.clicked.connect(self.save_settings)
        self.test_btn = QPushButton("测试连接")
        self.test_btn.clicked.connect(self.test_connection)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.close_dialog)
        
        button_layout.addWidget(self.test_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
    def on_unlimited_changed(self, state):
        # 启用或禁用超时时间设置
        self.timeout_spin.setEnabled(state == Qt.Unchecked)
        
    def load_settings(self):
        settings = QSettings("WhiteboardClient", "Config")
        self.server_edit.setText(settings.value("server", ""))
        self.board_id_edit.setText(settings.value("board_id", ""))
        self.secret_key_edit.setText(settings.value("secret_key", ""))
        self.level_combo.setCurrentIndex(settings.value("float_level", 0, type=int))
        self.timeout_spin.setValue(settings.value("float_timeout", 10, type=int))
        unlimited = settings.value("float_unlimited", False, type=bool)
        self.unlimited_check.setChecked(unlimited)
        self.timeout_spin.setEnabled(not unlimited)
        
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
        settings.setValue("float_level", self.level_combo.currentIndex())
        settings.setValue("float_timeout", self.timeout_spin.value())
        settings.setValue("float_unlimited", self.unlimited_check.isChecked())
        
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
            
    def close_dialog(self):
        self.reject()

# ------------------------------
# 数据查看对话框
# ------------------------------
class DataViewDialog(QDialog):
    def __init__(self, client, parent=None):
        super().__init__(parent)
        self.client = client
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle("查看所有数据")
        self.setMinimumSize(800, 600)
        
        layout = QVBoxLayout()
        
        # 选项卡
        self.tabs = QTabWidget()
        
        # 任务选项卡
        self.task_widget = QWidget()
        self.task_layout = QVBoxLayout()
        self.task_list = QListWidget()
        self.task_layout.addWidget(self.task_list)
        self.task_widget.setLayout(self.task_layout)
        self.tabs.addTab(self.task_widget, "任务")
        
        # 作业选项卡
        self.assignment_widget = QWidget()
        self.assignment_layout = QVBoxLayout()
        self.assignment_list = QListWidget()
        self.assignment_layout.addWidget(self.assignment_list)
        self.assignment_widget.setLayout(self.assignment_layout)
        self.tabs.addTab(self.assignment_widget, "作业")
        
        # 公告选项卡
        self.announcement_widget = QWidget()
        self.announcement_layout = QVBoxLayout()
        self.announcement_list = QListWidget()
        self.announcement_layout.addWidget(self.announcement_list)
        self.announcement_widget.setLayout(self.announcement_layout)
        self.tabs.addTab(self.announcement_widget, "公告")
        
        layout.addWidget(self.tabs)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.refresh_data)
        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.close_dialog)
        
        button_layout.addWidget(self.refresh_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
    def refresh_data(self):
        result = self.client.get_all_data()
        if result.get('success'):
            self.populate_data(result.get('data', []))
        else:
            QMessageBox.warning(self, "错误", f"获取数据失败: {result.get('error', '未知错误')}")
            
    def populate_data(self, data):
        # 清空列表
        self.task_list.clear()
        self.assignment_list.clear()
        self.announcement_list.clear()
        
        # 填充数据
        for item in data:
            item_type = item.get('type', '')
            item_id = item.get('id', '')
            title = item.get('title', '无标题')
            
            if item_type == 'task':
                # 只显示未完成的任务
                if item.get('is_completed', False):
                    continue
                    
                description = item.get('description', '无描述')
                priority = item.get('priority', 1)
                due_date = item.get('due_date', '无截止时间')
                is_acknowledged = item.get('is_acknowledged', False)
                is_completed = item.get('is_completed', False)
                
                # 创建自定义列表项
                item_widget = QWidget()
                item_layout = QVBoxLayout()
                
                # 基本信息
                info_layout = QHBoxLayout()
                title_label = QLabel(f"[ID: {item_id}] {title}")
                title_label.setStyleSheet("font-weight: bold;")
                info_layout.addWidget(title_label)
                
                status_label = QLabel(f"优先级: {priority} | 截止: {due_date}")
                info_layout.addWidget(status_label)
                
                ack_label = QLabel(f"已确认: {'是' if is_acknowledged else '否'} | 已完成: {'是' if is_completed else '否'}")
                info_layout.addWidget(ack_label)
                
                item_layout.addLayout(info_layout)
                
                # 描述
                desc_label = QLabel(f"描述: {description}")
                desc_label.setWordWrap(True)
                item_layout.addWidget(desc_label)
                
                # 操作按钮（如果任务未完成）
                if not is_completed:
                    btn_layout = QHBoxLayout()
                    
                    ack_btn = QPushButton("确认任务")
                    ack_btn.clicked.connect(lambda checked=False, tid=item_id: self.acknowledge_task(tid))
                    
                    complete_btn = QPushButton("完成任务")
                    complete_btn.clicked.connect(lambda checked=False, tid=item_id: self.complete_task(tid))
                    
                    btn_layout.addWidget(ack_btn)
                    btn_layout.addWidget(complete_btn)
                    item_layout.addLayout(btn_layout)
                
                item_widget.setLayout(item_layout)
                
                # 创建列表项并设置自定义widget
                list_item = QListWidgetItem()
                list_item.setSizeHint(item_widget.sizeHint())
                self.task_list.addItem(list_item)
                self.task_list.setItemWidget(list_item, item_widget)
                
            elif item_type == 'assignment':
                subject = item.get('subject', '无科目')
                description = item.get('description', '无描述')
                due_date = item.get('due_date', '无截止时间')
                
                item_text = f"[ID: {item_id}] {title} ({subject})\n截止: {due_date}\n"
                item_text += f"描述: {description}"
                
                list_item = QListWidgetItem(item_text)
                list_item.setData(Qt.UserRole, item_id)
                self.assignment_list.addItem(list_item)
                
            elif item_type == 'announcement':
                # 只显示未截止的公告
                due_date_str = item.get('due_date', '')
                is_long_term = item.get('is_long_term', False)
                
                # 检查公告是否已截止（如果不是长期公告且有截止日期）
                if not is_long_term and due_date_str:
                    try:
                        due_date = datetime.strptime(due_date_str, "%Y-%m-%d %H:%M:%S")
                        if due_date < datetime.now():
                            continue  # 已截止，不显示
                    except ValueError:
                        # 日期格式解析错误，按未截止处理
                        pass
                
                content = item.get('content', '无内容')
                
                item_text = f"[ID: {item_id}] {title}\n长期公告: {'是' if is_long_term else '否'}\n"
                item_text += f"内容: {content}"
                
                list_item = QListWidgetItem(item_text)
                list_item.setData(Qt.UserRole, item_id)
                self.announcement_list.addItem(list_item)
                
    def acknowledge_task(self, task_id):
        result = self.client.acknowledge_task(task_id)
        if result.get('success'):
            QMessageBox.information(self, "成功", f"任务 {task_id} 已确认")
            self.refresh_data()
        else:
            QMessageBox.warning(self, "错误", f"确认任务失败: {result.get('error', '未知错误')}")
            
    def complete_task(self, task_id):
        result = self.client.complete_task(task_id)
        if result.get('success'):
            QMessageBox.information(self, "成功", f"任务 {task_id} 已完成")
            self.refresh_data()
        else:
            QMessageBox.warning(self, "错误", f"完成任务失败: {result.get('error', '未知错误')}")
            
    def close_dialog(self):
        self.reject()

# ------------------------------
# 主应用和系统托盘
# ------------------------------
class WhiteboardApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.client = WhiteboardClient()
        self.tray_icon = None
        self.floating_windows = {}  # 使用字典存储悬浮窗，键为 (item_type, item_id)
        self.float_level = 0  # 0:桌面级, 1:总是最前, 2:全屏时不显示
        self.float_timeout = 10  # 默认10秒
        self.float_unlimited = False  # 是否无限制显示悬浮窗
        self.window_positions = {}  # 存储窗口位置，避免重叠
        self.next_window_y = 50  # 下一个窗口的Y坐标，用于避免重叠
        
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
            QMainWindow, QDialog, QWidget {
                background-color: #f5f5f5;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #e0e0e0;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
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
            QTabWidget::pane {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                background-color: white;
            }
            QTabBar::tab {
                background-color: #f0f0f0;
                border: 1px solid #e0e0e0;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: white;
                border-bottom-color: white;
            }
        """)
        
    def load_settings(self):
        settings = QSettings("WhiteboardClient", "Config")
        server = settings.value("server", "")
        board_id = settings.value("board_id", "")
        secret_key = settings.value("secret_key", "")
        self.float_level = settings.value("float_level", 0, type=int)
        self.float_timeout = settings.value("float_timeout", 10, type=int) * 1000  # 转换为毫秒
        self.float_unlimited = settings.value("float_unlimited", False, type=bool)
        
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
            # 只显示未完成的任务
            if not task.get('is_completed', False):
                content = f"标题：{task['title']}\n优先级：{task['priority']}\n描述：{task.get('description', '无')}"
                self.show_floating_window(content, "新任务", "task", task.get('id', ''))
            
        @sio.on('delete_task')
        def on_delete_task(data):
            task_id = data.get('task_id')
            if task_id:
                self.remove_floating_window("task", task_id)
                self.show_deletion_notification("任务", task_id)
            else:
                print(f"删除任务事件中未找到任务ID: {data}")

        @sio.on('delete_assignment')
        def on_delete_assignment(data):
            assignment_id = data.get('assignment_id')
            if assignment_id:
                self.remove_floating_window("assignment", assignment_id)
                self.show_deletion_notification("作业", assignment_id)
            else:
                print(f"删除作业事件中未找到作业ID: {data}")

        @sio.on('delete_announcement')
        def on_delete_announcement(data):
            announcement_id = data.get('announcement_id')
            if announcement_id:
                self.remove_floating_window("announcement", announcement_id)
                self.show_deletion_notification("公告", announcement_id)
            else:
                print(f"删除公告事件中未找到公告ID: {data}")
                    
                @sio.on('new_announcement')
                def on_new_announcement(ann):
                    # 只显示未截止的公告
                    due_date_str = ann.get('due_date', '')
                    is_long_term = ann.get('is_long_term', False)
                    
                    # 检查公告是否已截止（如果不是长期公告且有截止日期）
                    if not is_long_term and due_date_str:
                        try:
                            due_date = datetime.strptime(due_date_str, "%Y-%m-%d %H:%M:%S")
                            if due_date < datetime.now():
                                return  # 已截止，不显示
                        except ValueError:
                            # 日期格式解析错误，按未截止处理
                            pass
                            
                    content = f"标题：{ann['title']}\n长期有效：{'是' if ann.get('is_long_term', False) else '否'}\n内容：{ann['content']}"
                    self.show_floating_window(content, "新公告", "announcement", ann.get('id', ''))
            
        @sio.on('new_assignment')
        def on_new_assignment(ass):
            content = f"标题：{ass['title']}（{ass['subject']}）\n截止时间：{ass['due_date']}\n描述：{ass['description']}"
            self.show_floating_window(content, "新作业", "assignment", ass.get('id', ''))
            
        @sio.on('update_assignment')
        def on_update_assignment(ass):
            assignment_id = ass.get('id', '')
            content = f"标题：{ass['title']}（{ass['subject']}）\n截止时间：{ass['due_date']}\n描述：{ass['description']}"
            
            # 使用更安全的方式更新作业
            self.load_initial_data()
            
    def show_deletion_notification(self, item_type, item_id):
        # 显示删除通知
        # self.show_floating_window(f"{item_type} {item_id} 已被删除", f"{item_type}删除")
        pass
            
    def show_floating_window(self, content, title, item_type="", item_id=""):
        # 检查是否全屏应用运行中
        if self.float_level == 2 and self.is_fullscreen_app_running():
            return
            
        # 如果已经存在相同类型的窗口，先移除
        if (item_type, item_id) in self.floating_windows:
            window = self.floating_windows[(item_type, item_id)]
            window.close()
            del self.floating_windows[(item_type, item_id)]
            
        # 获取屏幕尺寸
        screen_geometry = self.app.primaryScreen().geometry()
        
        # 计算新窗口位置（右上角，并避免重叠）
        x = screen_geometry.width() - 350
        
        # 使用next_window_y来避免重叠，每次增加窗口高度+间距
        y = self.next_window_y
        
        # 决定超时时间（如果启用无限制显示，则timeout=0）
        timeout = 0 if self.float_unlimited else self.float_timeout
        
        # 创建悬浮窗，传入self作为app参数
        window = FloatingWindow(content, title, timeout, item_type, item_id, self)
        
        # 设置窗口层级
        if self.float_level == 1:  # 总是最前
            window.setWindowFlags(window.windowFlags() | Qt.WindowStaysOnTopHint)
        else:  # 桌面级
            window.setWindowFlags((window.windowFlags() | Qt.WindowStaysOnBottomHint) & ~Qt.WindowStaysOnTopHint)
        
        window.move(x, y)
        window.show()
        
        # 更新下一个窗口的Y坐标（当前窗口高度 + 间距）
        window_height = window.height()
        self.next_window_y = y + window_height + 10
        
        # 如果超出屏幕底部，重置到顶部
        if self.next_window_y + 100 > screen_geometry.height():  # 100是预估的新窗口最小高度
            self.next_window_y = 50
        
        # 存储窗口引用和位置
        self.floating_windows[(item_type, item_id)] = window
        self.window_positions[(item_type, item_id)] = window.pos()
        
        # 窗口关闭时从字典中移除
        window.closed.connect(self.on_floating_window_closed)
        
    def remove_floating_window(self, item_type, item_id):
        # 移除指定悬浮窗
        if (item_type, item_id) in self.floating_windows:
            window = self.floating_windows[(item_type, item_id)]
            window.close()
            del self.floating_windows[(item_type, item_id)]
            if (item_type, item_id) in self.window_positions:
                del self.window_positions[(item_type, item_id)]
                
    def on_floating_window_closed(self, item_type, item_id):
        # 悬浮窗关闭时的回调
        if (item_type, item_id) in self.floating_windows:
            del self.floating_windows[(item_type, item_id)]
        if (item_type, item_id) in self.window_positions:
            del self.window_positions[(item_type, item_id)]
            
        # 当一个窗口关闭时，重置下一个窗口的位置到顶部
        # 这样下次打开新窗口时会从顶部开始排列
        if not self.floating_windows:
            self.next_window_y = 50
        
    def is_fullscreen_app_running(self):
        # 检测是否有全屏应用运行
        # 这是一个简化的实现，实际可能需要更复杂的检测逻辑
        try:
            from PySide6.QtGui import QGuiApplication
            active_window = QGuiApplication.focusWindow()
            if active_window and active_window.windowState() & Qt.WindowFullScreen:
                return True
        except:
            pass
        return False
        
    def load_initial_data(self):
        # 加载初始数据并显示悬浮窗
        if not self.client.board_id or not self.client.secret_key:
            return
            
        # 重置窗口位置计数器
        self.next_window_y = 50
            
        result = self.client.get_all_data()
        if result.get('success'):
            for item in result.get('data', []):
                item_type = item.get('type', '')
                item_id = item.get('id', '')
                title = item.get('title', '无标题')
                
                if item_type == 'task':
                    # 只显示未完成的任务
                    if item.get('is_completed', False):
                        continue
                        
                    description = item.get('description', '无描述')
                    priority = item.get('priority', 1)
                    content = f"标题：{title}\n优先级：{priority}\n描述：{description}"
                    self.show_floating_window(content, "任务", "task", item_id)
                    
                elif item_type == 'assignment':
                    subject = item.get('subject', '无科目')
                    description = item.get('description', '无描述')
                    due_date = item.get('due_date', '无截止时间')
                    content = f"标题：{title}（{subject}）\n截止时间：{due_date}\n描述：{description}"
                    self.show_floating_window(content, "作业", "assignment", item_id)
                    
                elif item_type == 'announcement':
                    # 只显示未截止的公告
                    due_date_str = item.get('due_date', '')
                    is_long_term = item.get('is_long_term', False)
                    
                    # 检查公告是否已截止（如果不是长期公告且有截止日期）
                    if not is_long_term and due_date_str:
                        try:
                            due_date = datetime.strptime(due_date_str, "%Y-%m-%d %H:%M:%S")
                            if due_date < datetime.now():
                                continue  # 已截止，不显示
                        except ValueError:
                            # 日期格式解析错误，按未截止处理
                            pass
                            
                    content_text = item.get('content', '无内容')
                    content = f"标题：{title}\n长期有效：{'是' if is_long_term else '否'}\n内容：{content_text}"
                    self.show_floating_window(content, "公告", "announcement", item_id)
        
    def setup_tray_icon(self):
        # 创建系统托盘图标
        self.tray_icon = QSystemTrayIcon()
        
        # 创建托盘图标菜单
        tray_menu = QMenu()
        
        settings_action = QAction("设置", self.app)
        settings_action.triggered.connect(self.show_settings)
        tray_menu.addAction(settings_action)
        
        view_data_action = QAction("查看所有数据", self.app)
        view_data_action.triggered.connect(self.show_data_view)
        tray_menu.addAction(view_data_action)
        
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
        
        # 设置托盘图标
        self.tray_icon.setIcon(self.create_tray_icon())
        self.tray_icon.setToolTip("白板客户端")
        self.tray_icon.show()
        
        # 托盘图标点击事件
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        
    def create_tray_icon(self):
        # 创建一个简单的托盘图标
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(98, 0, 234))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(0, 0, 16, 16)
        painter.end()
        
        return QIcon(pixmap)
        
    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_settings()
            
    def show_settings(self):
        dialog = SettingsDialog(self.client, None)
        if dialog.exec() == QDialog.Accepted:
            # 设置已保存，重新加载设置并尝试重新连接
            self.load_settings()
            self.disconnect_client()
            self.connect_client()
            
    def show_data_view(self):
        dialog = DataViewDialog(self.client, None)
        dialog.refresh_data()
        dialog.exec()
            
    def connect_client(self):
        if self.client.connect_socket():
            self.tray_icon.showMessage("连接成功", "已成功连接到白板服务器", QSystemTrayIcon.Information, 2000)
            # 连接成功后加载初始数据
            self.load_initial_data()
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