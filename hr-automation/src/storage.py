import sqlite3
import os
from logger import get_logger

log = get_logger('storage')

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'hr_database.db')

DEPARTMENTS = ['Sales', 'Finance', 'Operations']

def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)

def initialize_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            employee_id     TEXT PRIMARY KEY,
            name            TEXT NOT NULL,
            department      TEXT NOT NULL,
            role            TEXT NOT NULL,
            hire_date       TEXT NOT NULL,
            status          TEXT NOT NULL DEFAULT 'Active',
            salary          REAL NOT NULL,
            email           TEXT,
            phone           TEXT,
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS activity_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT NOT NULL,
            action      TEXT NOT NULL,
            employee_id TEXT,
            details     TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS employee_documents (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id     TEXT NOT NULL,
            filename        TEXT NOT NULL,
            original_name   TEXT NOT NULL,
            uploaded_at     TEXT NOT NULL
        )
    ''')

    conn.commit()
    conn.close()
    log.info("Database initialized.")

def log_activity(action: str, employee_id: str = None, details: str = None):
    from datetime import datetime
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO activity_log (timestamp, action, employee_id, details) VALUES (?, ?, ?, ?)',
        (datetime.now().isoformat(), action, employee_id, details)
    )
    conn.commit()
    conn.close()

def upsert_employee(record: dict):
    from datetime import datetime
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()

    cursor.execute('SELECT employee_id FROM employees WHERE employee_id = ?', (record['employee_id'],))
    existing = cursor.fetchone()

    if existing:
        cursor.execute('''
            UPDATE employees SET
                name=?, department=?, role=?, hire_date=?, status=?,
                salary=?, email=?, phone=?, updated_at=?
            WHERE employee_id=?
        ''', (
            record['name'], record['department'], record['role'],
            record['hire_date'], record['status'], record['salary'],
            record.get('email'), record.get('phone'), now,
            record['employee_id']
        ))
        action = 'UPDATE'
    else:
        cursor.execute('''
            INSERT INTO employees
                (employee_id, name, department, role, hire_date, status, salary, email, phone, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            record['employee_id'], record['name'], record['department'],
            record['role'], record['hire_date'], record['status'],
            record['salary'], record.get('email'), record.get('phone'),
            now, now
        ))
        action = 'INSERT'

    conn.commit()
    conn.close()
    log_activity(action, record['employee_id'], f"{record['name']} | {record['department']}")
    log.info(f"{action}: {record['employee_id']} - {record['name']}")
    return action

def get_employee(employee_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM employees WHERE employee_id=?', (employee_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def delete_employee(employee_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM employees WHERE employee_id=?', (employee_id,))
    conn.commit()
    conn.close()
    log_activity('DELETE', employee_id)

def save_document(employee_id: str, filename: str, original_name: str):
    from datetime import datetime
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO employee_documents (employee_id, filename, original_name, uploaded_at) VALUES (?, ?, ?, ?)',
        (employee_id, filename, original_name, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def get_documents(employee_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM employee_documents WHERE employee_id=? ORDER BY uploaded_at DESC', (employee_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_all_employees():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM employees ORDER BY department, name')
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_employees_by_department(department: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM employees WHERE department=? ORDER BY name', (department,))
    rows = cursor.fetchall()
    conn.close()
    return rows
