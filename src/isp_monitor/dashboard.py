"""
Dashboard module for real-time ISP monitoring visualization.
"""

import sys
import time
from datetime import datetime
from typing import List, Tuple

import numpy as np
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QSplitter
from PyQt6.QtCore import QTimer, Qt, QThread, pyqtSignal
import pyqtgraph as pg
from pyqtgraph import AxisItem

from .monitor import ISPMonitor
from .workers import SpeedTestWorker
from .utils import format_time

class TimeAxisItem(AxisItem):
    def tickStrings(self, values, scale, spacing):
        return [format_time(v) for v in values]

class MonitoringDashboard(QMainWindow):
    """Main dashboard window for ISP monitoring."""
    
    def __init__(self, run_speedtest_at_start=True):
        super().__init__()
        self.monitor = ISPMonitor()
        self.setup_ui()
        self.setup_data_structures()
        self.setup_timers()
        self.speedtest_running = False
        self.speed_label_item = None
        self.speedtest_thread = None
        if run_speedtest_at_start:
            self.run_speed_test_now()
        
    def setup_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("ISP Uptime Monitor")
        self.setGeometry(100, 100, 1400, 600)  # Wider, less tall
        
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Status bar
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Status: Initializing...")
        self.ping_label = QLabel("Ping: -- ms")
        self.speed_label = QLabel("Speed: -- Mbps")
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.ping_label)
        status_layout.addWidget(self.speed_label)
        # Add speed test button
        self.speedtest_button = QPushButton("Run Speed Test Now")
        self.speedtest_button.clicked.connect(self.run_speed_test_now)
        status_layout.addWidget(self.speedtest_button)
        main_layout.addLayout(status_layout)
        # Show error if speedtest is not available
        if not self.monitor.speedtest_available:
            self.speedtest_button.setEnabled(False)
            self.speed_label.setText("Speed: Speedtest unavailable")
            self.speed_error_label = QLabel("Speedtest initialization failed. Try again later or check your network.")
            self.speed_error_label.setStyleSheet("color: red;")
            main_layout.addWidget(self.speed_error_label)
        # Splitter for balanced vertical space
        self.splitter = QSplitter()
        self.splitter.setOrientation(Qt.Orientation.Vertical)
        main_layout.addWidget(self.splitter, 1)
        # Ping panel
        ping_panel = QWidget()
        ping_layout = QHBoxLayout(ping_panel)
        ping_chart_col = QVBoxLayout()
        self.ping_plot = pg.PlotWidget(title="Ping Response Time", axisItems={'bottom': TimeAxisItem(orientation='bottom')})
        self.ping_plot.setLabel('left', 'Response Time', 'ms')
        self.ping_plot.setLabel('bottom', 'Time', '')
        ping_chart_col.addWidget(self.ping_plot, 1)
        self.ping_status_label = QLabel("Initializing...")
        self.ping_status_label.setStyleSheet("color: orange;")
        ping_chart_col.addWidget(self.ping_status_label)
        ping_layout.addLayout(ping_chart_col, 3)
        # Ping metrics box
        self.ping_metrics_box = QFrame()
        self.ping_metrics_box.setFrameShape(QFrame.Shape.StyledPanel)
        self.ping_metrics_box.setFixedWidth(200)
        self.ping_metrics_layout = QVBoxLayout(self.ping_metrics_box)
        self.ping_metrics_label = QLabel("")
        self.ping_metrics_label.setStyleSheet("font-size: 18px; color: white; background: #222; border-radius: 8px; padding: 12px;")
        self.ping_metrics_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ping_metrics_layout.addWidget(self.ping_metrics_label)
        ping_layout.addWidget(self.ping_metrics_box, 1)
        self.splitter.addWidget(ping_panel)
        # Speedtest panel: graph + result box
        speed_panel = QWidget()
        speed_layout = QHBoxLayout(speed_panel)
        self.speed_plot = pg.PlotWidget(title="Connection Speed")
        self.speed_plot.setLabel('left', 'Speed', 'Mbps')
        self.speed_plot.setLabel('bottom', 'Time', 's')
        self.speed_plot.setYRange(0, 100)
        self.speed_plot.setXRange(0, 30)
        speed_layout.addWidget(self.speed_plot, 3)
        # Result box
        self.result_box = QFrame()
        self.result_box.setFrameShape(QFrame.Shape.StyledPanel)
        self.result_box.setFixedWidth(200)
        self.result_layout = QVBoxLayout(self.result_box)
        self.result_label = QLabel("")
        self.result_label.setStyleSheet("font-size: 18px; color: white; background: #222; border-radius: 8px; padding: 12px;")
        self.result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_layout.addWidget(self.result_label)
        speed_layout.addWidget(self.result_box, 1)
        self.splitter.addWidget(speed_panel)
        # Speedtest status line
        self.speed_status_label = QLabel("Initializing...")
        self.speed_status_label.setStyleSheet("color: orange;")
        main_layout.addWidget(self.speed_status_label)
        # Hide result initially
        self.result_box.hide()
        self.splitter.setSizes([1, 1])
        
    def setup_data_structures(self):
        """Initialize data structures for storing monitoring data."""
        self.window_seconds = 300  # 5 minutes for ping
        self.ping_time_data = np.full(self.window_seconds, np.nan)
        self.ping_data = np.full(self.window_seconds, np.nan)
        self.current_index = 0
        self.last_speed_value = np.nan
        self.ping_curve = self.ping_plot.plot(pen='b')
        # For speedtest, use dynamic arrays
        self.speed_time_data = []
        self.speed_data = []
        self.speed_curve = self.speed_plot.plot(pen='g')
        self.speed_label_item = None
        self.speedtest_running = False
        self.speedtest_thread = None
        
    def setup_timers(self):
        """Set up timers for periodic updates."""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_data)
        self.update_timer.start(1000)  # Update every second
        
    def run_speed_test_now(self):
        """Run a speed test in a background thread and update the UI/chart when done."""
        if not self.monitor.speedtest_available:
            self.speed_label.setText("Speed: Speedtest unavailable")
            self.speed_status_label.setText("Speedtest unavailable")
            return
        if self.speedtest_running:
            self.speed_status_label.setText("Speedtest already running")
            return  # Prevent multiple concurrent tests
        # Clear old graph/result
        self.speed_time_data = []
        self.speed_data = []
        self.speed_curve.setData([], [])
        self.result_label.setText("")
        self.result_box.hide()
        self.speed_plot.show()
        self.speedtest_running = True
        self.speed_curve.setPen('g')  # Always green
        self.speed_status_label.setText("Running speed test...")
        QApplication.processEvents()  # Update UI
        self.speedtest_thread = SpeedTestWorker(self.monitor, force=True)
        self.speedtest_thread.result_ready.connect(self.handle_speedtest_result)
        self.speedtest_thread.finished.connect(self.cleanup_speedtest_thread)
        self.speedtest_thread.start()
        self._speedtest_progress = 0

    def handle_speedtest_result(self, speed):
        if speed.get("error"):
            self.speed_label.setText("Speed: Speedtest failed")
            self.speed_status_label.setText(f"Speedtest failed ({speed.get('error_code', 'error')})")
            self.result_label.setText("Speedtest failed")
            self.result_box.show()
            self.speedtest_running = False
            self.speed_curve.setPen('g')
            return
        self.last_speed_value = speed['download']
        self.speed_label.setText(f"Speed: {self.last_speed_value:.2f} Mbps (manual)")
        # Draw a horizontal green line at the measured speed, padded to 30s
        self.speed_curve.setPen('g')
        self.speed_time_data = list(range(31))
        self.speed_data = [self.last_speed_value] * 31
        self.speed_curve.setData(self.speed_time_data, self.speed_data)
        self.result_label.setText(f"<b>Download:</b> {self.last_speed_value:.2f} Mbps<br><b>Upload:</b> {speed['upload']:.2f} Mbps")
        self.result_box.show()
        self.speedtest_running = False
        self.speed_status_label.setText("Idle")

    def cleanup_speedtest_thread(self):
        self.speedtest_thread = None

    def update_data(self):
        """Update monitoring data and refresh plots."""
        if self.speedtest_running:
            self.ping_status_label.setText("Paused (speed test running)")
        else:
            is_connected = self.monitor.check_connection()
            if is_connected:
                self.ping_status_label.setText("Connected: Running")
            else:
                self.ping_status_label.setText("Disconnected")
        is_connected = self.monitor.check_connection()
        self.status_label.setText(f"Status: {'Connected' if is_connected else 'Disconnected'}")
        # Pause ping chart while speedtest is running
        if self.speedtest_running:
            # Still update speedtest chart
            if is_connected:
                if self.speedtest_running:
                    self._speedtest_progress += 1
                    x = list(range(self._speedtest_progress + 1))
                    y = [0] * (self._speedtest_progress + 1)
                    self.speed_curve.setPen('g')
                    self.speed_curve.setData(x, y)
                    self.speed_plot.show()
                    self.result_box.hide()
            return
        if is_connected:
            ping_time = self.monitor.measure_ping()
            self.ping_label.setText(f"Ping: {ping_time:.1f} ms")
            now = time.time()
            self.ping_time_data[self.current_index] = now
            self.ping_data[self.current_index] = ping_time
            # Only update speed graph if running
            if self.speedtest_running:
                self._speedtest_progress += 1
                x = list(range(self._speedtest_progress + 1))
                y = [0] * (self._speedtest_progress + 1)
                self.speed_curve.setPen('g')
                self.speed_curve.setData(x, y)
                self.speed_plot.show()
                self.result_box.hide()
            else:
                self.speed_curve.setPen('g')
                self.speed_plot.show()  # Keep the chart visible after test
            # Only plot valid (non-nan) data
            valid = ~np.isnan(self.ping_time_data)
            x = self.ping_time_data[valid]
            y = self.ping_data[valid]
            self.ping_curve.setData(x, y)
            # Scroll to show the last 5 minutes
            if len(x) > 0:
                right = x[-1]
                left = right - self.window_seconds
                self.ping_plot.setXRange(left, right)
                # Update metrics box
                valid_y = y[~np.isnan(y)]
                if len(valid_y) > 0:
                    min_ping = np.nanmin(valid_y)
                    max_ping = np.nanmax(valid_y)
                    avg_ping = np.nanmean(valid_y)
                    self.ping_metrics_label.setText(f"<b>Min:</b> {min_ping:.1f} ms<br><b>Max:</b> {max_ping:.1f} ms<br><b>Avg:</b> {avg_ping:.1f} ms")
                else:
                    self.ping_metrics_label.setText("No data")
        else:
            self.ping_data[self.current_index] = np.nan
            self.ping_time_data[self.current_index] = np.nan
            self.last_speed_value = np.nan
            self.ping_label.setText("Ping: -- ms")
            self.speed_label.setText("Speed: -- Mbps")
            self.speed_status_label.setText("Idle")
            self.speed_curve.setPen('k')
            self.speed_plot.hide()
            self.result_box.hide()
        self.current_index = (self.current_index + 1) % self.window_seconds
        if self.current_index == 0:
            self.ping_data = np.roll(self.ping_data, -1)
            self.ping_time_data = np.roll(self.ping_time_data, -1)

def run_dashboard(run_speedtest_at_start=True):
    """Run the monitoring dashboard."""
    app = QApplication(sys.argv)
    window = MonitoringDashboard(run_speedtest_at_start=run_speedtest_at_start)
    window.show()
    sys.exit(app.exec()) 