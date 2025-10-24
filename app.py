import sys
import json
import requests
import re
import time
import ctypes
from ctypes import wintypes
from datetime import datetime
from urllib.parse import urlparse
from typing import Dict, List, Optional

from PySide6.QtCore import (Qt, QTimer, QSettings, QThread, Signal, QPoint, 
                           QPropertyAnimation, QEasingCurve, QRect, QSize,
                           QParallelAnimationGroup, QSequentialAnimationGroup, QObject)
from PySide6.QtGui import (QIcon, QFont, QAction, QColor, QPalette, QPixmap, 
                          QPainter, QGuiApplication, QLinearGradient, QBrush,
                          QDesktopServices, QMouseEvent, QPen)
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                              QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                              QTextEdit, QListWidget, QListWidgetItem, 
                              QSystemTrayIcon, QMenu, QDialog, QFormLayout,
                              QMessageBox, QCheckBox, QScrollArea, QFrame, 
                              QSizePolicy, QComboBox, QGroupBox, QSpinBox, 
                              QTabWidget, QGridLayout, QGraphicsDropShadowEffect,
                              QProgressBar, QSplitter, QToolButton, QSlider)

SERVER = "https://dlass.tech" 

try:
    import socketio
    SOCKETIO_AVAILABLE = True
except ImportError:
    SOCKETIO_AVAILABLE = False
    print("python-socketio not available")

# 在SocketIOClientThread类中添加对action_id=2的处理
class SocketIOClientThread(QThread):
    message_received = Signal(dict)
    connected = Signal()
    disconnected = Signal()
    error_occurred = Signal(str)
    refresh_requested = Signal()
    system_notification = Signal(str, str, int)  # 添加紧急级别参数
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.sio = None
        self.running = False
        self.base_url = ""
        self.board_id = ""
        self.secret_key = ""
        
    def setup(self, server, board_id, secret_key):
        self.board_id = board_id
        self.secret_key = secret_key
        
        if not server.startswith(('http://', 'https://')):
            server = 'http://' + server
            
        parsed_url = urlparse(server)
        self.base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        print(f"Socket.IO客户端已设置: {self.base_url}")
        
    def run(self):
        if not SOCKETIO_AVAILABLE:
            error_msg = "python-socketio不可用"
            print(error_msg)
            self.error_occurred.emit(error_msg)
            return
            
        self.running = True
        
        try:
            self.sio = socketio.Client()
            
            self.sio.on('connect', self.on_connected)
            self.sio.on('disconnect', self.on_disconnected)
            self.sio.on('connect_error', self.on_connect_error)
            self.sio.on('connected', self.on_server_connected)
            self.sio.on('new_task', self.on_new_task)
            self.sio.on('new_announcement', self.on_new_announcement)
            self.sio.on('new_assignment', self.on_new_assignment)
            self.sio.on('update_assignment', self.on_update_assignment)
            self.sio.on('delete_task', self.on_delete_task)
            self.sio.on('delete_announcement', self.on_delete_announcement)
            self.sio.on('delete_assignment', self.on_delete_assignment)
            
            connect_url = f"{self.base_url}?board_id={self.board_id}&secret_key={self.secret_key}"
            print(f"正在连接Socket.IO: {connect_url}")
        
            self.sio.connect(
                connect_url,
                transports=['websocket', 'polling'],
                namespaces=['/']
            )
            
            print("Socket.IO连接命令已发送，等待连接...")
            
            while self.running:
                time.sleep(0.1)
                
        except Exception as e:
            error_msg = f"Socket.IO运行异常: {str(e)}"
            print(error_msg)
            self.error_occurred.emit(error_msg)
            
    def on_connected(self):
        print("=== Socket.IO连接已建立 ===")
        self.connected.emit()
        
    def on_disconnected(self):
        print("=== Socket.IO连接已断开 ===")
        self.disconnected.emit()
        
    def on_connect_error(self, data):
        error_msg = f"Socket.IO连接错误: {data}"
        print(error_msg)
        self.error_occurred.emit(error_msg)
        
    def on_server_connected(self, data):
        print(f"【认证结果】状态：{data.get('status')} | 消息：{data.get('message')}")
        
    def on_new_task(self, task_data):
        print(f"收到新任务: {task_data.get('title')}")
        message = {
            'type': 'new_task',
            'data': task_data
        }
        self.message_received.emit(message)
        self.refresh_requested.emit()
        
        action_id = task_data.get('action_id')
        if action_id == 1:
            title = "新任务通知"
            content = f"紧急任务: {task_data.get('title', '无标题')}"
            if task_data.get('description'):
                content += f"\n{task_data.get('description')}"
            
            print(f"触发系统通知: {title} - {content}")
            self.system_notification.emit(title, content, 1)  # 级别1：普通通知
            
        elif action_id == 2:
            title = "系统警告"
            content = f"重要系统通知: {task_data.get('title', '无标题')}"
            if task_data.get('description'):
                content += f"\n{task_data.get('description')}"
            
            print(f"触发系统级警告: {title} - {content}")
            self.system_notification.emit(title, content, 3)  # 级别3：系统级警告（Windows弹窗）
            
    def on_new_announcement(self, announcement_data):
        print(f"收到新公告: {announcement_data.get('title')}")
        message = {
            'type': 'new_announcement',
            'data': announcement_data
        }
        self.message_received.emit(message)
        self.refresh_requested.emit()
        
        # 检查是否需要系统级提醒
        action_id = announcement_data.get('action_id')
        if action_id == 2:
            title = "重要公告"
            content = f"系统公告: {announcement_data.get('title', '无标题')}"
            if announcement_data.get('content'):
                content += f"\n{announcement_data.get('content')}"
            
            print(f"触发系统级公告通知: {title} - {content}")
            self.system_notification.emit(title, content, 3)  # 级别3：系统级警告
            
    def on_new_assignment(self, assignment_data):
        print(f"收到新作业: {assignment_data.get('title')}")
        message = {
            'type': 'new_assignment',
            'data': assignment_data
        }
        self.message_received.emit(message)
        self.refresh_requested.emit()
        
        # 检查是否需要系统级提醒
        action_id = assignment_data.get('action_id')
        if action_id == 2:
            title = "重要作业"
            content = f"系统作业: {assignment_data.get('title', '无标题')}"
            if assignment_data.get('description'):
                content += f"\n{assignment_data.get('description')}"
            
            print(f"触发系统级作业通知: {title} - {content}")
            self.system_notification.emit(title, content, 3)  # 级别3：系统级警告
        
    def on_update_assignment(self, assignment_data):
        print(f"作业已更新: {assignment_data.get('title')}")
        message = {
            'type': 'assignment_updated',
            'data': assignment_data
        }
        self.message_received.emit(message)
        self.refresh_requested.emit()
        
    def on_delete_task(self, data):
        task_id = data.get('task_id')
        print(f"任务被删除: {task_id}")
        message = {
            'type': 'task_deleted',
            'data': data
        }
        self.message_received.emit(message)
        self.refresh_requested.emit()
        
    def on_delete_announcement(self, data):
        print("公告被删除")
        message = {
            'type': 'announcement_deleted',
            'data': data
        }
        self.message_received.emit(message)
        self.refresh_requested.emit()
        
    def on_delete_assignment(self, data):
        print("作业被删除")
        message = {
            'type': 'assignment_deleted',
            'data': data
        }
        self.message_received.emit(message)
        self.refresh_requested.emit()
        
    def send_heartbeat(self):
        if self.sio and self.sio.connected:
            heartbeat_data = {
                "board_id": self.board_id
            }
            self.sio.emit('heartbeat', heartbeat_data)
            print("发送Socket.IO心跳消息")
        else:
            print("Socket.IO未连接，无法发送心跳")
        
    def stop(self):
        print("停止Socket.IO客户端")
        self.running = False
        if self.sio:
            self.sio.disconnect()
        self.wait(2000)
    message_received = Signal(dict)
    connected = Signal()
    disconnected = Signal()
    error_occurred = Signal(str)
    refresh_requested = Signal()
    system_notification = Signal(str, str, int)  # 添加紧急级别参数
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.sio = None
        self.running = False
        self.base_url = ""
        self.board_id = ""
        self.secret_key = ""
        
    def setup(self, server, board_id, secret_key):
        self.board_id = board_id
        self.secret_key = secret_key
        
        if not server.startswith(('http://', 'https://')):
            server = 'http://' + server
            
        parsed_url = urlparse(server)
        self.base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        print(f"Socket.IO客户端已设置: {self.base_url}")
        
    def run(self):
        if not SOCKETIO_AVAILABLE:
            error_msg = "python-socketio不可用"
            print(error_msg)
            self.error_occurred.emit(error_msg)
            return
            
        self.running = True
        
        try:
            self.sio = socketio.Client()
            
            self.sio.on('connect', self.on_connected)
            self.sio.on('disconnect', self.on_disconnected)
            self.sio.on('connect_error', self.on_connect_error)
            self.sio.on('connected', self.on_server_connected)
            self.sio.on('new_task', self.on_new_task)
            self.sio.on('new_announcement', self.on_new_announcement)
            self.sio.on('new_assignment', self.on_new_assignment)
            self.sio.on('update_assignment', self.on_update_assignment)
            self.sio.on('delete_task', self.on_delete_task)
            self.sio.on('delete_announcement', self.on_delete_announcement)
            self.sio.on('delete_assignment', self.on_delete_assignment)
            
            connect_url = f"{self.base_url}?board_id={self.board_id}&secret_key={self.secret_key}"
            print(f"正在连接Socket.IO: {connect_url}")
        
            self.sio.connect(
                connect_url,
                transports=['websocket', 'polling'],
                namespaces=['/']
            )
            
            print("Socket.IO连接命令已发送，等待连接...")
            
            while self.running:
                time.sleep(0.1)
                
        except Exception as e:
            error_msg = f"Socket.IO运行异常: {str(e)}"
            print(error_msg)
            self.error_occurred.emit(error_msg)
            
    def on_connected(self):
        print("=== Socket.IO连接已建立 ===")
        self.connected.emit()
        
    def on_disconnected(self):
        print("=== Socket.IO连接已断开 ===")
        self.disconnected.emit()
        
    def on_connect_error(self, data):
        error_msg = f"Socket.IO连接错误: {data}"
        print(error_msg)
        self.error_occurred.emit(error_msg)
        
    def on_server_connected(self, data):
        print(f"【认证结果】状态：{data.get('status')} | 消息：{data.get('message')}")
        
    def on_new_task(self, task_data):
        print(f"收到新任务: {task_data.get('title')}")
        message = {
            'type': 'new_task',
            'data': task_data
        }
        self.message_received.emit(message)
        self.refresh_requested.emit()
        
        action_id = task_data.get('action_id')
        if action_id == 1:
            title = "新任务通知"
            content = f"紧急任务: {task_data.get('title', '无标题')}"
            if task_data.get('description'):
                content += f"\n{task_data.get('description')}"
            
            print(f"触发系统通知: {title} - {content}")
            self.system_notification.emit(title, content, 1)  # 级别1：普通通知
            
        elif action_id == 2:
            title = "系统警告"
            content = f"重要系统通知: {task_data.get('title', '无标题')}"
            if task_data.get('description'):
                content += f"\n{task_data.get('description')}"
            
            print(f"触发系统级警告: {title} - {content}")
            self.system_notification.emit(title, content, 3)  # 级别3：系统级警告
            
    def on_new_announcement(self, announcement_data):
        print(f"收到新公告: {announcement_data.get('title')}")
        message = {
            'type': 'new_announcement',
            'data': announcement_data
        }
        self.message_received.emit(message)
        self.refresh_requested.emit()
        
        # 检查是否需要系统级提醒
        action_id = announcement_data.get('action_id')
        if action_id == 2:
            title = "重要公告"
            content = f"系统公告: {announcement_data.get('title', '无标题')}"
            if announcement_data.get('content'):
                content += f"\n{announcement_data.get('content')}"
            
            print(f"触发系统级公告通知: {title} - {content}")
            self.system_notification.emit(title, content, 3)  # 级别3：系统级警告
            
    def on_new_assignment(self, assignment_data):
        print(f"收到新作业: {assignment_data.get('title')}")
        message = {
            'type': 'new_assignment',
            'data': assignment_data
        }
        self.message_received.emit(message)
        self.refresh_requested.emit()
        
        # 检查是否需要系统级提醒
        action_id = assignment_data.get('action_id')
        if action_id == 2:
            title = "重要作业"
            content = f"系统作业: {assignment_data.get('title', '无标题')}"
            if assignment_data.get('description'):
                content += f"\n{assignment_data.get('description')}"
            
            print(f"触发系统级作业通知: {title} - {content}")
            self.system_notification.emit(title, content, 3)  # 级别3：系统级警告
        
    def on_update_assignment(self, assignment_data):
        print(f"作业已更新: {assignment_data.get('title')}")
        message = {
            'type': 'assignment_updated',
            'data': assignment_data
        }
        self.message_received.emit(message)
        self.refresh_requested.emit()
        
    def on_delete_task(self, data):
        task_id = data.get('task_id')
        print(f"任务被删除: {task_id}")
        message = {
            'type': 'task_deleted',
            'data': data
        }
        self.message_received.emit(message)
        self.refresh_requested.emit()
        
    def on_delete_announcement(self, data):
        print("公告被删除")
        message = {
            'type': 'announcement_deleted',
            'data': data
        }
        self.message_received.emit(message)
        self.refresh_requested.emit()
        
    def on_delete_assignment(self, data):
        print("作业被删除")
        message = {
            'type': 'assignment_deleted',
            'data': data
        }
        self.message_received.emit(message)
        self.refresh_requested.emit()
        
    def send_heartbeat(self):
        if self.sio and self.sio.connected:
            heartbeat_data = {
                "board_id": self.board_id
            }
            self.sio.emit('heartbeat', heartbeat_data)
            print("发送Socket.IO心跳消息")
        else:
            print("Socket.IO未连接，无法发送心跳")
        
    def stop(self):
        print("停止Socket.IO客户端")
        self.running = False
        if self.sio:
            self.sio.disconnect()
        self.wait(2000)

class WhiteboardClientAPI:
    def __init__(self):
        self.headers = {}
        self.base_url = ""
        self.board_id = ""
        self.secret_key = ""
        self.connected = False
        
    def setup(self, server, board_id, secret_key):
        self.board_id = board_id
        self.secret_key = secret_key
        
        if not server.startswith(('http://', 'https://')):
            server = 'http://' + server
        
        parsed_url = urlparse(server)
        self.base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        self.headers = {
            'X-Board-ID': board_id,
            'X-Secret-Key': secret_key
        }
        
        print(f"API客户端已设置: {self.base_url}, Board ID: {board_id}")

    def get_assignments(self, date=None, subject=None):
        params = {}
        if date:
            params['date'] = date
        if subject:
            params['subject'] = subject
            
        try:
            response = requests.get(
                f"{self.base_url}/api/whiteboard/assignments",
                headers=self.headers,
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"success": False, "error": f"HTTP错误: {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_tasks(self, date=None, priority=None, status=None):
        params = {}
        if date:
            params['date'] = date
        if priority:
            params['priority'] = priority
        if status:
            params['status'] = status
            
        try:
            response = requests.get(
                f"{self.base_url}/api/whiteboard/tasks",
                headers=self.headers,
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"success": False, "error": f"HTTP错误: {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_announcements(self, date=None, long_term=None):
        params = {}
        if date:
            params['date'] = date
        if long_term is not None:
            params['long_term'] = str(long_term).lower()
            
        try:
            response = requests.get(
                f"{self.base_url}/api/whiteboard/announcements",
                headers=self.headers,
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"success": False, "error": f"HTTP错误: {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_all_data(self, date=None):
        params = {}
        if date:
            params['date'] = date
            
        try:
            response = requests.get(
                f"{self.base_url}/api/whiteboard/all",
                headers=self.headers,
                params=params,
                timeout=10
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
                headers=self.headers,
                timeout=10
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
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"success": False, "error": f"HTTP错误: {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def send_heartbeat(self):
        try:
            response = requests.post(
                f"{self.base_url}/api/whiteboard/heartbeat",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"success": False, "error": f"HTTP错误: {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

class DataFetchThread(QThread):
    data_fetched = Signal(list)
    error_occurred = Signal(str)
    
    def __init__(self, api_client):
        super().__init__()
        self.api_client = api_client
        self.running = True
        self.last_fetch_time = 0
        self.fetch_interval = 30
        
    def run(self):
        while self.running:
            current_time = time.time()
            if (current_time - self.last_fetch_time) >= self.fetch_interval:
                if self.api_client.board_id and self.api_client.secret_key:
                    try:
                        result = self.api_client.get_all_data()
                        if result.get('success'):
                            self.data_fetched.emit(result.get('data', []))
                            self.last_fetch_time = current_time
                            print(f"数据获取成功，共{len(result.get('data', []))}条数据")
                        else:
                            self.error_occurred.emit(f"数据获取失败: {result.get('error', '未知错误')}")
                    except Exception as e:
                        self.error_occurred.emit(f"网络错误: {str(e)}")
            time.sleep(1)
            
    def stop(self):
        self.running = False

class HeartbeatThread(QThread):
    heartbeat_sent = Signal(bool, str)
    
    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.running = True
        self.interval = 30
        
    def run(self):
        while self.running:
            if self.api_client.board_id and self.api_client.secret_key:
                try:
                    result = self.api_client.send_heartbeat()
                    success = result.get('success', False)
                    message = result.get('message', '未知状态')
                    self.heartbeat_sent.emit(success, message)
                    print(f"心跳发送: {success}, {message}")
                except Exception as e:
                    self.heartbeat_sent.emit(False, str(e))
                    print(f"心跳发送失败: {str(e)}")
            
            for i in range(self.interval * 2):
                if not self.running:
                    return
                time.sleep(0.5)
    
    def stop(self):
        self.running = False

class DataManager(QObject):
    data_updated = Signal(list)
    task_acknowledged = Signal(str)
    task_completed = Signal(str)
    error_occurred = Signal(str)
    system_notification = Signal(str, str, int)  # 添加紧急级别参数
    socketio_status = Signal(bool, str)
    
    def __init__(self):
        super().__init__()
        self.api_client = WhiteboardClientAPI()
        self.data_thread = None
        self.heartbeat_thread = None
        self.socketio_thread = None
        self.heartbeat_timer = QTimer()
        self.heartbeat_timer.timeout.connect(self.send_socketio_heartbeat)
        
    def setup(self, server, board_id, secret_key):
        self.api_client.setup(server, board_id, secret_key)
        
    def start_data_fetching(self):
        if self.data_thread and self.data_thread.isRunning():
            self.data_thread.stop()
            
        self.data_thread = DataFetchThread(self.api_client)
        self.data_thread.data_fetched.connect(self.data_updated)
        self.data_thread.error_occurred.connect(self.error_occurred)
        self.data_thread.start()
        print("数据获取线程已启动")
        
    def start_heartbeat(self):
        if self.heartbeat_thread and self.heartbeat_thread.isRunning():
            self.heartbeat_thread.stop()
            
        self.heartbeat_thread = HeartbeatThread(self.api_client)
        self.heartbeat_thread.heartbeat_sent.connect(self.on_heartbeat_result)
        self.heartbeat_thread.start()
        print("心跳线程已启动")
        
    def start_socketio(self):
        if not SOCKETIO_AVAILABLE:
            error_msg = "python-socketio不可用"
            print(error_msg)
            self.socketio_status.emit(False, error_msg)
            return
            
        if self.socketio_thread and self.socketio_thread.isRunning():
            print("停止现有的Socket.IO客户端")
            self.socketio_thread.stop()
            self.socketio_thread.wait(2000)
            
        self.socketio_thread = SocketIOClientThread()
        
        self.socketio_thread.message_received.connect(self.on_socketio_message)
        self.socketio_thread.connected.connect(self.on_socketio_connected)
        self.socketio_thread.disconnected.connect(self.on_socketio_disconnected)
        self.socketio_thread.error_occurred.connect(self.on_socketio_error)
        self.socketio_thread.refresh_requested.connect(self.on_refresh_requested)
        self.socketio_thread.system_notification.connect(self.on_system_notification)
        
        settings = QSettings("WhiteboardClient", "Config")
        board_id = settings.value("board_id", "")
        secret_key = settings.value("secret_key", "")
        
        if board_id and secret_key:
            self.socketio_thread.setup(SERVER, board_id, secret_key)
            self.socketio_thread.start()
            print("Socket.IO客户端启动命令已发送")
        else:
            error_msg = "缺少配置，无法启动Socket.IO"
            print(error_msg)
            self.socketio_status.emit(False, error_msg)
            
    def on_refresh_requested(self):
        print("Socket.IO触发数据刷新")
        self.manual_refresh()
        
    def on_system_notification(self, title, content, level):
        print(f"显示系统通知: {title}, 级别: {level}")
        self.system_notification.emit(title, content, level)
        
    def on_socketio_connected(self):
        print("Socket.IO连接成功")
        self.socketio_status.emit(True, "连接成功")
        self.heartbeat_timer.start(10000)
        
    def on_socketio_disconnected(self):
        print("Socket.IO连接断开")
        self.socketio_status.emit(False, "连接断开")
        self.heartbeat_timer.stop()
        
    def on_socketio_error(self, error_msg):
        print(f"Socket.IO错误: {error_msg}")
        self.socketio_status.emit(False, f"错误: {error_msg}")
        self.error_occurred.emit(f"Socket.IO错误: {error_msg}")
        
    def on_socketio_message(self, message):
        print(f"收到Socket.IO消息: {message.get('type')}")
        
    def send_socketio_heartbeat(self):
        if self.socketio_thread:
            self.socketio_thread.send_heartbeat()
        
    def acknowledge_task(self, task_id):
        result = self.api_client.acknowledge_task(task_id)
        if result.get('success'):
            self.task_acknowledged.emit(task_id)
            title = task_id
            content = "已确认" 
            self.system_notification.emit(title, content, 1)
            self.manual_refresh()
        else:
            self.error_occurred.emit(f"确认任务失败: {result.get('error', '未知错误')}")
            
    def complete_task(self, task_id):
        result = self.api_client.complete_task(task_id)
        if result.get('success'):
            self.task_completed.emit(task_id)
            title = task_id
            content = "已完成" 
            self.system_notification.emit(title, content, 1)
            self.manual_refresh()
        else:
            self.error_occurred.emit(f"完成任务失败: {result.get('error', '未知错误')}")
            
    def manual_refresh(self):
        if self.api_client.board_id and self.api_client.secret_key:
            try:
                result = self.api_client.get_all_data()
                if result.get('success'):
                    self.data_updated.emit(result.get('data', []))
                    print("手动刷新数据成功")
                else:
                    self.error_occurred.emit(f"刷新数据失败: {result.get('error', '未知错误')}")
            except Exception as e:
                self.error_occurred.emit(f"刷新数据失败: {str(e)}")
                
    def on_heartbeat_result(self, success, message):
        if not success:
            print(f"心跳发送失败: {message}")
            
    def stop(self):
        self.heartbeat_timer.stop()
        
        if self.data_thread:
            self.data_thread.stop()
            self.data_thread.wait(2000)
        if self.heartbeat_thread:
            self.heartbeat_thread.stop()
            self.heartbeat_thread.wait(2000)
        if self.socketio_thread:
            self.socketio_thread.stop()

class AnimatedButton(QPushButton):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        
        self._animation = QPropertyAnimation(self, b"geometry")
        self._animation.setDuration(200)
        self._animation.setEasingCurve(QEasingCurve.OutCubic)
        
    def enterEvent(self, event):
        self._animate_hover(True)
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        self._animate_hover(False)
        super().leaveEvent(event)
        
    def _animate_hover(self, hover):
        rect = self.geometry()
        if hover:
            self._animation.setStartValue(rect)
            self._animation.setEndValue(QRect(rect.x()-2, rect.y()-2, 
                                            rect.width()+4, rect.height()+4))
        else:
            self._animation.setStartValue(rect)
            self._animation.setEndValue(QRect(rect.x()+2, rect.y()+2, 
                                            rect.width()-4, rect.height()-4))
        self._animation.start()

# 样式配置类
class StyleConfig:
    @staticmethod
    def get_task_style():
        settings = QSettings("WhiteboardClient", "Styles")
        return {
            "title_font_size": settings.value("task_title_font_size", 10, type=int),
            "title_color": settings.value("task_title_color", "#2c3e50"),
            "title_bold": settings.value("task_title_bold", True, type=bool),
            "subject_font_size": settings.value("task_subject_font_size", 8, type=int),
            "subject_color": settings.value("task_subject_color", "#7f8c8d"),
            "content_font_size": settings.value("task_content_font_size", 8, type=int),
            "content_color": settings.value("task_content_color", "#7f8c8d"),
            "time_font_size": settings.value("task_time_font_size", 7, type=int),
            "time_color": settings.value("task_time_color", "#95a5a6")
        }
    
    @staticmethod
    def get_assignment_style():
        settings = QSettings("WhiteboardClient", "Styles")
        return {
            "title_font_size": settings.value("assignment_title_font_size", 10, type=int),
            "title_color": settings.value("assignment_title_color", "#2c3e50"),
            "title_bold": settings.value("assignment_title_bold", True, type=bool),
            "subject_font_size": settings.value("assignment_subject_font_size", 8, type=int),
            "subject_color": settings.value("assignment_subject_color", "#7f8c8d"),
            "content_font_size": settings.value("assignment_content_font_size", 8, type=int),
            "content_color": settings.value("assignment_content_color", "#7f8c8d"),
            "time_font_size": settings.value("assignment_time_font_size", 7, type=int),
            "time_color": settings.value("assignment_time_color", "#95a5a6")
        }
    
    @staticmethod
    def get_announcement_style():
        settings = QSettings("WhiteboardClient", "Styles")
        return {
            "title_font_size": settings.value("announcement_title_font_size", 10, type=int),
            "title_color": settings.value("announcement_title_color", "#2c3e50"),
            "title_bold": settings.value("announcement_title_bold", True, type=bool),
            "subject_font_size": settings.value("announcement_subject_font_size", 8, type=int),
            "subject_color": settings.value("announcement_subject_color", "#7f8c8d"),
            "content_font_size": settings.value("announcement_content_font_size", 8, type=int),
            "content_color": settings.value("announcement_content_color", "#7f8c8d"),
            "time_font_size": settings.value("announcement_time_font_size", 7, type=int),
            "time_color": settings.value("announcement_time_color", "#95a5a6")
        }

class BaseFloatingWindow(QMainWindow):
    def __init__(self, title, color, parent=None):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Tool)
        self.title = title
        self.color = color
        self.data_manager = None
        self.is_collapsed = False
        self.normal_height = 400
        self.collapsed_height = 30
        
        self.setup_ui()
        self.setup_dragging()
        
    def setup_ui(self):
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.title_bar = QWidget()
        self.title_bar.setFixedHeight(30)
        title_layout = QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(10, 0, 10, 0)
        
        self.title_label = QLabel(self.title)
        title_font = QFont()
        title_font.setPointSize(10)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.title_label.setStyleSheet(f"color: {self.color};")
        
        self.count_label = QLabel("0")
        self.count_label.setStyleSheet(f"""
            QLabel {{
                background-color: {self.color};
                color: white;
                border-radius: 10px;
                padding: 2px 6px;
                font-weight: bold;
                font-size: 9px;
                min-width: 16px;
            }}
        """)
        
        self.collapse_btn = QToolButton()
        self.collapse_btn.setText("−")
        self.collapse_btn.setFixedSize(16, 16)
        self.collapse_btn.setStyleSheet("""
            QToolButton {
                background: rgba(255,255,255,0.2);
                border: none;
                border-radius: 3px;
                color: white;
                font-weight: bold;
                font-size: 10px;
            }
            QToolButton:hover {
                background: rgba(255,255,255,0.3);
            }
        """)
        self.collapse_btn.clicked.connect(self.toggle_collapse)
        
        title_layout.addWidget(self.title_label)
        title_layout.addStretch()
        title_layout.addWidget(self.count_label)
        title_layout.addWidget(self.collapse_btn)
        
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setSpacing(8)
        self.content_layout.setContentsMargins(12, 8, 12, 8)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                background: rgba(255,255,255,0.3);
                width: 6px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255,255,255,0.6);
                border-radius: 3px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(255,255,255,0.8);
            }
        """)
        self.scroll_area.setWidget(self.content_widget)
        
        layout.addWidget(self.title_bar)
        layout.addWidget(self.scroll_area)
        
        self.setStyleSheet(f"""
            BaseFloatingWindow {{
                background-color: rgba(255, 255, 255, 0.95);
                border-radius: 8px;
                border: 2px solid {self.color};
            }}
        """)
        
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 60))
        shadow.setOffset(0, 3)
        self.setGraphicsEffect(shadow)
        
        self.setFixedSize(300, self.normal_height)
        
    def setup_dragging(self):
        self.drag_position = None
        
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            
    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.drag_position:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()
            
    def set_data_manager(self, data_manager):
        self.data_manager = data_manager
        
    def update_data(self, data):
        self.clear_layout(self.content_layout)
        
        count = 0
        for item in data:
            if self.should_display_item(item):
                widget = DataItemWidget(item, self.data_manager, self.get_style_config())
                self.content_layout.insertWidget(count, widget)
                count += 1
                
        self.count_label.setText(str(count))
        
    def get_style_config(self):
        # 子类需要重写这个方法
        return {}
        
    def should_display_item(self, item):
        return True
        
    def clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
    def toggle_collapse(self):
        if self.is_collapsed:
            self.expand()
        else:
            self.collapse()
            
    def collapse(self):
        self.is_collapsed = True
        self.collapse_btn.setText("+")
        
        self.animation_group = QParallelAnimationGroup()
        
        height_animation = QPropertyAnimation(self, b"minimumHeight")
        height_animation.setDuration(300)
        height_animation.setEasingCurve(QEasingCurve.InOutCubic)
        height_animation.setStartValue(self.height())
        height_animation.setEndValue(self.collapsed_height)
        
        fixed_height_animation = QPropertyAnimation(self, b"maximumHeight")
        fixed_height_animation.setDuration(300)
        fixed_height_animation.setEasingCurve(QEasingCurve.InOutCubic)
        fixed_height_animation.setStartValue(self.height())
        fixed_height_animation.setEndValue(self.collapsed_height)
        
        self.opacity_animation = QPropertyAnimation(self.scroll_area, b"windowOpacity")
        self.opacity_animation.setDuration(200)
        self.opacity_animation.setStartValue(1.0)
        self.opacity_animation.setEndValue(0.0)
        
        self.animation_group.addAnimation(height_animation)
        self.animation_group.addAnimation(fixed_height_animation)
        self.animation_group.addAnimation(self.opacity_animation)
        
        self.animation_group.finished.connect(self.on_collapse_finished)
        self.animation_group.start()
        
    def on_collapse_finished(self):
        if self.is_collapsed:
            self.scroll_area.hide()
            self.setFixedHeight(self.collapsed_height)
        self.animation_group.finished.disconnect()
            
    def expand(self):
        self.is_collapsed = False
        self.collapse_btn.setText("−")
        
        self.scroll_area.show()
        self.scroll_area.setWindowOpacity(0.0)
        
        self.animation_group = QParallelAnimationGroup()
        
        height_animation = QPropertyAnimation(self, b"minimumHeight")
        height_animation.setDuration(300)
        height_animation.setEasingCurve(QEasingCurve.InOutCubic)
        height_animation.setStartValue(self.height())
        height_animation.setEndValue(self.normal_height)
        
        fixed_height_animation = QPropertyAnimation(self, b"maximumHeight")
        fixed_height_animation.setDuration(300)
        fixed_height_animation.setEasingCurve(QEasingCurve.InOutCubic)
        fixed_height_animation.setStartValue(self.height())
        fixed_height_animation.setEndValue(self.normal_height)
        
        self.opacity_animation = QPropertyAnimation(self.scroll_area, b"windowOpacity")
        self.opacity_animation.setDuration(200)
        self.opacity_animation.setStartValue(0.0)
        self.opacity_animation.setEndValue(1.0)
        
        self.animation_group.addAnimation(height_animation)
        self.animation_group.addAnimation(fixed_height_animation)
        self.animation_group.addAnimation(self.opacity_animation)
        
        self.animation_group.finished.connect(self.on_expand_finished)
        self.animation_group.start()
        
    def on_expand_finished(self):
        if not self.is_collapsed:
            self.setFixedHeight(self.normal_height)
        self.animation_group.finished.disconnect()

class TaskFloatingWindow(BaseFloatingWindow):
    def __init__(self, parent=None):
        super().__init__("任务", "#ff6b6b", parent)
        
    def should_display_item(self, item):
        return (item.get('type') == 'task' and 
                not item.get('is_completed', False))
                
    def get_style_config(self):
        return StyleConfig.get_task_style()

class AssignmentFloatingWindow(BaseFloatingWindow):
    def __init__(self, parent=None):
        super().__init__("作业", "#4ecdc4", parent)
        
    def should_display_item(self, item):
        return item.get('type') == 'assignment'
        
    def get_style_config(self):
        return StyleConfig.get_assignment_style()

class AnnouncementFloatingWindow(BaseFloatingWindow):
    def __init__(self, parent=None):
        super().__init__("公告", "#45b7d1", parent)
        
    def should_display_item(self, item):
        if item.get('type') != 'announcement':
            return False
            
        due_date_str = item.get('due_date', '')
        is_long_term = item.get('is_long_term', False)
        
        if is_long_term:
            return True
            
        if not due_date_str:
            return True
            
        try:
            due_date = datetime.strptime(due_date_str, "%Y-%m-%d %H:%M:%S")
            return due_date >= datetime.now()
        except ValueError:
            return True
            
    def get_style_config(self):
        return StyleConfig.get_announcement_style()

class DataItemWidget(QFrame):
    def __init__(self, data, data_manager, style_config, parent=None):
        super().__init__(parent)
        self.data = data
        self.data_manager = data_manager
        self.style_config = style_config
        self.setup_ui()
        
    def setup_ui(self):
        self.setFrameStyle(QFrame.StyledPanel)
        self.setStyleSheet("""
            DataItemWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(255,255,255,0.9),
                    stop:1 rgba(250,250,250,0.9));
                border-radius: 6px;
                border: 1px solid #e0e0e0;
                padding: 10px;
            }
            DataItemWidget:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(255,255,255,1),
                    stop:1 rgba(245,245,245,1));
                border: 1px solid #d0d0d0;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        
        title = self.data.get('title', '无标题')
        self.title_label = QLabel(title)
        title_font = QFont()
        title_font.setPointSize(self.style_config.get('title_font_size', 10))
        title_font.setBold(self.style_config.get('title_bold', True))
        self.title_label.setFont(title_font)
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet(f"color: {self.style_config.get('title_color', '#2c3e50')};")
        layout.addWidget(self.title_label)
        
        details = self.get_details_text()
        if details:
            self.details_label = QLabel(details)
            details_font = QFont()
            details_font.setPointSize(self.style_config.get('content_font_size', 8))
            self.details_label.setFont(details_font)
            self.details_label.setWordWrap(True)
            self.details_label.setStyleSheet(f"color: {self.style_config.get('content_color', '#7f8c8d')}; margin-top: 3px;")
            layout.addWidget(self.details_label)
            
        if self.data.get('type') == 'task' and not self.data.get('is_completed', False):
            self.add_action_buttons(layout)
            
        time_text = self.get_time_text()
        if time_text:
            time_label = QLabel(time_text)
            time_font = QFont()
            time_font.setPointSize(self.style_config.get('time_font_size', 7))
            time_label.setFont(time_font)
            time_label.setStyleSheet(f"color: {self.style_config.get('time_color', '#95a5a6')}; margin-top: 6px;")
            layout.addWidget(time_label)
            
    def get_details_text(self):
        item_type = self.data.get('type', '')
        
        if item_type == 'task':
            desc = self.data.get('description', '无描述')
            priority = self.data.get('priority', 1)
            priority_text = {1: "低", 2: "中", 3: "高"}.get(priority, "未知")
            return f"优先级: {priority_text}\n{desc}"
            
        elif item_type == 'assignment':
            subject = self.data.get('subject', '无科目')
            desc = self.data.get('description', '无描述')
            subject_text = f"<span style='color: {self.style_config.get('subject_color', '#7f8c8d')}; font-size: {self.style_config.get('subject_font_size', 8)}px;'>科目: {subject}</span><br>{desc}"
            return subject_text
            
        elif item_type == 'announcement':
            return self.data.get('content', '无内容')
            
        return ""
        
    def get_time_text(self):
        due_date = self.data.get('due_date', '')
        created_at = self.data.get('created_at', '')
        
        if due_date:
            try:
                due_dt = datetime.strptime(due_date, "%Y-%m-%d %H:%M:%S")
                now = datetime.now()
                if due_dt > now:
                    delta = due_dt - now
                    if delta.days > 0:
                        return f"剩余 {delta.days} 天"
                    else:
                        hours = delta.seconds // 3600
                        return f"剩余 {hours} 小时"
                else:
                    return "已过期"
            except:
                pass
                
        if created_at:
            try:
                created_dt = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
                return f"创建于 {created_dt.strftime('%m-%d %H:%M')}"
            except:
                pass
                
        return ""
        
    def add_action_buttons(self, layout):
        btn_layout = QHBoxLayout()
        
        ack_btn = AnimatedButton("确认")
        ack_btn.setFixedHeight(24)
        ack_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3498db, stop:1 #2980b9);
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                padding: 4px 8px;
                font-size: 9px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3cb0fd, stop:1 #3498db);
            }
        """)
        ack_btn.clicked.connect(self.on_acknowledge)
        
        complete_btn = AnimatedButton("完成")
        complete_btn.setFixedHeight(24)
        complete_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2ecc71, stop:1 #27ae60);
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                padding: 4px 8px;
                font-size: 9px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #58d68d, stop:1 #2ecc71);
            }
        """)
        complete_btn.clicked.connect(self.on_complete)
        
        btn_layout.addWidget(ack_btn)
        btn_layout.addWidget(complete_btn)
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
        
    def on_acknowledge(self):
        if self.data_manager:
            self.data_manager.acknowledge_task(self.data['id'])
        
    def on_complete(self):
        if self.data_manager:
            self.data_manager.complete_task(self.data['id'])

# WinUI风格的设置对话框
class SettingsDialog(QDialog):
    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.setup_ui()
        self.load_settings()
        
    def setup_ui(self):
        self.setWindowTitle("白板客户端设置")
        self.setFixedSize(700, 600)
        
        # WinUI风格样式
        self.setStyleSheet("""
            QDialog {
                background-color: #f3f3f3;
                font-family: "Segoe UI", "Microsoft YaHei";
            }
            QTabWidget::pane {
                border: 1px solid #d1d1d1;
                background-color: white;
                border-radius: 4px;
            }
            QTabWidget::tab-bar {
                alignment: left;
            }
            QTabBar::tab {
                background-color: #f3f3f3;
                border: 1px solid #d1d1d1;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                color: #323130;
            }
            QTabBar::tab:selected {
                background-color: white;
                border-bottom-color: white;
                color: #0078d4;
            }
            QTabBar::tab:hover {
                background-color: #f8f8f8;
            }
            QGroupBox {
                font-weight: bold;
                font-size: 12px;
                color: #323130;
                border: 1px solid #d1d1d1;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 12px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #323130;
            }
            QLineEdit, QComboBox, QSpinBox {
                padding: 6px 8px;
                border: 1px solid #d1d1d1;
                border-radius: 4px;
                background: white;
                font-size: 11px;
                color: #323130;
                min-height: 20px;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
                border-color: #0078d4;
            }
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11px;
                min-height: 24px;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
            QPushButton.secondary {
                background-color: #f3f3f3;
                color: #323130;
                border: 1px solid #d1d1d1;
            }
            QPushButton.secondary:hover {
                background-color: #f8f8f8;
            }
            QLabel {
                color: #323130;
                font-size: 11px;
            }
            QCheckBox {
                spacing: 8px;
                font-size: 11px;
                color: #323130;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 2px;
                border: 1px solid #d1d1d1;
                background-color: white;
            }
            QCheckBox::indicator:checked {
                background-color: #0078d4;
                border-color: #0078d4;
                image: url();
            }
            QSlider::groove:horizontal {
                border: 1px solid #d1d1d1;
                height: 4px;
                background: white;
                margin: 2px 0;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #0078d4;
                border: 1px solid #0078d4;
                width: 16px;
                height: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题
        title_label = QLabel("白板客户端设置")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #323130; margin-bottom: 10px;")
        layout.addWidget(title_label)
        
        # 选项卡
        self.tab_widget = QTabWidget()
        
        # 基本设置选项卡
        self.basic_tab = QWidget()
        self.setup_basic_tab()
        self.tab_widget.addTab(self.basic_tab, "基本设置")
        
        # 通知设置选项卡
        self.notify_tab = QWidget()
        self.setup_notify_tab()
        self.tab_widget.addTab(self.notify_tab, "通知设置")
        
        # 样式设置选项卡
        self.style_tab = QWidget()
        self.setup_style_tab()
        self.tab_widget.addTab(self.style_tab, "样式设置")
        
        layout.addWidget(self.tab_widget)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        self.test_btn = QPushButton("测试连接")
        self.test_btn.setProperty("class", "secondary")
        self.test_btn.clicked.connect(self.test_connection)
        
        self.save_btn = QPushButton("保存")
        self.save_btn.clicked.connect(self.save_settings)
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setProperty("class", "secondary")
        self.cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(self.test_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
        
    def setup_basic_tab(self):
        layout = QVBoxLayout(self.basic_tab)
        layout.setSpacing(15)
        
        # 服务器配置组
        server_group = QGroupBox("服务器配置")
        server_layout = QFormLayout(server_group)
        server_layout.setLabelAlignment(Qt.AlignRight)
        
        server_info_label = QLabel(f"服务器地址: {SERVER}")
        server_info_label.setStyleSheet("font-weight: bold; color: #605e5c; background: #f8f8f8; padding: 6px; border-radius: 4px;")
        
        self.board_id_edit = QLineEdit()
        self.board_id_edit.setPlaceholderText("请输入白板ID")
        
        self.secret_key_edit = QLineEdit()
        self.secret_key_edit.setEchoMode(QLineEdit.Password)
        self.secret_key_edit.setPlaceholderText("请输入白板密钥")
        
        self.dlass_edit = QLineEdit()
        self.dlass_edit.setPlaceholderText("输入dlass://链接快速配置")
        parse_btn = QPushButton("解析")
        parse_btn.setProperty("class", "secondary")
        parse_btn.clicked.connect(self.parse_dlass_link)
        
        dlass_layout = QHBoxLayout()
        dlass_layout.addWidget(self.dlass_edit)
        dlass_layout.addWidget(parse_btn)
        
        server_layout.addRow("服务器:", server_info_label)
        server_layout.addRow("白板ID:", self.board_id_edit)
        server_layout.addRow("白板密钥:", self.secret_key_edit)
        server_layout.addRow("快速配置:", dlass_layout)
        
        layout.addWidget(server_group)
        
        # 窗口设置组
        window_group = QGroupBox("窗口设置")
        window_layout = QFormLayout(window_group)
        
        self.window_level_combo = QComboBox()
        self.window_level_combo.addItems(["普通窗口", "始终置顶", "桌面级"])
        
        opacity_layout = QHBoxLayout()
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(30, 100)
        self.opacity_slider.setTickPosition(QSlider.TicksBelow)
        self.opacity_slider.setTickInterval(10)
        self.opacity_label = QLabel("90%")
        opacity_layout.addWidget(self.opacity_slider)
        opacity_layout.addWidget(self.opacity_label)
        self.opacity_slider.valueChanged.connect(self.on_opacity_changed)
        
        window_layout.addRow("窗口层级:", self.window_level_combo)
        window_layout.addRow("窗口不透明度:", opacity_layout)
        
        layout.addWidget(window_group)
        
        layout.addStretch()
        
    def setup_notify_tab(self):
        layout = QVBoxLayout(self.notify_tab)
        layout.setSpacing(15)
        
        # 基本通知设置
        basic_notify_group = QGroupBox("基本通知设置")
        basic_notify_layout = QVBoxLayout(basic_notify_group)
        
        self.notify_new = QCheckBox("新消息通知")
        self.notify_new.setChecked(True)
        
        self.notify_task = QCheckBox("任务更新通知")
        self.notify_task.setChecked(True)
        
        self.notify_sound = QCheckBox("提示音")
        self.notify_sound.setChecked(True)
        
        basic_notify_layout.addWidget(self.notify_new)
        basic_notify_layout.addWidget(self.notify_task)
        basic_notify_layout.addWidget(self.notify_sound)
        
        layout.addWidget(basic_notify_group)
        
        # 高级通知设置
        advanced_notify_group = QGroupBox("高级通知设置")
        advanced_notify_layout = QVBoxLayout(advanced_notify_group)
        
        self.notify_assignment = QCheckBox("作业发布提醒")
        self.notify_assignment.setChecked(True)
        
        self.notify_announcement = QCheckBox("公告发布提醒")
        self.notify_announcement.setChecked(True)
        
        self.system_level_notify = QCheckBox("启用系统级提醒 (action_id=2)")
        self.system_level_notify.setChecked(True)
        
        system_notify_desc = QLabel("当收到action_id为2的消息时，会触发系统级提醒（类似\"还有一分钟注销您的登录\"级别的提醒）")
        system_notify_desc.setWordWrap(True)
        system_notify_desc.setStyleSheet("color: #605e5c; font-size: 10px; margin-top: 5px;")
        
        advanced_notify_layout.addWidget(self.notify_assignment)
        advanced_notify_layout.addWidget(self.notify_announcement)
        advanced_notify_layout.addWidget(self.system_level_notify)
        advanced_notify_layout.addWidget(system_notify_desc)
        
        layout.addWidget(advanced_notify_group)
        
        layout.addStretch()
        
    def setup_style_tab(self):
        layout = QVBoxLayout(self.style_tab)
        layout.setSpacing(15)
        
        # 任务窗口样式
        task_style_group = QGroupBox("任务窗口样式")
        task_style_layout = QGridLayout(task_style_group)
        
        task_style_layout.addWidget(QLabel("标题字体大小:"), 0, 0)
        self.task_title_size = QSpinBox()
        self.task_title_size.setRange(8, 20)
        task_style_layout.addWidget(self.task_title_size, 0, 1)
        
        task_style_layout.addWidget(QLabel("标题颜色:"), 0, 2)
        self.task_title_color = QLineEdit("#2c3e50")
        task_style_layout.addWidget(self.task_title_color, 0, 3)
        
        task_style_layout.addWidget(QLabel("内容字体大小:"), 1, 0)
        self.task_content_size = QSpinBox()
        self.task_content_size.setRange(6, 16)
        task_style_layout.addWidget(self.task_content_size, 1, 1)
        
        task_style_layout.addWidget(QLabel("内容颜色:"), 1, 2)
        self.task_content_color = QLineEdit("#7f8c8d")
        task_style_layout.addWidget(self.task_content_color, 1, 3)
        
        self.task_title_bold = QCheckBox("标题加粗")
        self.task_title_bold.setChecked(True)
        task_style_layout.addWidget(self.task_title_bold, 2, 0, 1, 2)
        
        layout.addWidget(task_style_group)
        
        # 作业窗口样式
        assignment_style_group = QGroupBox("作业窗口样式")
        assignment_style_layout = QGridLayout(assignment_style_group)
        
        assignment_style_layout.addWidget(QLabel("标题字体大小:"), 0, 0)
        self.assignment_title_size = QSpinBox()
        self.assignment_title_size.setRange(8, 20)
        assignment_style_layout.addWidget(self.assignment_title_size, 0, 1)
        
        assignment_style_layout.addWidget(QLabel("标题颜色:"), 0, 2)
        self.assignment_title_color = QLineEdit("#2c3e50")
        assignment_style_layout.addWidget(self.assignment_title_color, 0, 3)
        
        assignment_style_layout.addWidget(QLabel("科目字体大小:"), 1, 0)
        self.assignment_subject_size = QSpinBox()
        self.assignment_subject_size.setRange(6, 16)
        assignment_style_layout.addWidget(self.assignment_subject_size, 1, 1)
        
        assignment_style_layout.addWidget(QLabel("科目颜色:"), 1, 2)
        self.assignment_subject_color = QLineEdit("#7f8c8d")
        assignment_style_layout.addWidget(self.assignment_subject_color, 1, 3)
        
        assignment_style_layout.addWidget(QLabel("内容字体大小:"), 2, 0)
        self.assignment_content_size = QSpinBox()
        self.assignment_content_size.setRange(6, 16)
        assignment_style_layout.addWidget(self.assignment_content_size, 2, 1)
        
        assignment_style_layout.addWidget(QLabel("内容颜色:"), 2, 2)
        self.assignment_content_color = QLineEdit("#7f8c8d")
        assignment_style_layout.addWidget(self.assignment_content_color, 2, 3)
        
        self.assignment_title_bold = QCheckBox("标题加粗")
        self.assignment_title_bold.setChecked(True)
        assignment_style_layout.addWidget(self.assignment_title_bold, 3, 0, 1, 2)
        
        layout.addWidget(assignment_style_group)
        
        # 公告窗口样式
        announcement_style_group = QGroupBox("公告窗口样式")
        announcement_style_layout = QGridLayout(announcement_style_group)
        
        announcement_style_layout.addWidget(QLabel("标题字体大小:"), 0, 0)
        self.announcement_title_size = QSpinBox()
        self.announcement_title_size.setRange(8, 20)
        announcement_style_layout.addWidget(self.announcement_title_size, 0, 1)
        
        announcement_style_layout.addWidget(QLabel("标题颜色:"), 0, 2)
        self.announcement_title_color = QLineEdit("#2c3e50")
        announcement_style_layout.addWidget(self.announcement_title_color, 0, 3)
        
        announcement_style_layout.addWidget(QLabel("内容字体大小:"), 1, 0)
        self.announcement_content_size = QSpinBox()
        self.announcement_content_size.setRange(6, 16)
        announcement_style_layout.addWidget(self.announcement_content_size, 1, 1)
        
        announcement_style_layout.addWidget(QLabel("内容颜色:"), 1, 2)
        self.announcement_content_color = QLineEdit("#7f8c8d")
        announcement_style_layout.addWidget(self.announcement_content_color, 1, 3)
        
        self.announcement_title_bold = QCheckBox("标题加粗")
        self.announcement_title_bold.setChecked(True)
        announcement_style_layout.addWidget(self.announcement_title_bold, 2, 0, 1, 2)
        
        layout.addWidget(announcement_style_group)
        
        layout.addStretch()
        
    def on_opacity_changed(self, value):
        self.opacity_label.setText(f"{value}%")
        
    def parse_dlass_link(self):
        link = self.dlass_edit.text().strip()
        if not link:
            return
            
        pattern = r'^dlass://config/([^/]+)/([^/]+)$'
        match = re.match(pattern, link)
        
        if match:
            board_id = match.group(1)
            secret_key = match.group(2)
            
            self.board_id_edit.setText(board_id)
            self.secret_key_edit.setText(secret_key)
            
            QMessageBox.information(self, "成功", "DLASS链接解析成功！")
        else:
            QMessageBox.warning(self, "错误", "无效的DLASS链接格式")
        
    def load_settings(self):
        settings = QSettings("WhiteboardClient", "Config")
        self.board_id_edit.setText(settings.value("board_id", ""))
        self.secret_key_edit.setText(settings.value("secret_key", ""))
        self.window_level_combo.setCurrentIndex(settings.value("window_level", 0, type=int))
        self.opacity_slider.setValue(settings.value("opacity", 90, type=int))
        self.notify_new.setChecked(settings.value("notify_new", True, type=bool))
        self.notify_task.setChecked(settings.value("notify_task", True, type=bool))
        self.notify_sound.setChecked(settings.value("notify_sound", True, type=bool))
        self.notify_assignment.setChecked(settings.value("notify_assignment", True, type=bool))
        self.notify_announcement.setChecked(settings.value("notify_announcement", True, type=bool))
        self.system_level_notify.setChecked(settings.value("system_level_notify", True, type=bool))
        
        # 加载样式设置
        style_settings = QSettings("WhiteboardClient", "Styles")
        self.task_title_size.setValue(style_settings.value("task_title_font_size", 10, type=int))
        self.task_title_color.setText(style_settings.value("task_title_color", "#2c3e50"))
        self.task_content_size.setValue(style_settings.value("task_content_font_size", 8, type=int))
        self.task_content_color.setText(style_settings.value("task_content_color", "#7f8c8d"))
        self.task_title_bold.setChecked(style_settings.value("task_title_bold", True, type=bool))
        
        self.assignment_title_size.setValue(style_settings.value("assignment_title_font_size", 10, type=int))
        self.assignment_title_color.setText(style_settings.value("assignment_title_color", "#2c3e50"))
        self.assignment_subject_size.setValue(style_settings.value("assignment_subject_font_size", 8, type=int))
        self.assignment_subject_color.setText(style_settings.value("assignment_subject_color", "#7f8c8d"))
        self.assignment_content_size.setValue(style_settings.value("assignment_content_font_size", 8, type=int))
        self.assignment_content_color.setText(style_settings.value("assignment_content_color", "#7f8c8d"))
        self.assignment_title_bold.setChecked(style_settings.value("assignment_title_bold", True, type=bool))
        
        self.announcement_title_size.setValue(style_settings.value("announcement_title_font_size", 10, type=int))
        self.announcement_title_color.setText(style_settings.value("announcement_title_color", "#2c3e50"))
        self.announcement_content_size.setValue(style_settings.value("announcement_content_font_size", 8, type=int))
        self.announcement_content_color.setText(style_settings.value("announcement_content_color", "#7f8c8d"))
        self.announcement_title_bold.setChecked(style_settings.value("announcement_title_bold", True, type=bool))
        
    def save_settings(self):
        board_id = self.board_id_edit.text().strip()
        secret_key = self.secret_key_edit.text().strip()
        
        if not board_id or not secret_key:
            QMessageBox.warning(self, "输入错误", "请填写白板ID和密钥")
            return
            
        settings = QSettings("WhiteboardClient", "Config")
        settings.setValue("board_id", board_id)
        settings.setValue("secret_key", secret_key)
        settings.setValue("window_level", self.window_level_combo.currentIndex())
        settings.setValue("opacity", self.opacity_slider.value())
        settings.setValue("notify_new", self.notify_new.isChecked())
        settings.setValue("notify_task", self.notify_task.isChecked())
        settings.setValue("notify_sound", self.notify_sound.isChecked())
        settings.setValue("notify_assignment", self.notify_assignment.isChecked())
        settings.setValue("notify_announcement", self.notify_announcement.isChecked())
        settings.setValue("system_level_notify", self.system_level_notify.isChecked())
        
        # 保存样式设置
        style_settings = QSettings("WhiteboardClient", "Styles")
        style_settings.setValue("task_title_font_size", self.task_title_size.value())
        style_settings.setValue("task_title_color", self.task_title_color.text())
        style_settings.setValue("task_content_font_size", self.task_content_size.value())
        style_settings.setValue("task_content_color", self.task_content_color.text())
        style_settings.setValue("task_title_bold", self.task_title_bold.isChecked())
        
        style_settings.setValue("assignment_title_font_size", self.assignment_title_size.value())
        style_settings.setValue("assignment_title_color", self.assignment_title_color.text())
        style_settings.setValue("assignment_subject_font_size", self.assignment_subject_size.value())
        style_settings.setValue("assignment_subject_color", self.assignment_subject_color.text())
        style_settings.setValue("assignment_content_font_size", self.assignment_content_size.value())
        style_settings.setValue("assignment_content_color", self.assignment_content_color.text())
        style_settings.setValue("assignment_title_bold", self.assignment_title_bold.isChecked())
        
        style_settings.setValue("announcement_title_font_size", self.announcement_title_size.value())
        style_settings.setValue("announcement_title_color", self.announcement_title_color.text())
        style_settings.setValue("announcement_content_font_size", self.announcement_content_size.value())
        style_settings.setValue("announcement_content_color", self.announcement_content_color.text())
        style_settings.setValue("announcement_title_bold", self.announcement_title_bold.isChecked())
        
        self.api_client.setup(SERVER, board_id, secret_key)
        QMessageBox.information(self, "成功", "设置已保存")
        self.accept()
        
    def test_connection(self):
        board_id = self.board_id_edit.text().strip()
        secret_key = self.secret_key_edit.text().strip()
        
        if not board_id or not secret_key:
            QMessageBox.warning(self, "输入错误", "请填写白板ID和密钥")
            return
            
        try:
            test_client = WhiteboardClientAPI()
            test_client.setup(SERVER, board_id, secret_key)
            result = test_client.send_heartbeat()
            
            if result.get("success"):
                QMessageBox.information(self, "连接成功", "服务器连接测试成功")
            else:
                QMessageBox.warning(self, "连接失败", f"服务器连接测试失败: {result.get('error', '未知错误')}")
        except Exception as e:
            QMessageBox.critical(self, "连接错误", f"连接过程中发生错误: {str(e)}")

class WindowManager:
    def __init__(self):
        self.data_manager = DataManager()
        self.windows = {}
        self.tray_icon = None
        
        self.setup_windows()
        self.setup_tray()
        self.connect_signals()
        self.load_settings()
        
    def setup_windows(self):
        self.windows['task'] = TaskFloatingWindow()
        self.windows['assignment'] = AssignmentFloatingWindow()
        self.windows['announcement'] = AnnouncementFloatingWindow()
        
        for window in self.windows.values():
            window.set_data_manager(self.data_manager)
            
    def setup_tray(self):
        self.tray_icon = QSystemTrayIcon()
        self.tray_icon.setIcon(self.create_tray_icon())
        
        tray_menu = QMenu()
        
        window_menu = QMenu("窗口控制", tray_menu)
        
        show_all_action = QAction("显示所有窗口", window_menu)
        show_all_action.triggered.connect(self.show_all_windows)
        
        hide_all_action = QAction("隐藏所有窗口", window_menu)
        hide_all_action.triggered.connect(self.hide_all_windows)
        
        collapse_all_action = QAction("收起所有窗口", window_menu)
        collapse_all_action.triggered.connect(self.collapse_all_windows)
        
        expand_all_action = QAction("展开所有窗口", window_menu)
        expand_all_action.triggered.connect(self.expand_all_windows)
        
        window_menu.addAction(show_all_action)
        window_menu.addAction(hide_all_action)
        window_menu.addSeparator()
        window_menu.addAction(collapse_all_action)
        window_menu.addAction(expand_all_action)
        window_menu.addSeparator()
        
        for name, window in self.windows.items():
            action = QAction(f"显示{window.title}窗口", window_menu)
            action.triggered.connect(lambda checked, w=window: w.show())
            window_menu.addAction(action)
            
        tray_menu.addMenu(window_menu)
        
        settings_action = QAction("设置", tray_menu)
        settings_action.triggered.connect(self.show_settings)
        tray_menu.addAction(settings_action)
        
        refresh_action = QAction("刷新数据", tray_menu)
        refresh_action.triggered.connect(self.data_manager.manual_refresh)
        tray_menu.addAction(refresh_action)
        
        tray_menu.addSeparator()
        
        quit_action = QAction("退出", tray_menu)
        quit_action.triggered.connect(self.quit_application)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()
        
    def create_tray_icon(self):
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        gradient = QLinearGradient(0, 0, 64, 64)
        gradient.setColorAt(0, QColor(102, 126, 234))
        gradient.setColorAt(1, QColor(118, 75, 162))
        
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(4, 4, 56, 56)
        
        painter.setPen(QPen(Qt.white))
        painter.setFont(QFont("Arial", 24, QFont.Bold))
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "W")
        
        painter.end()
        return QIcon(pixmap)
        
    def connect_signals(self):
        self.data_manager.data_updated.connect(self.on_data_updated)
        self.data_manager.error_occurred.connect(self.show_error)
        self.data_manager.system_notification.connect(self.show_system_notification)
        self.data_manager.socketio_status.connect(self.on_socketio_status)
        print("所有信号已连接")
        
    def show_system_notification(self, title, content, level):
        print(f"触发系统通知: {title} - {content}, 级别: {level}")
        
        settings = QSettings("WhiteboardClient", "Config")
        
        # 检查是否启用了系统级通知
        system_level_enabled = settings.value("system_level_notify", True, type=bool)
        
        # 根据级别决定是否显示通知
        if level == 3 and not system_level_enabled:
            print("系统级通知已禁用")
            return
            
        # 检查基本通知设置
        notify_enabled = settings.value("notify_new", True, type=bool)
        
        print(f"通知设置状态: {notify_enabled}")
        
        if notify_enabled:
            if level == 3:  # 系统级警告 - 使用 Windows 弹窗
                self.show_windows_message_box(title, content)
                print(f"Windows 弹窗已发送，级别: {level}")
            else:  # 普通通知 - 使用系统托盘通知
                # 根据级别设置不同的图标和持续时间
                if level == 2:  # 警告
                    icon = QSystemTrayIcon.Warning
                    duration = 7000  # 7秒
                else:  # 普通信息
                    icon = QSystemTrayIcon.Information
                    duration = 5000  # 5秒
                    
                self.tray_icon.showMessage(
                    title, 
                    content, 
                    icon, 
                    duration
                )
                print(f"系统托盘通知已发送，级别: {level}")
    
    def show_windows_message_box(self, title, content):
        """
        显示 Windows 底层消息弹窗
        类似 shutdown /t 10 的那种强制弹窗
        """
        try:
            # 使用 MB_SYSTEMMODAL | MB_ICONWARNING | MB_OK 来创建系统级模态对话框
            # MB_SYSTEMMODAL: 系统模态，会置顶在所有窗口之上
            # MB_ICONWARNING: 警告图标
            # MB_OK: 确定按钮
            
            result = ctypes.windll.user32.MessageBoxW(
                0,  # 没有父窗口
                f"{content}\n\n此消息需要您确认。",  # 消息内容
                f"系统警告 - {title}",  # 标题
                0x00001000 | 0x00000030 | 0x00000000  # MB_SYSTEMMODAL | MB_ICONWARNING | MB_OK
            )
            
            # 可选：记录用户响应
            if result == 1:  # IDOK
                print("用户确认了系统警告")
            else:
                print(f"系统警告返回代码: {result}")
                
        except Exception as e:
            print(f"显示 Windows 弹窗失败: {e}")
            # 失败时回退到系统托盘通知
            self.tray_icon.showMessage(
                title, 
                content, 
                QSystemTrayIcon.Critical, 
                10000
            )
            
    def on_socketio_status(self, connected, message):
        status = "已连接" if connected else "未连接"
        print(f"Socket.IO状态: {status} - {message}")
        
        if connected:
            self.tray_icon.setToolTip(f"白板客户端 - Socket.IO已连接")
        else:
            self.tray_icon.setToolTip(f"白板客户端 - Socket.IO未连接: {message}")
            
    def on_data_updated(self, data):
        for window in self.windows.values():
            window.update_data(data)
            
    def show_error(self, error_msg):
        self.tray_icon.showMessage("错误", error_msg, QSystemTrayIcon.Critical, 3000)
        
    def load_settings(self):
        settings = QSettings("WhiteboardClient", "Config")
        board_id = settings.value("board_id", "")
        secret_key = settings.value("secret_key", "")
        window_level = settings.value("window_level", 0, type=int)
        opacity = settings.value("opacity", 90, type=int)
        
        for window in self.windows.values():
            if window_level == 1:
                window.setWindowFlags(window.windowFlags() | Qt.WindowStaysOnTopHint)
            elif window_level == 2:
                window.setWindowFlags(window.windowFlags() | Qt.WindowStaysOnBottomHint)
                
            window.setWindowOpacity(opacity / 100.0)
            
        if board_id and secret_key:
            self.data_manager.setup(SERVER, board_id, secret_key)
            self.data_manager.start_data_fetching()
            self.data_manager.start_heartbeat()
            self.data_manager.start_socketio()
            print("所有服务已启动")
            
        self.arrange_windows()
        
    def arrange_windows(self):
        screen_geometry = QGuiApplication.primaryScreen().geometry()
        
        window_width = 300
        window_height = 400
        spacing = 10
        total_width = (window_width * 3) + (spacing * 2)
        
        start_x = (screen_geometry.width() - total_width) // 2
        y_pos = 50
        
        positions = {
            'task': (start_x, y_pos),
            'assignment': (start_x + window_width + spacing, y_pos),
            'announcement': (start_x + (window_width + spacing) * 2, y_pos)
        }
        
        for name, window in self.windows.items():
            pos = positions.get(name, (0, 0))
            window.move(pos[0], pos[1])
            
    def show_all_windows(self):
        for window in self.windows.values():
            window.show()
            window.raise_()
            
    def hide_all_windows(self):
        for window in self.windows.values():
            window.hide()
            
    def collapse_all_windows(self):
        for window in self.windows.values():
            if not window.is_collapsed:
                window.collapse()
                
    def expand_all_windows(self):
        for window in self.windows.values():
            if window.is_collapsed:
                window.expand()
            
    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            any_visible = any(window.isVisible() for window in self.windows.values())
            if any_visible:
                self.hide_all_windows()
            else:
                self.show_all_windows()
                
    def show_settings(self):
        dialog = SettingsDialog(self.data_manager.api_client, None)
        if dialog.exec() == QDialog.Accepted:
            self.load_settings()
            self.data_manager.manual_refresh()
            
            if self.data_manager.socketio_thread:
                self.data_manager.socketio_thread.stop()
                self.data_manager.start_socketio()
                
    def quit_application(self):
        self.data_manager.stop()
        QApplication.quit()
    def __init__(self):
        self.data_manager = DataManager()
        self.windows = {}
        self.tray_icon = None
        
        self.setup_windows()
        self.setup_tray()
        self.connect_signals()
        self.load_settings()
        
    def setup_windows(self):
        self.windows['task'] = TaskFloatingWindow()
        self.windows['assignment'] = AssignmentFloatingWindow()
        self.windows['announcement'] = AnnouncementFloatingWindow()
        
        for window in self.windows.values():
            window.set_data_manager(self.data_manager)
            
    def setup_tray(self):
        self.tray_icon = QSystemTrayIcon()
        self.tray_icon.setIcon(self.create_tray_icon())
        
        tray_menu = QMenu()
        
        window_menu = QMenu("窗口控制", tray_menu)
        
        show_all_action = QAction("显示所有窗口", window_menu)
        show_all_action.triggered.connect(self.show_all_windows)
        
        hide_all_action = QAction("隐藏所有窗口", window_menu)
        hide_all_action.triggered.connect(self.hide_all_windows)
        
        collapse_all_action = QAction("收起所有窗口", window_menu)
        collapse_all_action.triggered.connect(self.collapse_all_windows)
        
        expand_all_action = QAction("展开所有窗口", window_menu)
        expand_all_action.triggered.connect(self.expand_all_windows)
        
        window_menu.addAction(show_all_action)
        window_menu.addAction(hide_all_action)
        window_menu.addSeparator()
        window_menu.addAction(collapse_all_action)
        window_menu.addAction(expand_all_action)
        window_menu.addSeparator()
        
        for name, window in self.windows.items():
            action = QAction(f"显示{window.title}窗口", window_menu)
            action.triggered.connect(lambda checked, w=window: w.show())
            window_menu.addAction(action)
            
        tray_menu.addMenu(window_menu)
        
        settings_action = QAction("设置", tray_menu)
        settings_action.triggered.connect(self.show_settings)
        tray_menu.addAction(settings_action)
        
        refresh_action = QAction("刷新数据", tray_menu)
        refresh_action.triggered.connect(self.data_manager.manual_refresh)
        tray_menu.addAction(refresh_action)
        
        tray_menu.addSeparator()
        
        quit_action = QAction("退出", tray_menu)
        quit_action.triggered.connect(self.quit_application)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()
        
    def create_tray_icon(self):
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        gradient = QLinearGradient(0, 0, 64, 64)
        gradient.setColorAt(0, QColor(102, 126, 234))
        gradient.setColorAt(1, QColor(118, 75, 162))
        
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(4, 4, 56, 56)
        
        painter.setPen(QPen(Qt.white))
        painter.setFont(QFont("Arial", 24, QFont.Bold))
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "W")
        
        painter.end()
        return QIcon(pixmap)
        
    def connect_signals(self):
        self.data_manager.data_updated.connect(self.on_data_updated)
        self.data_manager.error_occurred.connect(self.show_error)
        self.data_manager.system_notification.connect(self.show_system_notification)
        self.data_manager.socketio_status.connect(self.on_socketio_status)
        print("所有信号已连接")
        
    def show_system_notification(self, title, content, level):
        print(f"触发系统通知: {title} - {content}, 级别: {level}")
        
        settings = QSettings("WhiteboardClient", "Config")
        
        # 检查是否启用了系统级通知
        system_level_enabled = settings.value("system_level_notify", True, type=bool)
        
        # 根据级别决定是否显示通知
        if level == 3 and not system_level_enabled:
            print("系统级通知已禁用")
            return
            
        # 检查基本通知设置
        notify_enabled = settings.value("notify_new", True, type=bool)
        
        print(f"通知设置状态: {notify_enabled}")
        
        if notify_enabled:
            # 根据级别设置不同的图标和持续时间
            if level == 3:  # 系统级警告
                icon = QSystemTrayIcon.Critical
                duration = 10000  # 10秒
            elif level == 2:  # 警告
                icon = QSystemTrayIcon.Warning
                duration = 7000  # 7秒
            else:  # 普通信息
                icon = QSystemTrayIcon.Information
                duration = 5000  # 5秒
                
            self.tray_icon.showMessage(
                title, 
                content, 
                icon, 
                duration
            )
            print(f"系统通知已发送，级别: {level}")
            
    def on_socketio_status(self, connected, message):
        status = "已连接" if connected else "未连接"
        print(f"Socket.IO状态: {status} - {message}")
        
        if connected:
            self.tray_icon.setToolTip(f"白板客户端 - Socket.IO已连接")
        else:
            self.tray_icon.setToolTip(f"白板客户端 - Socket.IO未连接: {message}")
            
    def on_data_updated(self, data):
        for window in self.windows.values():
            window.update_data(data)
            
    def show_error(self, error_msg):
        self.tray_icon.showMessage("错误", error_msg, QSystemTrayIcon.Critical, 3000)
        
    def load_settings(self):
        settings = QSettings("WhiteboardClient", "Config")
        board_id = settings.value("board_id", "")
        secret_key = settings.value("secret_key", "")
        window_level = settings.value("window_level", 0, type=int)
        opacity = settings.value("opacity", 90, type=int)
        
        for window in self.windows.values():
            if window_level == 1:
                window.setWindowFlags(window.windowFlags() | Qt.WindowStaysOnTopHint)
            elif window_level == 2:
                window.setWindowFlags(window.windowFlags() | Qt.WindowStaysOnBottomHint)
                
            window.setWindowOpacity(opacity / 100.0)
            
        if board_id and secret_key:
            self.data_manager.setup(SERVER, board_id, secret_key)
            self.data_manager.start_data_fetching()
            self.data_manager.start_heartbeat()
            self.data_manager.start_socketio()
            print("所有服务已启动")
            
        self.arrange_windows()
        
    def arrange_windows(self):
        screen_geometry = QGuiApplication.primaryScreen().geometry()
        
        window_width = 300
        window_height = 400
        spacing = 10
        total_width = (window_width * 3) + (spacing * 2)
        
        start_x = (screen_geometry.width() - total_width) // 2
        y_pos = 50
        
        positions = {
            'task': (start_x, y_pos),
            'assignment': (start_x + window_width + spacing, y_pos),
            'announcement': (start_x + (window_width + spacing) * 2, y_pos)
        }
        
        for name, window in self.windows.items():
            pos = positions.get(name, (0, 0))
            window.move(pos[0], pos[1])
            
    def show_all_windows(self):
        for window in self.windows.values():
            window.show()
            window.raise_()
            
    def hide_all_windows(self):
        for window in self.windows.values():
            window.hide()
            
    def collapse_all_windows(self):
        for window in self.windows.values():
            if not window.is_collapsed:
                window.collapse()
                
    def expand_all_windows(self):
        for window in self.windows.values():
            if window.is_collapsed:
                window.expand()
            
    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            any_visible = any(window.isVisible() for window in self.windows.values())
            if any_visible:
                self.hide_all_windows()
            else:
                self.show_all_windows()
                
    def show_settings(self):
        dialog = SettingsDialog(self.data_manager.api_client, None)
        if dialog.exec() == QDialog.Accepted:
            self.load_settings()
            self.data_manager.manual_refresh()
            
            if self.data_manager.socketio_thread:
                self.data_manager.socketio_thread.stop()
                self.data_manager.start_socketio()
                
    def quit_application(self):
        self.data_manager.stop()
        QApplication.quit()

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    app.setStyle("Fusion")
    
    window_manager = WindowManager()
    window_manager.show_all_windows()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()