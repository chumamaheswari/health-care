import os
import csv
from datetime import datetime
from storage import get_all_employees, get_employees_by_department, DEPARTMENTS
from logger import get_logger

log = get_logger('reporter')

REPORTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'reports')
COLUMNS = ['employee_id', 'name', 'department', 'role', 'hire_date', 'status', 'salary', 'email', 'phone', 'created_at', 'updated_at']


def _write_csv(filepath: str, rows: list):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNS)
        writer.writerows(rows)


def generate_full_report():
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filepath = os.path.join(REPORTS_DIR, f'all_employees_{timestamp}.csv')
    rows = get_all_employees()
    _write_csv(filepath, rows)
    log.info(f"Full report generated: {os.path.basename(filepath)} ({len(rows)} employees)")
    return filepath


def generate_department_reports():
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    generated = []
    for dept in DEPARTMENTS:
        rows = get_employees_by_department(dept)
        filepath = os.path.join(REPORTS_DIR, f'{dept.lower()}_{timestamp}.csv')
        _write_csv(filepath, rows)
        log.info(f"{dept} report: {len(rows)} employees -> {os.path.basename(filepath)}")
        generated.append(filepath)
    return generated


def generate_summary() -> dict:
    summary = {}
    all_rows = get_all_employees()
    summary['total'] = len(all_rows)
    for dept in DEPARTMENTS:
        dept_rows = [r for r in all_rows if r[2] == dept]
        active = [r for r in dept_rows if r[5] == 'Active']
        summary[dept] = {'total': len(dept_rows), 'active': len(active)}
    return summary
