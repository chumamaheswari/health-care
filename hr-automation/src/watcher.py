import os
import time
import shutil
from employee_manager import process_file
from reporter import generate_full_report, generate_department_reports, generate_summary
from logger import get_logger

log = get_logger('watcher')

INCOMING_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'incoming')
PROCESSED_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'processed')
FAILED_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'failed')


def watch(interval: int = 10):
    os.makedirs(INCOMING_DIR, exist_ok=True)
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    os.makedirs(FAILED_DIR, exist_ok=True)

    log.info(f"Watching for new files in: {INCOMING_DIR}")
    log.info(f"Drop CSV files there to trigger automatic processing.")

    while True:
        csv_files = [f for f in os.listdir(INCOMING_DIR) if f.lower().endswith('.csv')]

        for filename in csv_files:
            filepath = os.path.join(INCOMING_DIR, filename)
            log.info(f"New file detected: {filename}")

            result = process_file(filepath)

            if 'error' in result:
                dest = os.path.join(FAILED_DIR, filename)
                log.error(f"Moving {filename} to failed/")
            else:
                dest = os.path.join(PROCESSED_DIR, filename)
                log.info(f"Moving {filename} to processed/")

                # Auto-generate reports after each successful batch
                generate_full_report()
                generate_department_reports()

                summary = generate_summary()
                log.info(f"Summary: Total={summary['total']} | " +
                         " | ".join(f"{d}: {summary[d]['total']} ({summary[d]['active']} active)"
                                    for d in summary if d != 'total'))

            shutil.move(filepath, dest)

        time.sleep(interval)
