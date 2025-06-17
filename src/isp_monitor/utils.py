"""
Utility functions for ISP Uptime Monitoring.
"""
import time

def format_time(ts: float) -> str:
    """Format a timestamp as HH:MM:SS."""
    return time.strftime('%H:%M:%S', time.localtime(ts)) 