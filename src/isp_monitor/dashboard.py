"""
Dashboard module for real-time ISP monitoring visualization.

Features:
- Real-time ping monitoring with min/max/avg and packet loss tracking
- Red X markers on the ping plot for lost packets
- Speedtest with indeterminate progress bar and results display
- DNS leak testing with detailed results
- Unified, simple UI with all results in a right-side column
"""

import sys
import time
import math
from datetime import datetime
from typing import List, Tuple

import numpy as np
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QSplitter, QProgressBar,
    QDialog
)
from PyQt6.QtCore import QTimer, Qt, QThread, pyqtSignal
import pyqtgraph as pg
from pyqtgraph import AxisItem

from .monitor import ISPMonitor
from .workers import SpeedTestWorker, DNSLeakTestWorker
from .utils import format_time

class TimeAxisItem(AxisItem):
    """Custom axis for displaying formatted time labels on the ping plot."""
    def tickStrings(self, values, scale, spacing):
        return [format_time(v) for v in values]

class MonitoringDashboard(QMainWindow):
    """
    Main dashboard window for ISP monitoring.
    Shows real-time ping, packet loss, and speedtest results in a unified UI.
    """
    def __init__(self, run_speedtest_at_start=True):
        super().__init__()
        self.monitor = ISPMonitor()
        self.setup_ui()
        self.setup_data_structures()
        self.setup_timers()
        self.speedtest_running = False
        self.speed_label_item = None
        self.speedtest_thread = None
        self.dns_test_thread = None
        self.dns_test_running = False
        if run_speedtest_at_start:
            self.run_speed_test_now()

    def setup_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("ISP Uptime Monitor")
        self.setGeometry(100, 100, 1400, 600)
        # Central widget and main layout
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
        self.speedtest_button = QPushButton("Run Speed Test Now")
        self.speedtest_button.clicked.connect(self.run_speed_test_now)
        status_layout.addWidget(self.speedtest_button)
        
        # Add DNS leak test button
        self.dns_test_button = QPushButton("Run DNS Leak Test")
        self.dns_test_button.clicked.connect(self.run_dns_leak_test)
        status_layout.addWidget(self.dns_test_button)
        
        main_layout.addLayout(status_layout)

        # Show error if speedtest is not available
        if not self.monitor.speedtest_available:
            self.speedtest_button.setEnabled(False)
            self.speed_label.setText("Speed: Speedtest unavailable")
            self.speed_error_label = QLabel("Speedtest initialization failed. Try again later or check your network.")
            self.speed_error_label.setStyleSheet("color: red;")
            main_layout.addWidget(self.speed_error_label)

        # DNS leak test results box
        self.dns_result_box = QFrame()
        self.dns_result_box.setFrameShape(QFrame.Shape.StyledPanel)
        self.dns_result_box.setFixedWidth(200)
        self.dns_result_layout = QVBoxLayout(self.dns_result_box)
        self.dns_result_title = QLabel("DNS Leak Test")
        self.dns_result_title.setStyleSheet("font-size: 20px; font-weight: bold; color: #ff69b4; background: #222; border-radius: 8px; padding: 4px; margin-bottom: 4px;")
        self.dns_result_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dns_result_layout.addWidget(self.dns_result_title)
        self.dns_result_label = QLabel("")
        self.dns_result_label.setStyleSheet("font-size: 18px; color: white; background: #222; border-radius: 8px; padding: 12px;")
        self.dns_result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dns_result_layout.addWidget(self.dns_result_label)
        self.dns_result_box.hide()

        # DNS leak test progress bar
        self.dns_progress = QProgressBar()
        self.dns_progress.setMinimum(0)
        self.dns_progress.setMaximum(100)
        self.dns_progress.hide()
        main_layout.addWidget(self.dns_progress)

        # Splitter for vertical space
        self.splitter = QSplitter()
        self.splitter.setOrientation(Qt.Orientation.Vertical)
        main_layout.addWidget(self.splitter, 1)
        # Ping panel
        ping_panel = QWidget()
        ping_layout = QHBoxLayout(ping_panel)
        ping_chart_col = QVBoxLayout()
        self.ping_plot = pg.PlotWidget(title="Ping Response Time", axisItems={'bottom': TimeAxisItem(orientation='bottom')})
        self.ping_plot.setLabel('left', 'Response Time', 'ms')
        self.ping_plot.setLabel('bottom', 'Time')
        ping_chart_col.addWidget(self.ping_plot, 1)
        self.ping_status_label = QLabel("Initializing...")
        self.ping_status_label.setStyleSheet("color: orange;")
        ping_chart_col.addWidget(self.ping_status_label)
        ping_layout.addLayout(ping_chart_col, 3)
        # Metrics/results column
        metrics_col = QVBoxLayout()
        # Ping metrics box
        self.ping_metrics_box = QFrame()
        self.ping_metrics_box.setFrameShape(QFrame.Shape.StyledPanel)
        self.ping_metrics_box.setFixedWidth(200)
        self.ping_metrics_layout = QVBoxLayout(self.ping_metrics_box)
        self.ping_metrics_title = QLabel("Ping")
        self.ping_metrics_title.setStyleSheet("font-size: 20px; font-weight: bold; color: #00ccff; background: #222; border-radius: 8px; padding: 4px; margin-bottom: 4px;")
        self.ping_metrics_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ping_metrics_layout.addWidget(self.ping_metrics_title)
        self.ping_metrics_label = QLabel("")
        self.ping_metrics_label.setStyleSheet("font-size: 18px; color: white; background: #222; border-radius: 8px; padding: 12px;")
        self.ping_metrics_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ping_metrics_layout.addWidget(self.ping_metrics_label)
        metrics_col.addWidget(self.ping_metrics_box)
        # Speedtest results box
        self.result_box = QFrame()
        self.result_box.setFrameShape(QFrame.Shape.StyledPanel)
        self.result_box.setFixedWidth(200)
        self.result_layout = QVBoxLayout(self.result_box)
        self.result_title = QLabel("Speed")
        self.result_title.setStyleSheet("font-size: 20px; font-weight: bold; color: #00cc66; background: #222; border-radius: 8px; padding: 4px; margin-bottom: 4px;")
        self.result_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_layout.addWidget(self.result_title)
        self.result_label = QLabel("")
        self.result_label.setStyleSheet("font-size: 18px; color: white; background: #222; border-radius: 8px; padding: 12px;")
        self.result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_layout.addWidget(self.result_label)
        metrics_col.addWidget(self.result_box)
        # Add DNS result box to metrics column
        metrics_col.addWidget(self.dns_result_box)
        metrics_col.addStretch(1)
        ping_layout.addLayout(metrics_col, 1)
        self.splitter.addWidget(ping_panel)
        # Speedtest panel: just the progress bar
        speed_panel = QWidget()
        speed_layout = QHBoxLayout(speed_panel)
        self.speed_progress = QProgressBar()
        self.speed_progress.setMinimum(0)
        self.speed_progress.setMaximum(0)  # Indeterminate/busy mode
        self.speed_progress.setTextVisible(False)
        self.speed_progress.hide()
        speed_layout.addWidget(self.speed_progress, 3)
        self.splitter.addWidget(speed_panel)
        self.splitter.setSizes([1, 1])

    def setup_data_structures(self):
        """Initialize data structures for storing monitoring data and packet loss."""
        self.window_seconds = 300  # 5 minutes for ping
        self.ping_time_data = []
        self.ping_data = []
        self.current_index = 0
        self.last_speed_value = np.nan
        self.ping_curve = self.ping_plot.plot(pen='b')
        # Packet loss tracking
        self.total_pings = 0
        self.lost_pings = 0
        self.lost_ping_times = []
        self.lost_ping_scatter = pg.ScatterPlotItem(size=14, pen=pg.mkPen('r', width=2), brush=pg.mkBrush(255,0,0,100), symbol='x')
        self.ping_plot.addItem(self.lost_ping_scatter)
        self.speed_label_item = None
        self.speedtest_running = False
        self.speedtest_thread = None

    def setup_timers(self):
        """Set up timers for periodic updates."""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_data)
        self.update_timer.start(1000)  # Update every second

    def run_speed_test_now(self):
        """Run a speed test in a background thread and update the UI when done."""
        if not self.monitor.speedtest_available:
            try:
                self.speed_label.setText("Initializing speedtest...")
                QApplication.processEvents()
                self.monitor.init_speedtest()
            except Exception as e:
                self.speed_label.setText("Speed: Speedtest unavailable")
                self.speed_error_label.setText(f"Speedtest initialization failed. Try again later or check your network.\n{e}")
                return
            if not self.monitor.speedtest_available:
                self.speed_label.setText("Speed: Speedtest unavailable")
                self.speed_error_label.setText("Speedtest initialization failed. Try again later or check your network.")
                return
        if self.speedtest_running:
            self.speed_label.setText("Speedtest already running")
            self.speedtest_button.setEnabled(False)
            self.speedtest_button.setText("Speedtest currently running")
            return  # Prevent multiple concurrent tests
        # Reset progress bar and result
        self.result_label.setText("")
        self.result_box.hide()
        self.speed_progress.show()
        self.speedtest_running = True
        self.speed_label.setText("Running speed test...")
        self.speedtest_button.setEnabled(False)
        self.speedtest_button.setText("Speedtest currently running")
        QApplication.processEvents()  # Update UI
        self.speedtest_thread = SpeedTestWorker(self.monitor, force=True)
        self.speedtest_thread.progress.connect(self.handle_speedtest_progress)
        self.speedtest_thread.result_ready.connect(self.handle_speedtest_result)
        self.speedtest_thread.finished.connect(self.cleanup_speedtest_thread)
        self.speedtest_thread.start()
        self._speedtest_progress = 0

    def handle_speedtest_progress(self, phase, elapsed_time, speed_mbps):
        # No progress bar logic needed; indeterminate bar is already shown
        pass

    def handle_speedtest_result(self, speed):
        """Display speedtest results and hide the progress bar."""
        dn = speed['download']
        up = speed['upload']
        self.speed_label.setText(f"Speed: {dn:.2f} Mbps (manual)")
        dn_str = f"{dn:.2f}" if dn is not None and not math.isnan(dn) else "--"
        up_str = f"{up:.2f}" if up is not None and not math.isnan(up) else "--"
        self.result_label.setText(f"<b>Dn:</b> {dn_str} Mbps<br><b>Up:</b> {up_str} Mbps")
        self.result_box.show()
        self.speedtest_running = False
        self.speed_progress.hide()
        self.speedtest_button.setEnabled(True)
        self.speedtest_button.setText("Run Speed Test Now")

    def cleanup_speedtest_thread(self):
        self.speedtest_thread = None

    def update_data(self):
        """Update monitoring data, refresh plots, and update packet loss info."""
        if self.speedtest_running:
            self.ping_status_label.setText("Paused (speed test running)")
            self.speed_progress.show()
            return
        else:
            is_connected = self.monitor.check_connection()
            if is_connected:
                self.ping_status_label.setText("Connected: Running")
            else:
                self.ping_status_label.setText("Disconnected")
        is_connected = self.monitor.check_connection()
        self.status_label.setText(f"Status: {'Connected' if is_connected else 'Disconnected'}")
        if self.speedtest_running:
            self.speed_progress.show()
        else:
            self.speed_progress.hide()
        if is_connected:
            ping_time = self.monitor.measure_ping()
            self.total_pings += 1
            lost = False
            self.ping_label.setText(f"Ping: {ping_time:.1f} ms")
            now = time.time()
            # Add new data point
            self.ping_time_data.append(now)
            self.ping_data.append(ping_time)
            # Track lost pings
            if ping_time == 0.0 or ping_time is None:
                self.lost_pings += 1
                self.lost_ping_times.append(now)
                lost = True
            # Remove old data points outside the window
            cutoff_time = now - self.window_seconds
            while self.ping_time_data and self.ping_time_data[0] < cutoff_time:
                self.ping_time_data.pop(0)
                self.ping_data.pop(0)
            # Remove old lost ping times
            while self.lost_ping_times and self.lost_ping_times[0] < cutoff_time:
                self.lost_ping_times.pop(0)
            # Update the ping plot
            if self.ping_time_data:
                self.ping_curve.setData(self.ping_time_data, self.ping_data)
                # Update lost ping scatter plot
                lost_x = self.lost_ping_times
                lost_y = [max(self.ping_data) * 1.05 if self.ping_data else 100 for _ in lost_x]  # Place X above the plot
                self.lost_ping_scatter.setData(lost_x, lost_y)
                # Scroll to show the last 5 minutes
                right = self.ping_time_data[-1]
                left = right - self.window_seconds
                self.ping_plot.setXRange(left, right)
                # Update metrics box
                valid_y = [y for y in self.ping_data if not np.isnan(y)]
                if len(valid_y) > 0:
                    min_ping = np.nanmin(valid_y)
                    max_ping = np.nanmax(valid_y)
                    avg_ping = np.nanmean(valid_y)
                    loss_percent = (self.lost_pings / self.total_pings * 100) if self.total_pings > 0 else 0
                    self.ping_metrics_label.setText(
                        f"<b>Min:</b> {min_ping:.1f} ms<br>"
                        f"<b>Max:</b> {max_ping:.1f} ms<br>"
                        f"<b>Avg:</b> {avg_ping:.1f} ms<br>"
                        f"<b>Loss:</b> {self.lost_pings}/{self.total_pings} ({loss_percent:.1f}%)"
                    )
                else:
                    self.ping_metrics_label.setText("No data")
        else:
            self.ping_data = []
            self.ping_time_data = []
            self.last_speed_value = np.nan
            self.ping_label.setText("Ping: -- ms")
            self.speed_label.setText("Speed: -- Mbps")
            self.speed_progress.hide()
            self.result_box.hide()

    def run_dns_leak_test(self):
        """Run a DNS leak test in a background thread."""
        if self.dns_test_running:
            return
        
        self.dns_test_running = True
        self.dns_test_button.setEnabled(False)
        self.dns_test_button.setText("DNS Test Running...")
        self.dns_progress.show()
        self.dns_result_box.hide()
        
        self.dns_test_thread = DNSLeakTestWorker()
        self.dns_test_thread.progress.connect(self.handle_dns_test_progress)
        self.dns_test_thread.result_ready.connect(self.handle_dns_test_result)
        self.dns_test_thread.finished.connect(self.cleanup_dns_test_thread)
        self.dns_test_thread.start()

    def handle_dns_test_progress(self, progress):
        """Update DNS leak test progress bar."""
        self.dns_progress.setValue(int(progress))

    def handle_dns_test_result(self, results):
        """Display DNS leak test results."""
        is_leaking = results["is_leaking"]
        self.dns_test_results = results  # Store results for the details dialog
        
        status_color = "#ff4444" if is_leaking else "#44ff44"
        status_text = "LEAKING" if is_leaking else "SECURE"
        
        result_text = f"Status: <span style='color: {status_color}'>{status_text}</span>"
        
        self.dns_result_label.setText(result_text)
        
        # Add "More Info" button if not already added
        if not hasattr(self, 'dns_more_info_button'):
            self.dns_more_info_button = QPushButton("More Info")
            self.dns_more_info_button.clicked.connect(self.show_dns_details)
            self.dns_result_layout.addWidget(self.dns_more_info_button)
        
        self.dns_result_box.show()
        self.dns_progress.hide()
        self.dns_test_button.setEnabled(True)
        self.dns_test_button.setText("Run DNS Leak Test")
        self.dns_test_running = False

    def show_dns_details(self):
        """Show the DNS leak test details dialog."""
        if hasattr(self, 'dns_test_results'):
            dialog = DNSDetailsDialog(self.dns_test_results, self)
            dialog.exec()

    def cleanup_dns_test_thread(self):
        """Clean up the DNS leak test thread."""
        self.dns_test_thread = None
        self.dns_test_running = False
        self.dns_test_button.setEnabled(True)
        self.dns_test_button.setText("Run DNS Leak Test")
        self.dns_progress.hide()

class DNSDetailsDialog(QDialog):
    """Dialog window for displaying detailed DNS leak test results."""
    def __init__(self, results, parent=None):
        super().__init__(parent)
        self.setWindowTitle("DNS Leak Test Details")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout(self)
        
        # Status
        is_leaking = results["is_leaking"]
        status_color = "#ff4444" if is_leaking else "#44ff44"
        status_text = "LEAKING" if is_leaking else "SECURE"
        
        status_label = QLabel(f"Status: <span style='color: {status_color}'>{status_text}</span>")
        status_label.setStyleSheet("font-size: 18px;")
        layout.addWidget(status_label)
        
        # Configured DNS
        layout.addWidget(QLabel("<b>Configured DNS Servers:</b>"))
        for server in results["configured_dns"]:
            layout.addWidget(QLabel(server))
        
        # Unexpected servers (if leaking)
        if is_leaking:
            layout.addWidget(QLabel(""))  # Spacer
            layout.addWidget(QLabel("<b>Unexpected DNS Servers:</b>"))
            layout.addWidget(QLabel("The following servers were detected but not configured:"))
            for server in results["unexpected_servers"]:
                layout.addWidget(QLabel(server))
        
        # Test details
        layout.addWidget(QLabel(""))  # Spacer
        layout.addWidget(QLabel("<b>Test Details:</b>"))
        layout.addWidget(QLabel(f"Domains tested: {results['details']['domains_tested']}"))
        layout.addWidget(QLabel(f"Total servers detected: {results['details']['total_servers_detected']}"))
        
        # Close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)

def run_dashboard(run_speedtest_at_start=True):
    """Run the monitoring dashboard."""
    app = QApplication(sys.argv)
    window = MonitoringDashboard(run_speedtest_at_start=run_speedtest_at_start)
    window.show()
    sys.exit(app.exec()) 