import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from storage import initialize_db
from logger import get_logger

log = get_logger('main')


def run_watcher():
    from watcher import watch
    log.info("Starting HR Automation System - File Watcher Mode")
    watch(interval=10)


def run_report():
    from reporter import generate_full_report, generate_department_reports, generate_summary
    log.info("Generating reports...")
    full = generate_full_report()
    dept_reports = generate_department_reports()
    summary = generate_summary()

    print(f"\n=== HR Summary ===")
    print(f"Total Employees: {summary['total']}")
    for dept in ['Sales', 'Finance', 'Operations']:
        d = summary.get(dept, {})
        print(f"  {dept}: {d.get('total', 0)} total, {d.get('active', 0)} active")
    print(f"\nReports saved to: reports/")


def run_process(filepath: str):
    from employee_manager import process_file
    result = process_file(filepath)
    print(f"\nResult: {result}")


if __name__ == '__main__':
    initialize_db()

    if len(sys.argv) < 2:
        print("HR Automation System")
        print("Usage:")
        print("  python main.py watch          - Watch for new CSV files and auto-process")
        print("  python main.py report         - Generate department reports")
        print("  python main.py process <file> - Process a specific CSV file")
        sys.exit(0)

    command = sys.argv[1].lower()

    if command == 'watch':
        run_watcher()
    elif command == 'report':
        run_report()
    elif command == 'process' and len(sys.argv) == 3:
        run_process(sys.argv[2])
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
