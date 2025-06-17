"""
Worker threads for ISP Uptime Monitoring.
"""
from PyQt6.QtCore import QThread, pyqtSignal

class SpeedTestWorker(QThread):
    result_ready = pyqtSignal(dict)
    def __init__(self, monitor, force=False):
        super().__init__()
        self.monitor = monitor
        self.force = force
    def run(self):
        speed = self.monitor.measure_speed(force=self.force)
        self.result_ready.emit(speed) 