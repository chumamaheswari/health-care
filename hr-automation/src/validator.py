import re
from datetime import datetime, date
from logger import get_logger

log = get_logger('validator')

REQUIRED_FIELDS = ['employee_id', 'name', 'department', 'role', 'hire_date', 'salary']
VALID_DEPARTMENTS = ['Sales', 'Finance', 'Operations']
VALID_STATUSES = ['Active', 'Inactive', 'On Leave']
MIN_SALARY = 15000
MAX_SALARY = 1_000_000
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
EMPLOYEE_ID_REGEX = re.compile(r'^[A-Za-z0-9_-]{1,20}$')


def validate_record(record: dict) -> tuple[bool, list[str]]:
    errors = []

    # Required fields — check presence and non-empty
    for field in REQUIRED_FIELDS:
        value = record.get(field)
        if value is None or str(value).strip() == '':
            errors.append(f"Missing required field: '{field}'")

    if errors:
        log.warning(f"Record {record.get('employee_id', 'UNKNOWN')} failed validation: {errors}")
        return False, errors

    emp_id = str(record['employee_id']).strip()
    name = str(record['name']).strip()
    dept = str(record['department']).strip()
    role = str(record['role']).strip()

    # Employee ID format
    if not EMPLOYEE_ID_REGEX.match(emp_id):
        errors.append("Employee ID must be 1-20 alphanumeric characters (hyphens/underscores allowed).")

    # Name length
    if len(name) < 2 or len(name) > 100:
        errors.append("Name must be between 2 and 100 characters.")

    # Role length
    if len(role) < 2 or len(role) > 100:
        errors.append("Role must be between 2 and 100 characters.")

    # Department
    if dept not in VALID_DEPARTMENTS:
        errors.append(f"Invalid department '{dept}'. Must be one of: {VALID_DEPARTMENTS}")

    # Status
    status = str(record.get('status', 'Active')).strip()
    if status not in VALID_STATUSES:
        errors.append(f"Invalid status '{status}'. Must be one of: {VALID_STATUSES}")

    # Salary range
    try:
        salary = float(record['salary'])
        if salary < MIN_SALARY:
            errors.append(f"Salary must be at least ${MIN_SALARY:,}.")
        elif salary > MAX_SALARY:
            errors.append(f"Salary cannot exceed ${MAX_SALARY:,}.")
    except (ValueError, TypeError):
        errors.append(f"Invalid salary value: '{record['salary']}'")

    # Hire date — format + not in future + not unrealistically old
    hire_date_str = str(record.get('hire_date', '')).strip()
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', hire_date_str):
        errors.append(f"Invalid hire_date format '{hire_date_str}'. Expected YYYY-MM-DD.")
    else:
        try:
            hire_date_obj = datetime.strptime(hire_date_str, '%Y-%m-%d').date()
            if hire_date_obj > date.today():
                errors.append("Hire date cannot be in the future.")
            if hire_date_obj.year < 1970:
                errors.append("Hire date is unrealistically far in the past.")
        except ValueError:
            errors.append(f"Hire date '{hire_date_str}' is not a valid calendar date.")

    # Email — optional but validated if present
    email = str(record.get('email', '')).strip()
    if email and not EMAIL_REGEX.match(email):
        errors.append(f"Invalid email format: '{email}'.")

    # Phone — optional, basic length check
    phone = str(record.get('phone', '')).strip()
    if phone and (len(phone) < 7 or len(phone) > 20):
        errors.append("Phone number must be 7-20 characters.")

    if errors:
        log.warning(f"Record {record.get('employee_id')} failed validation: {errors}")
        return False, errors

    log.info(f"Record {emp_id} passed validation.")
    return True, []


def validate_batch(records: list[dict]) -> tuple[list[dict], list[dict]]:
    valid, invalid = [], []
    for record in records:
        ok, errors = validate_record(record)
        if ok:
            record['status'] = str(record.get('status', 'Active')).strip()
            valid.append(record)
        else:
            record['_errors'] = errors
            invalid.append(record)
    return valid, invalid
