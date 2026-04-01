import os
import signal
import sys
import time
import shutil
from employee_manager import process_file
from reporter import generate_full_report, generate_department_reports, generate_summary
from logger import get_logger

log = get_logger('watcher')

INCOMING_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'incoming')
PROCESSED_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'processed')
FAILED_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'failed')

_running = True


def _handle_shutdown(sig, frame):
    global _running
    log.info("Shutdown signal received. Stopping watcher...")
    _running = False


def watch(interval: int = 10):
    global _running
    signal.signal(signal.SIGINT, _handle_shutdown)
    signal.signal(signal.SIGTERM, _handle_shutdown)

    os.makedirs(INCOMING_DIR, exist_ok=True)
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    os.makedirs(FAILED_DIR, exist_ok=True)

    log.info(f"Watching for new files in: {INCOMING_DIR}")
    log.info("Drop CSV files there to trigger automatic processing. Press Ctrl+C to stop.")

    while _running:
        try:
            csv_files = [f for f in os.listdir(INCOMING_DIR) if f.lower().endswith('.csv')]
        except OSError as e:
            log.error(f"Cannot read incoming directory: {e}")
            time.sleep(interval)
            continue

        for filename in csv_files:
            if not _running:
                break
            filepath = os.path.join(INCOMING_DIR, filename)

            # Wait briefly to ensure file is fully written before reading
            try:
                size_before = os.path.getsize(filepath)
                time.sleep(1)
                size_after = os.path.getsize(filepath)
                if size_before != size_after:
                    log.info(f"File {filename} still being written, skipping this cycle.")
                    continue
            except OSError:
                continue

            log.info(f"New file detected: {filename}")
            result = process_file(filepath)

            if 'error' in result:
                dest = os.path.join(FAILED_DIR, filename)
                log.error(f"Moving {filename} to failed/")
            else:
                dest = os.path.join(PROCESSED_DIR, filename)
                log.info(f"Moving {filename} to processed/")

                generate_full_report()
                generate_department_reports()

                summary = generate_summary()
                log.info(f"Summary: Total={summary['total']} | " +
                         " | ".join(f"{d}: {summary[d]['total']} ({summary[d]['active']} active)"
                                    for d in summary if d != 'total'))

            try:
                shutil.move(filepath, dest)
            except OSError as e:
                log.error(f"Could not move {filename}: {e}")

        time.sleep(interval)

    log.info("Watcher stopped.")
