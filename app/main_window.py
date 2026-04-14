from PyQt6.QtWidgets import QMainWindow, QLabel, QVBoxLayout, QWidget


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GAI Usage Viewer")
        self.setMinimumSize(800, 600)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(QLabel("GAI Usage Viewer - 初始化完成"))
        self.setCentralWidget(central)
