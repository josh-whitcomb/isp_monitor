# ISP Uptime Monitoring

A Python project for monitoring ISP uptime and performance with a real-time dashboard.

## Features
- Real-time ping and speedtest monitoring
- Beautiful PyQt6 dashboard with charts and metrics
- Modular, maintainable codebase
- Threaded speedtest to keep UI responsive
- 5-minute scrolling ping window with wall-clock time
- Metrics for min/max/avg ping and speedtest results

## Project Structure

```
src/
  isp_monitor/
    __init__.py
    main.py         # Entry point, argument parsing
    dashboard.py    # PyQt6 GUI and dashboard logic
    monitor.py      # ISPMonitor: ping and speedtest logic
    workers.py      # QThread-based background workers
    utils.py        # Utility functions (e.g., time formatting)
tests/
  ...
```

## Setup

1. **Create and activate a virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Unix/macOS
   # or
   .\venv\Scripts\activate  # On Windows
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## Install with pip or pipx

You can install directly from GitHub:

```bash
pip install git+https://github.com/josh-whitcomb/isp_monitor.git
```

Or, for isolated CLI usage:

```bash
pipx install git+https://github.com/josh-whitcomb/isp_monitor.git
```

Then run:

```bash
isp-uptime-monitor
```

## Usage

Run the dashboard (if not using pipx):
```bash
python -m src.isp_monitor.main
```

Optional arguments:
- `--no-speedtest` : Do not run a speed test at startup

## Development
- Use `black` for code formatting
- Use `flake8` for linting
- Use `pytest` for testing

## Notes
- The dashboard is fully modular and easy to extend.
- All network logic is in `monitor.py`, all threading in `workers.py`, and all UI in `dashboard.py`.
- The ping chart pauses during speed tests for accuracy.

---

Enjoy monitoring your ISP uptime and performance! 