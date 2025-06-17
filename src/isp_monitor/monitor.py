"""
Network monitoring logic for ISP Uptime Monitoring.
"""
import time
import ping3
import speedtest
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class ISPMonitor:
    """Main class for monitoring ISP uptime and performance."""
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        try:
            self.speedtest = speedtest.Speedtest()
            self.speedtest_available = True
        except Exception as e:
            logger.error(f"Speedtest initialization failed: {e}")
            self.speedtest = None
            self.speedtest_available = False
        self.last_speed_test = 0
        self.speed_test_interval = 300  # 5 minutes
        logger.info("ISP Monitor initialized")
    def check_connection(self) -> bool:
        try:
            return ping3.ping('8.8.8.8', timeout=1) is not None
        except Exception as e:
            logger.error(f"Error checking connection: {e}")
            return False
    def measure_ping(self) -> float:
        try:
            ping_time = ping3.ping('8.8.8.8', timeout=1)
            if ping_time is not None:
                return ping_time * 1000
            return 0.0
        except Exception as e:
            logger.error(f"Error measuring ping: {e}")
            return 0.0
    def measure_speed(self, force=False, progress_callback=None) -> Dict[str, float]:
        if not self.speedtest_available:
            logger.error("Speedtest is not available.")
            return {"download": 0.0, "upload": 0.0, "error": True}
        current_time = time.time()
        if not force and current_time - self.last_speed_test < self.speed_test_interval:
            return {"download": self.speedtest.results.download / 1_000_000 if hasattr(self.speedtest, 'results') else 0.0, "upload": self.speedtest.results.upload / 1_000_000 if hasattr(self.speedtest, 'results') else 0.0}
        try:
            logger.info("Starting speed test...")
            self.speedtest.get_best_server()
            # Real-time download progress
            download_progress = []
            def download_callback(*args, **kwargs):
                if len(args) >= 3:
                    bytes_received, total_bytes, elapsed = args[:3]
                    mbps = (bytes_received * 8) / (elapsed * 1_000_000) if elapsed > 0 else 0.0
                    if progress_callback:
                        progress_callback('download', elapsed, mbps)
                    download_progress.append((elapsed, mbps))
            download_speed = self.speedtest.download(callback=download_callback) / 1_000_000
            # Real-time upload progress
            upload_progress = []
            def upload_callback(*args, **kwargs):
                if len(args) >= 3:
                    bytes_sent, total_bytes, elapsed = args[:3]
                    mbps = (bytes_sent * 8) / (elapsed * 1_000_000) if elapsed > 0 else 0.0
                    if progress_callback:
                        progress_callback('upload', elapsed, mbps)
                    upload_progress.append((elapsed, mbps))
            upload_speed = self.speedtest.upload(callback=upload_callback) / 1_000_000
            self.last_speed_test = current_time
            logger.info(f"Speed test completed: {download_speed:.1f} Mbps down, {upload_speed:.1f} Mbps up")
            return {"download": download_speed, "upload": upload_speed}
        except Exception as e:
            logger.error(f"Error measuring speed: {e}")
            return {"download": 0.0, "upload": 0.0, "error": True} 