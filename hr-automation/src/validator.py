from logger import get_logger

log = get_logger('validator')

REQUIRED_FIELDS = ['employee_id', 'name', 'department', 'role', 'hire_date', 'salary']
VALID_DEPARTMENTS = ['Sales', 'Finance', 'Operations']
VALID_STATUSES = ['Active', 'Inactive', 'On Leave']


def validate_record(record: dict) -> tuple[bool, list[str]]:
    errors = []

    # Check required fields
    for field in REQUIRED_FIELDS:
        value = record.get(field)
        if value is None or str(value).strip() == '':
            errors.append(f"Missing required field: '{field}'")

    if errors:
        log.warning(f"Record {record.get('employee_id', 'UNKNOWN')} failed validation: {errors}")
        return False, errors

    # Validate department
    dept = str(record['department']).strip()
    if dept not in VALID_DEPARTMENTS:
        errors.append(f"Invalid department '{dept}'. Must be one of: {VALID_DEPARTMENTS}")

    # Validate salary
    try:
        salary = float(record['salary'])
        if salary < 0:
            errors.append("Salary cannot be negative.")
    except (ValueError, TypeError):
        errors.append(f"Invalid salary value: '{record['salary']}'")

    # Validate status if present
    status = record.get('status', 'Active')
    if str(status).strip() not in VALID_STATUSES:
        errors.append(f"Invalid status '{status}'. Must be one of: {VALID_STATUSES}")

    # Validate hire_date format (YYYY-MM-DD)
    import re
    hire_date = str(record.get('hire_date', '')).strip()
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', hire_date):
        errors.append(f"Invalid hire_date format '{hire_date}'. Expected YYYY-MM-DD.")

    if errors:
        log.warning(f"Record {record.get('employee_id')} failed validation: {errors}")
        return False, errors

    log.info(f"Record {record['employee_id']} passed validation.")
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
