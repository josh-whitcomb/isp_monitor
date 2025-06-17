"""
Main entry point for ISP Uptime Monitoring.
"""
import argparse
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    """Main entry point for the application."""
    parser = argparse.ArgumentParser(description="ISP Uptime Monitoring Dashboard")
    parser.add_argument('--no-speedtest', action='store_true', help='Do not run a speed test at startup')
    args = parser.parse_args()
    from .dashboard import run_dashboard
    run_dashboard(run_speedtest_at_start=not args.no_speedtest)

if __name__ == "__main__":
    main() 