import csv
import os
from validator import validate_batch
from storage import upsert_employee, log_activity
from logger import get_logger

log = get_logger('employee_manager')


def load_csv(filepath: str) -> list[dict]:
    records = []
    with open(filepath, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cleaned = {k.strip().lower(): v.strip() for k, v in row.items()}
            records.append(cleaned)
    log.info(f"Loaded {len(records)} records from {os.path.basename(filepath)}")
    return records


def process_file(filepath: str) -> dict:
    filename = os.path.basename(filepath)
    log.info(f"Processing file: {filename}")
    log_activity('FILE_RECEIVED', details=filename)

    try:
        records = load_csv(filepath)
    except Exception as e:
        log.error(f"Failed to read {filename}: {e}")
        log_activity('FILE_ERROR', details=str(e))
        return {'file': filename, 'error': str(e)}

    valid, invalid = validate_batch(records)

    results = {'file': filename, 'total': len(records), 'processed': 0, 'failed': len(invalid), 'actions': {}}

    for record in invalid:
        log.warning(f"Skipped {record.get('employee_id', 'UNKNOWN')}: {record['_errors']}")
        log_activity('VALIDATION_FAILED', record.get('employee_id'), str(record['_errors']))

    for record in valid:
        action = upsert_employee(record)
        results['actions'][action] = results['actions'].get(action, 0) + 1
        results['processed'] += 1

    log.info(f"Done: {results['processed']} processed, {results['failed']} failed.")
    log_activity('FILE_COMPLETE', details=str(results))
    return results
