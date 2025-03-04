import sys
import json
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QFrame
from PyQt5.QtCore import Qt, QTimer, QDateTime, QMargins, QThread, pyqtSignal
from PyQt5.QtGui import QFont
import requests


APIKEY = ""
MODELNAME = "Qwen/Qwen2.5-7B-Instruct"

class MessageBubble(QWidget):
    def __init__(self, text, is_user=False):
        super().__init__()
        self.text = text
        self.is_user = is_user
        
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        timestamp = QDateTime.currentDateTime().toString("HH:mm")
        time_label = QLabel(timestamp)
        time_label.setFont(QFont("Segoe UI", 8))
        time_label.setStyleSheet("color: #999; padding: 2px 6px;")
        
        content_frame = QFrame()
        content_frame.setContentsMargins(10, 8, 10, 8)
        content_layout = QVBoxLayout()
        content_layout.setSpacing(4)
        
        self.message_label = QLabel(text)
        self.message_label.setFont(QFont("Segoe UI", 12))
        self.message_label.setWordWrap(True)
        self.message_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        
        content_layout.addWidget(self.message_label)
        content_frame.setLayout(content_layout)
        
        if self.is_user:
            content_frame.setStyleSheet("""
                QFrame {
                    background: #8a2be2;
                    border-radius: 12px;
                    color: white;
                }
            """)
            time_label.setAlignment(Qt.AlignRight)
            layout.addStretch(1)
            layout.addWidget(time_label)
            layout.addWidget(content_frame)
            layout.setAlignment(Qt.AlignRight)
        else:
            content_frame.setStyleSheet("""
                QFrame {
                    background: white;
                    border-radius: 12px;
                    color: black;
                }
            """)
            time_label.setAlignment(Qt.AlignLeft)
            layout.addWidget(content_frame)
            layout.addWidget(time_label)
            layout.addStretch(1)
            layout.setAlignment(Qt.AlignLeft)
        
        self.setLayout(layout)

class ApiWorker(QThread):
    content_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()
    
    def __init__(self, messages):
        super().__init__()
        self.messages = messages
    
    def run(self):
        API_URL = "https://api.siliconflow.cn/v1/chat/completions"
        HEADERS = {
            "Authorization": f"Bearer {APIKEY}",  # 替换为实际API密钥
            "Content-Type": "application/json"
        }
        DATA = {
            "model": {MODELNAME},
            "messages": self.messages,
            "stream": True
        }
        
        try:
            response = requests.post(API_URL, headers=HEADERS, json=DATA, stream=True)
            response.raise_for_status()
            
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8').strip()
                    if decoded_line.startswith("data:"):
                        json_str = decoded_line[5:]
                        try:
                            chunk = json.loads(json_str)
                            if "choices" in chunk:
                                content = chunk["choices"][0]["delta"].get("content", "")
                                self.content_signal.emit(content)
                        except json.JSONDecodeError:
                            continue
            self.finished_signal.emit()
        except Exception as e:
            self.content_signal.emit(f"API调用失败：{str(e)}")
            self.finished_signal.emit()

class ChatWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("UniLLM")
        self.setGeometry(100, 100, 400, 400)
        self.is_requesting = False
        self.messages = []
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.message_container = QWidget()
        self.message_layout = QVBoxLayout()
        self.message_layout.setAlignment(Qt.AlignTop)
        self.message_layout.setSpacing(8)
        self.message_layout.setContentsMargins(10, 10, 10, 10)
        self.message_container.setLayout(self.message_layout)
        
        self.scroll_area.setWidget(self.message_container)
        
        input_frame = QFrame()
        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(10, 5, 10, 5)
        
        self.input_line = QLineEdit()
        self.input_line.setFont(QFont("Segoe UI", 12))
        self.input_line.setPlaceholderText("输入消息...")
        self.input_line.setFixedHeight(40)
        self.input_line.setMaxLength(1000)  # 设置最大输入长度
        self.input_line.setStyleSheet("""
            QLineEdit {
                background: white;
                border: 1px solid #ddd;
                border-radius: 20px;
                padding: 0 15px;
            }
        """)
        
        send_button = QPushButton("发送")
        send_button.setFont(QFont("Segoe UI", 12))
        send_button.setFixedSize(80, 40)
        send_button.setStyleSheet("""
            QPushButton {
                background: #6200ea;
                color: white;
                border-radius: 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #3700b3;
            }
        """)
        
        input_layout.addWidget(self.input_line)
        input_layout.addWidget(send_button)
        input_frame.setLayout(input_layout)
        input_frame.setStyleSheet("background: #f5f5f5;")
        
        main_layout.addWidget(self.scroll_area)
        main_layout.addWidget(input_frame)
        main_widget.setLayout(main_layout)
        
        send_button.clicked.connect(self.send_message)
        self.input_line.returnPressed.connect(self.send_message)

    def send_message(self):
        if self.is_requesting:
            return
            
        text = self.input_line.text().strip()
        if not text:
            return
        
        self.is_requesting = True
        user_bubble = MessageBubble(text, is_user=True)
        self.message_layout.addWidget(user_bubble)
        self.messages.append({"role": "user", "content": text})
        self.input_line.clear()
        self.scrollToBottom()
        
        self.current_ai_content = ""
        self.ai_bubble = MessageBubble("", is_user=False)
        self.message_layout.addWidget(self.ai_bubble)
        
        self.worker = ApiWorker(self.messages.copy())
        self.worker.content_signal.connect(self.update_ai_response)
        self.worker.finished_signal.connect(self.finalize_response)
        self.worker.start()

    def update_ai_response(self, content):
        self.current_ai_content += content
        self.ai_bubble.message_label.setText(self.current_ai_content)
        self.scrollToBottom()

    def finalize_response(self):
        self.messages.append({"role": "assistant", "content": self.current_ai_content})
        self.is_requesting = False
        self.ai_bubble = None

    def scrollToBottom(self):
        self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        )

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ChatWindow()
    window.show()
    sys.exit(app.exec_())