"""
Worker threads for ISP Uptime Monitoring.
"""
from PyQt6.QtCore import QThread, pyqtSignal
from .dns_leak import DNSLeakTester

class SpeedTestWorker(QThread):
    result_ready = pyqtSignal(dict)
    progress = pyqtSignal(str, float, float)  # phase ('download' or 'upload'), elapsed_time, speed_mbps
    def __init__(self, monitor, force=False):
        super().__init__()
        self.monitor = monitor
        self.force = force
    def run(self):
        speed = self.monitor.measure_speed(force=self.force, progress_callback=self.emit_progress)
        self.result_ready.emit(speed)

    def emit_progress(self, phase, elapsed_time, speed_mbps):
        self.progress.emit(phase, elapsed_time, speed_mbps)

class DNSLeakTestWorker(QThread):
    """Worker thread for running DNS leak tests."""
    result_ready = pyqtSignal(dict)
    progress = pyqtSignal(float)  # Progress percentage (0-100)

    def __init__(self):
        super().__init__()
        self.dns_tester = DNSLeakTester()

    def run(self):
        """Run the DNS leak test and emit results."""
        results = self.dns_tester.check_dns_leaks(progress_callback=self.progress.emit)
        self.result_ready.emit(results) 