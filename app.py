import sys
import json
import socketio
import requests
from datetime import datetime
from urllib.parse import urlparse
from pathlib import Path
import threading
import time

from PySide6.QtCore import Qt, QTimer, QPoint, QSettings, QSize, Signal
from PySide6.QtGui import QIcon, QFont, QAction, QColor, QPalette, QPixmap, QPainter, QGuiApplication
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                              QLabel, QLineEdit, QPushButton, QTextEdit, QListWidget, 
                              QListWidgetItem, QSystemTrayIcon, QMenu, QDialog, QFormLayout,
                              QMessageBox, QCheckBox, QScrollArea, QFrame, QSizePolicy,
                              QComboBox, QGroupBox, QSpinBox, QToolButton, QButtonGroup,
                              QRadioButton, QTabWidget, QGridLayout, QGraphicsDropShadowEffect)

# ------------------------------
# 现代化悬浮窗实现
# ------------------------------
class ModernFloatingWindow(QWidget):
    closed = Signal(str, str)  # 参数: item_type, item_id
    
    def __init__(self, content, title="通知", timeout=10000, item_type="", item_id="", app=None, 
                 font_size=12, window_width=350, opacity=0.95):
        super().__init__(None, Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.item_type = item_type
        self.item_id = item_id
        self.app = app
        self.font_size = font_size
        self.window_width = window_width
        self.opacity = opacity
        self.setup_ui(content, title)
        self.setup_behavior(timeout)
        
    def setup_ui(self, content, title):
        # 设置窗口样式
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet(self.get_stylesheet())
        self.setWindowOpacity(self.opacity)
        
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(5)
        
        # 标题栏
        title_bar = self.create_title_bar(title)
        main_layout.addWidget(title_bar)
        
        # 内容区域
        content_widget = self.create_content_widget(content)
        main_layout.addWidget(content_widget)
        
        # 操作按钮区域（如果是任务）
        if self.item_type == "task" and self.item_id:
            action_buttons = self.create_action_buttons()
            main_layout.addLayout(action_buttons)
            
        self.adjustSize()
        
    def create_title_bar(self, title):
        title_bar = QWidget()
        title_bar.setFixedHeight(30)
        title_bar_layout = QHBoxLayout(title_bar)
        title_bar_layout.setContentsMargins(5, 0, 5, 0)
        
        title_label = QLabel(title)
        title_label.setObjectName("title")
        title_font = QFont()
        title_font.setPointSize(self.font_size + 2)  # 标题比内容大2点
        title_font.setBold(True)
        title_label.setFont(title_font)
        
        close_btn = QPushButton("×")
        close_btn.setFixedSize(20, 20)
        close_btn.setStyleSheet("border: none; background: transparent; font-weight: bold;")
        close_btn.clicked.connect(self.close)
        
        title_bar_layout.addWidget(title_label)
        title_bar_layout.addStretch()
        title_bar_layout.addWidget(close_btn)
        
        return title_bar
        
    def create_content_widget(self, content):
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        content_label = QLabel(content)
        content_label.setWordWrap(True)
        content_label.setMinimumWidth(self.window_width - 40)  # 减去边距
        content_label.setMaximumWidth(self.window_width - 40)
        
        content_font = QFont()
        content_font.setPointSize(self.font_size)
        content_label.setFont(content_font)
        
        content_layout.addWidget(content_label)
        return content_widget
        
    def create_action_buttons(self):
        button_layout = QHBoxLayout()
        
        ack_btn = QPushButton("确认任务")
        ack_btn.setObjectName("actionBtn")
        ack_btn.clicked.connect(self.acknowledge_task)
        
        complete_btn = QPushButton("完成任务")
        complete_btn.setObjectName("actionBtn")
        complete_btn.clicked.connect(self.complete_task)
        
        button_layout.addWidget(ack_btn)
        button_layout.addWidget(complete_btn)
        
        return button_layout
        
    def get_stylesheet(self):
        return f"""
            ModernFloatingWindow {{
                background-color: rgba(255, 255, 255, {int(self.opacity * 100)}%);
                border-radius: 12px;
                border: 1px solid #e0e0e0;
            }}
            QLabel#title {{
                font-weight: bold;
                color: #6200ea;
                font-size: {self.font_size + 2}px;
            }}
            QPushButton#actionBtn {{
                background-color: #e0e0e0;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: {self.font_size}px;
            }}
            QPushButton#actionBtn:hover {{
                background-color: #d0d0d0;
            }}
            QPushButton#actionBtn:pressed {{
                background-color: #c0c0c0;
            }}
        """
        
    def setup_behavior(self, timeout):
        # 设置超时自动关闭
        if timeout > 0:
            QTimer.singleShot(timeout, self.close)
            
        # 添加阴影效果
        self.add_shadow_effect()
        
    def add_shadow_effect(self):
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 100))
        shadow.setOffset(0, 0)
        self.setGraphicsEffect(shadow)
        
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            
    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and hasattr(self, 'drag_position'):
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()
            
    def acknowledge_task(self):
        if self.app and hasattr(self.app, 'client'):
            result = self.app.client.acknowledge_task(self.item_id)
            if result.get('success'):
                QMessageBox.information(self, "成功", f"任务 {self.item_id} 已确认")
            else:
                QMessageBox.warning(self, "错误", f"确认任务失败: {result.get('error', '未知错误')}")
                
    def complete_task(self):
        if self.app and hasattr(self.app, 'client'):
            result = self.app.client.complete_task(self.item_id)
            if result.get('success'):
                QMessageBox.information(self, "成功", f"任务 {self.item_id} 已完成")
                self.close()
            else:
                QMessageBox.warning(self, "错误", f"完成任务失败: {result.get('error', '未知错误')}")
                
    def update_content(self, content, title):
        # 查找并更新标题和内容
        for child in self.findChildren(QLabel):
            if child.objectName() == "title":
                child.setText(title)
            elif isinstance(child, QLabel) and not child.objectName():
                child.setText(content)
                break
        
        self.adjustSize()

    def closeEvent(self, event):
        self.closed.emit(self.item_type, self.item_id)
        super().closeEvent(event)

# ------------------------------
# 现代化设置对话框
# ------------------------------
class ModernSettingsDialog(QDialog):
    def __init__(self, client, parent=None):
        super().__init__(parent)
        self.client = client
        self.setup_ui()
        self.load_settings()
        
    def setup_ui(self):
        self.setWindowTitle("白板客户端设置")
        self.setMinimumSize(500, 500)
        
        layout = QVBoxLayout(self)
        
        # 创建选项卡
        tab_widget = QTabWidget()
        
        # 服务器设置选项卡
        server_tab = QWidget()
        self.setup_server_tab(server_tab)
        tab_widget.addTab(server_tab, "服务器")
        
        # 通知设置选项卡
        notification_tab = QWidget()
        self.setup_notification_tab(notification_tab)
        tab_widget.addTab(notification_tab, "通知")
        
        # 外观设置选项卡
        appearance_tab = QWidget()
        self.setup_appearance_tab(appearance_tab)
        tab_widget.addTab(appearance_tab, "外观")
        
        layout.addWidget(tab_widget)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        self.test_btn = QPushButton("测试连接")
        self.test_btn.clicked.connect(self.test_connection)
        self.save_btn = QPushButton("保存")
        self.save_btn.clicked.connect(self.save_settings)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)  # 使用reject()而不是close()
        
        button_layout.addWidget(self.test_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
        
    def setup_server_tab(self, tab):
        layout = QFormLayout(tab)
        
        self.server_edit = QLineEdit()
        self.board_id_edit = QLineEdit()
        self.secret_key_edit = QLineEdit()
        self.secret_key_edit.setEchoMode(QLineEdit.Password)
        
        layout.addRow("服务器地址:", self.server_edit)
        layout.addRow("白板ID:", self.board_id_edit)
        layout.addRow("白板密钥:", self.secret_key_edit)
        
    def setup_notification_tab(self, tab):
        layout = QFormLayout(tab)
        
        self.level_combo = QComboBox()
        self.level_combo.addItems(["桌面级", "总是最前", "全屏时不显示"])
        
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(5, 120)
        self.timeout_spin.setSuffix(" 秒")
        
        self.unlimited_check = QCheckBox("无限制显示悬浮窗")
        self.unlimited_check.stateChanged.connect(self.on_unlimited_changed)
        
        layout.addRow("悬浮层级:", self.level_combo)
        layout.addRow("显示时长:", self.timeout_spin)
        layout.addRow("", self.unlimited_check)
        
    def setup_appearance_tab(self, tab):
        layout = QFormLayout(tab)
        
        # 字体大小设置
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 20)
        self.font_size_spin.setSuffix(" pt")
        
        # 悬浮窗宽度设置
        self.window_width_spin = QSpinBox()
        self.window_width_spin.setRange(200, 600)
        self.window_width_spin.setSuffix(" px")
        
        # 悬浮窗间隔设置
        self.window_spacing_spin = QSpinBox()
        self.window_spacing_spin.setRange(5, 50)
        self.window_spacing_spin.setSuffix(" px")
        
        # 悬浮窗不透明度设置
        self.opacity_spin = QSpinBox()
        self.opacity_spin.setRange(10, 100)
        self.opacity_spin.setSuffix(" %")
        
        layout.addRow("字体大小:", self.font_size_spin)
        layout.addRow("悬浮窗宽度:", self.window_width_spin)
        layout.addRow("悬浮窗间隔:", self.window_spacing_spin)
        layout.addRow("悬浮窗不透明度:", self.opacity_spin)
        
    def on_unlimited_changed(self, state):
        self.timeout_spin.setEnabled(state == Qt.Unchecked)
        
    def load_settings(self):
        settings = QSettings("WhiteboardClient", "Config")
        self.server_edit.setText(settings.value("server", ""))
        self.board_id_edit.setText(settings.value("board_id", ""))
        self.secret_key_edit.setText(settings.value("secret_key", ""))
        self.level_combo.setCurrentIndex(settings.value("float_level", 0, type=int))
        self.timeout_spin.setValue(settings.value("float_timeout", 10, type=int))
        self.unlimited_check.setChecked(settings.value("float_unlimited", False, type=bool))
        self.timeout_spin.setEnabled(not self.unlimited_check.isChecked())
        
        # 加载外观设置
        self.font_size_spin.setValue(settings.value("font_size", 12, type=int))
        self.window_width_spin.setValue(settings.value("window_width", 350, type=int))
        self.window_spacing_spin.setValue(settings.value("window_spacing", 10, type=int))
        self.opacity_spin.setValue(settings.value("window_opacity", 95, type=int))
        
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
        
        # 保存外观设置
        settings.setValue("font_size", self.font_size_spin.value())
        settings.setValue("window_width", self.window_width_spin.value())
        settings.setValue("window_spacing", self.window_spacing_spin.value())
        settings.setValue("window_opacity", self.opacity_spin.value())
        
        self.client.setup(server, board_id, secret_key)
        QMessageBox.information(self, "成功", "设置已保存")
        self.accept()  # 使用accept()而不是close()
        
    def test_connection(self):
        server = self.server_edit.text().strip()
        board_id = self.board_id_edit.text().strip()
        secret_key = self.secret_key_edit.text().strip()
        
        if not server or not board_id or not secret_key:
            QMessageBox.warning(self, "输入错误", "请填写所有字段")
            return
            
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

    # 添加closeEvent处理，确保不会意外退出程序
    def closeEvent(self, event):
        self.reject()
        event.accept()

# ------------------------------
# 现代化数据查看对话框
# ------------------------------
class ModernDataViewDialog(QDialog):
    def __init__(self, client, parent=None):
        super().__init__(parent)
        self.client = client
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle("查看所有数据")
        self.setMinimumSize(800, 600)
        
        layout = QVBoxLayout(self)
        
        # 刷新按钮
        refresh_layout = QHBoxLayout()
        self.refresh_btn = QPushButton("刷新数据")
        self.refresh_btn.clicked.connect(self.refresh_data)
        refresh_layout.addWidget(self.refresh_btn)
        refresh_layout.addStretch()
        
        layout.addLayout(refresh_layout)
        
        # 选项卡
        self.tabs = QTabWidget()
        
        # 任务选项卡
        self.task_widget = QWidget()
        self.setup_task_tab(self.task_widget)
        self.tabs.addTab(self.task_widget, "任务")
        
        # 作业选项卡
        self.assignment_widget = QWidget()
        self.setup_assignment_tab(self.assignment_widget)
        self.tabs.addTab(self.assignment_widget, "作业")
        
        # 公告选项卡
        self.announcement_widget = QWidget()
        self.setup_announcement_tab(self.announcement_widget)
        self.tabs.addTab(self.announcement_widget, "公告")
        
        layout.addWidget(self.tabs)
        
        # 关闭按钮
        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.reject)  # 使用reject()而不是close()
        layout.addWidget(self.close_btn)
        
    def setup_task_tab(self, tab):
        layout = QVBoxLayout(tab)
        self.task_list = QListWidget()
        layout.addWidget(self.task_list)
        
    def setup_assignment_tab(self, tab):
        layout = QVBoxLayout(tab)
        self.assignment_list = QListWidget()
        layout.addWidget(self.assignment_list)
        
    def setup_announcement_tab(self, tab):
        layout = QVBoxLayout(tab)
        self.announcement_list = QListWidget()
        layout.addWidget(self.announcement_list)
        
    def refresh_data(self):
        result = self.client.get_all_data()
        if result.get('success'):
            self.populate_data(result.get('data', []))
            QMessageBox.information(self, "成功", "数据已刷新")
        else:
            QMessageBox.warning(self, "错误", f"获取数据失败: {result.get('error', '未知错误')}")
            
    def populate_data(self, data):
        # 清空所有列表
        self.task_list.clear()
        self.assignment_list.clear()
        self.announcement_list.clear()
        
        # 填充数据
        for item in data:
            item_type = item.get('type', '')
            item_id = item.get('id', '')
            title = item.get('title', '无标题')
            
            if item_type == 'task':
                if item.get('is_completed', False):
                    continue
                    
                description = item.get('description', '无描述')
                priority = item.get('priority', 1)
                due_date = item.get('due_date', '无截止时间')
                is_acknowledged = item.get('is_acknownledged', False)
                
                item_text = f"[ID: {item_id}] {title}\n优先级: {priority} | 截止: {due_date}\n"
                item_text += f"已确认: {'是' if is_acknowledged else '否'} | 描述: {description}"
                
                list_item = QListWidgetItem(item_text)
                list_item.setData(Qt.UserRole, item_id)
                self.task_list.addItem(list_item)
                
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
                due_date_str = item.get('due_date', '')
                is_long_term = item.get('is_long_term', False)
                
                if not is_long_term and due_date_str:
                    try:
                        due_date = datetime.strptime(due_date_str, "%Y-%m-%d %H:%M:%S")
                        if due_date < datetime.now():
                            continue
                    except ValueError:
                        pass
                
                content = item.get('content', '无内容')
                
                item_text = f"[ID: {item_id}] {title}\n长期公告: {'是' if is_long_term else '否'}\n"
                item_text += f"内容: {content}"
                
                list_item = QListWidgetItem(item_text)
                list_item.setData(Qt.UserRole, item_id)
                self.announcement_list.addItem(list_item)

    # 添加closeEvent处理，确保不会意外退出程序
    def closeEvent(self, event):
        self.reject()
        event.accept()

# ------------------------------
# 现代化系统托盘和应用管理
# ------------------------------
class ModernTrayIcon(QSystemTrayIcon):
    def __init__(self, app_manager):
        super().__init__()
        self.app_manager = app_manager
        self.setup_ui()
        
    def setup_ui(self):
        # 创建托盘图标
        self.setIcon(self.create_icon())
        self.setToolTip("白板客户端")
        
        # 创建上下文菜单
        menu = QMenu()
        
        settings_action = QAction("设置", menu)
        settings_action.triggered.connect(self.app_manager.show_settings)
        menu.addAction(settings_action)
        
        view_data_action = QAction("查看数据", menu)
        view_data_action.triggered.connect(self.app_manager.show_data_view)
        menu.addAction(view_data_action)
        
        connect_action = QAction("连接", menu)
        connect_action.triggered.connect(self.app_manager.connect_client)
        menu.addAction(connect_action)
        
        disconnect_action = QAction("断开", menu)
        disconnect_action.triggered.connect(self.app_manager.disconnect_client)
        menu.addAction(disconnect_action)
        
        menu.addSeparator()
        
        exit_action = QAction("退出", menu)
        exit_action.triggered.connect(self.app_manager.quit)
        menu.addAction(exit_action)
        
        self.setContextMenu(menu)
        self.activated.connect(self.on_activated)
        
    def create_icon(self):
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(98, 0, 234))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(0, 0, 16, 16)
        painter.end()
        
        return QIcon(pixmap)
        
    def on_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.app_manager.show_settings()

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

class ModernAppManager:
    def __init__(self):
        self.app = QApplication(sys.argv)
        # 设置应用程序不随着最后一个窗口关闭而退出
        self.app.setQuitOnLastWindowClosed(False)
        self.client = WhiteboardClient()
        self.tray_icon = None
        self.floating_windows = {}
        self.window_positions = {}
        self.next_window_y = 50
        self.last_update_time = datetime.now()
        self.polling_timer = None
        self.heartbeat_timer = None
        
        # 对话框引用
        self.settings_dialog = None
        self.data_view_dialog = None
        
        # 加载设置
        self.load_settings()
        
        # 设置应用样式
        self.apply_modern_style()
        
        # 设置轮询更新和心跳
        self.setup_polling()
        self.setup_heartbeat()
        
    def load_settings(self):
        settings = QSettings("WhiteboardClient", "Config")
        server = settings.value("server", "")
        board_id = settings.value("board_id", "")
        secret_key = settings.value("secret_key", "")
        self.float_level = settings.value("float_level", 0, type=int)
        self.float_timeout = settings.value("float_timeout", 10, type=int) * 1000
        self.float_unlimited = settings.value("float_unlimited", False, type=bool)
        
        # 加载外观设置
        self.font_size = settings.value("font_size", 12, type=int)
        self.window_width = settings.value("window_width", 350, type=int)
        self.window_spacing = settings.value("window_spacing", 10, type=int)
        self.window_opacity = settings.value("window_opacity", 95, type=int) / 100.0  # 转换为0-1范围
        
        if server and board_id and secret_key:
            self.client.setup(server, board_id, secret_key)
            
    def setup_polling(self):
        """设置轮询更新机制"""
        # 每5秒检查一次更新
        self.polling_timer = QTimer()
        self.polling_timer.timeout.connect(self.check_for_updates)
        self.polling_timer.start(5000)  # 5秒
        
    def setup_heartbeat(self):
        """设置心跳机制"""
        # 每30秒发送一次心跳
        self.heartbeat_timer = QTimer()
        self.heartbeat_timer.timeout.connect(self.send_heartbeat)
        self.heartbeat_timer.start(30000)  # 30秒
        
    def send_heartbeat(self):
        """发送心跳信号"""
        if not self.client.board_id or not self.client.secret_key:
            return
            
        try:
            result = self.client.send_heartbeat_api()
            if result.get('success'):
                print(f"【{datetime.now().strftime('%H:%M:%S')}】心跳发送成功")
            else:
                print(f"【{datetime.now().strftime('%H:%M:%S')}】心跳发送失败: {result.get('error', '未知错误')}")
        except Exception as e:
            print(f"【{datetime.now().strftime('%H:%M:%S')}】心跳发送异常: {str(e)}")
        
    def check_for_updates(self):
        """检查是否有更新"""
        if not self.client.board_id or not self.client.secret_key:
            return
            
        # 获取最新数据
        result = self.client.get_all_data()
        if result.get('success'):
            data = result.get('data', [])
            
            # 检查是否有新数据
            current_items = self.get_current_items()
            new_items = self.extract_items_from_data(data)
            
            # 如果有变化，更新窗口
            if current_items != new_items:
                print(f"【{datetime.now().strftime('%H:%M:%S')}】检测到数据变化，更新悬浮窗")
                self.refresh_all_windows()
                
    def get_current_items(self):
        """获取当前显示的项"""
        items = set()
        for key in self.floating_windows.keys():
            item_type, item_id = key
            items.add(f"{item_type}_{item_id}")
        return items
        
    def extract_items_from_data(self, data):
        """从数据中提取项"""
        items = set()
        for item in data:
            item_type = item.get('type', '')
            item_id = item.get('id', '')
            
            # 检查是否应该显示
            if self.should_display_item(item):
                items.add(f"{item_type}_{item_id}")
        return items
        
    def should_display_item(self, item):
        """检查项目是否应该显示"""
        item_type = item.get('type', '')
        
        if item_type == 'task':
            # 只显示未完成的任务
            return not item.get('is_completed', False)
            
        elif item_type == 'assignment':
            # 作业总是显示
            return True
            
        elif item_type == 'announcement':
            # 只显示未截止的公告
            due_date_str = item.get('due_date', '')
            is_long_term = item.get('is_long_term', False)
            
            if not is_long_term and due_date_str:
                try:
                    due_date = datetime.strptime(due_date_str, "%Y-%m-%d %H:%M:%S")
                    return due_date >= datetime.now()
                except ValueError:
                    # 日期格式解析错误，按未截止处理
                    pass
            return True
            
        return False
            
    def apply_modern_style(self):
        # 设置现代风格样式表
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
        
    def refresh_all_windows(self):
        """完全重置所有悬浮窗"""
        print(f"【{datetime.now().strftime('%H:%M:%S')}】更新所有悬浮窗")
        
        # 安全地关闭所有窗口
        for window_key in list(self.floating_windows.keys()):
            window = self.floating_windows[window_key]
            try:
                # 断开信号连接，避免触发closed信号
                window.closed.disconnect()
                window.close()
            except:
                pass
        
        # 清空窗口字典
        self.floating_windows.clear()
        self.window_positions.clear()
        
        # 重置窗口位置
        self.next_window_y = 50
        
        # 重新加载数据
        self.load_initial_data()
            
    def show_floating_window(self, content, title, item_type="", item_id=""):
        if self.float_level == 2 and self.is_fullscreen_app_running():
            return
            
        screen_geometry = self.app.primaryScreen().geometry()
        x = screen_geometry.width() - self.window_width - 20  # 右侧留20px边距
        y = self.next_window_y
        
        timeout = 0 if self.float_unlimited else self.float_timeout
        
        window = ModernFloatingWindow(
            content, title, timeout, item_type, item_id, self,
            self.font_size, self.window_width, self.window_opacity
        )
        
        if self.float_level == 1:
            window.setWindowFlags(window.windowFlags() | Qt.WindowStaysOnTopHint)
        else:
            window.setWindowFlags((window.windowFlags() | Qt.WindowStaysOnBottomHint) & ~Qt.WindowStaysOnTopHint)
        
        window.move(x, y)
        window.show()
        
        window_height = window.height()
        self.next_window_y = y + window_height + self.window_spacing
        
        if self.next_window_y + 100 > screen_geometry.height():
            self.next_window_y = 50
        
        key = (item_type, item_id)
        self.floating_windows[key] = window
        self.window_positions[key] = window.pos()
        
        window.closed.connect(self.on_floating_window_closed)
        
    def on_floating_window_closed(self, item_type, item_id):
        key = (item_type, item_id)
        if key in self.floating_windows:
            del self.floating_windows[key]
        if key in self.window_positions:
            del self.window_positions[key]
        
        if not self.floating_windows:
            self.next_window_y = 50
        
    def is_fullscreen_app_running(self):
        try:
            active_window = QGuiApplication.focusWindow()
            if active_window and active_window.windowState() & Qt.WindowFullScreen:
                return True
        except:
            pass
        return False
        
    def load_initial_data(self):
        if not self.client.board_id or not self.client.secret_key:
            return
            
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
        
    def setup_tray(self):
        self.tray_icon = ModernTrayIcon(self)
        self.tray_icon.show()
        
        # 添加刷新菜单项
        refresh_action = QAction("刷新", self.app)
        refresh_action.triggered.connect(self.refresh_all_windows)
        self.tray_icon.contextMenu().insertAction(
            self.tray_icon.contextMenu().actions()[0],  # 插入到第一个位置
            refresh_action
        )
            
    def show_settings(self):
        # 如果对话框已经存在，则激活它
        if self.settings_dialog and self.settings_dialog.isVisible():
            self.settings_dialog.activateWindow()
            return
            
        self.settings_dialog = ModernSettingsDialog(self.client)
        self.settings_dialog.setAttribute(Qt.WA_DeleteOnClose)
        self.settings_dialog.finished.connect(self.on_settings_dialog_finished)
        self.settings_dialog.show()
        
    def on_settings_dialog_finished(self, result):
        if result == QDialog.Accepted:
            self.load_settings()
            # 重新启动轮询和心跳
            if self.polling_timer:
                self.polling_timer.stop()
            if self.heartbeat_timer:
                self.heartbeat_timer.stop()
            self.setup_polling()
            self.setup_heartbeat()
            # 刷新所有窗口以应用新的外观设置
            self.refresh_all_windows()
        self.settings_dialog = None
            
    def show_data_view(self):
        # 如果对话框已经存在，则激活它
        if self.data_view_dialog and self.data_view_dialog.isVisible():
            self.data_view_dialog.activateWindow()
            return
            
        self.data_view_dialog = ModernDataViewDialog(self.client)
        self.data_view_dialog.setAttribute(Qt.WA_DeleteOnClose)
        self.data_view_dialog.finished.connect(lambda: setattr(self, 'data_view_dialog', None))
        self.data_view_dialog.show()
            
    def connect_client(self):
        # 重新启动轮询和心跳
        if self.polling_timer:
            self.polling_timer.stop()
        if self.heartbeat_timer:
            self.heartbeat_timer.stop()
        self.setup_polling()
        self.setup_heartbeat()
        self.tray_icon.showMessage("连接成功", "已成功连接到白板服务器", QSystemTrayIcon.Information, 2000)
        self.load_initial_data()
            
    def disconnect_client(self):
        # 停止轮询和心跳
        if self.polling_timer:
            self.polling_timer.stop()
        if self.heartbeat_timer:
            self.heartbeat_timer.stop()
        self.tray_icon.showMessage("已断开", "已断开与白板服务器的连接", QSystemTrayIcon.Information, 2000)
        
    def quit(self):
        # 停止轮询和心跳
        if self.polling_timer:
            self.polling_timer.stop()
        if self.heartbeat_timer:
            self.heartbeat_timer.stop()
        self.app.quit()
        
    def run(self):
        self.setup_tray()
        
        if self.client.board_id and self.client.secret_key:
            self.connect_client()
            
        sys.exit(self.app.exec())

# ------------------------------
# 主函数
# ------------------------------
if __name__ == "__main__":
    app = ModernAppManager()
    app.run()