import os
import sys
import uuid
import csv
import io
import subprocess
import secrets

sys.path.insert(0, os.path.dirname(__file__))

from flask import (Flask, render_template_string, request, redirect, url_for,
                   flash, send_from_directory, Response)
from storage import (initialize_db, get_all_employees, get_employee, upsert_employee,
                     delete_employee, get_employees_by_department, save_document,
                     delete_document, get_documents, get_activity_log,
                     get_next_employee_id, DEPARTMENTS, log_activity)
from validator import validate_record

app = Flask(__name__)
app.secret_key = os.environ.get('HR_SECRET_KEY', secrets.token_hex(32))

UPLOADS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'uploads'))
MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'png', 'jpg', 'jpeg', 'xlsx', 'csv'}
PER_PAGE = 20

os.makedirs(UPLOADS_DIR, exist_ok=True)


# ── helpers ──────────────────────────────────────────────────────────────────

def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def safe_filename_in_uploads(filename: str) -> bool:
    """Ensure filename exists in our uploads folder (prevents path traversal)."""
    target = os.path.abspath(os.path.join(UPLOADS_DIR, filename))
    return target.startswith(UPLOADS_DIR + os.sep) or target == UPLOADS_DIR


def push_to_github() -> tuple[bool, str]:
    try:
        repo = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        gen_script = os.path.join(os.path.dirname(__file__), 'generate_html.py')

        r = subprocess.run([sys.executable, gen_script], capture_output=True, text=True)
        if r.returncode != 0:
            return False, f"HTML generation failed: {r.stderr.strip()}"

        subprocess.run(['git', '-C', repo, 'add', 'docs/'], check=True, capture_output=True)

        r = subprocess.run(['git', '-C', repo, 'diff', '--cached', '--quiet'], capture_output=True)
        if r.returncode == 0:
            return True, "No changes to publish — dashboard is already up to date."

        subprocess.run(['git', '-C', repo, 'commit', '-m', 'Update HR dashboard [auto]'],
                       check=True, capture_output=True)
        subprocess.run(['git', '-C', repo, 'push', 'origin', 'main'],
                       check=True, capture_output=True)
        return True, "Dashboard published to GitHub Pages successfully!"
    except subprocess.CalledProcessError as e:
        return False, f"Git error: {e.stderr.strip() if e.stderr else str(e)}"
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"


# ── shared styles ─────────────────────────────────────────────────────────────

BASE_STYLE = """
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Segoe UI', sans-serif; background: #f0f4f8; color: #333; min-height: 100vh; }
nav { background: #1a73e8; color: white; padding: 14px 32px; display: flex; align-items: center; gap: 20px; flex-wrap: wrap; }
nav .brand { font-size: 1.15rem; font-weight: 700; margin-right: auto; }
nav a { color: white; text-decoration: none; font-size: 0.9rem; opacity: 0.85; padding: 4px 0; }
nav a:hover { opacity: 1; }
nav .nav-btn { background: rgba(255,255,255,0.18); padding: 6px 14px; border-radius: 6px; opacity: 1 !important; }
nav .nav-btn:hover { background: rgba(255,255,255,0.3); }
.container { max-width: 1150px; margin: 28px auto; padding: 0 20px; }
.card { background: white; border-radius: 10px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.07); margin-bottom: 22px; }
h2 { font-size: 1.25rem; margin-bottom: 18px; color: #222; }
h3 { font-size: 1.05rem; color: #444; margin-bottom: 14px; }

/* Buttons */
.btn { display: inline-block; padding: 9px 18px; border-radius: 6px; font-size: 0.9rem;
       cursor: pointer; border: none; text-decoration: none; transition: opacity .15s; }
.btn:hover { opacity: 0.85; }
.btn-primary { background: #1a73e8; color: white; }
.btn-success { background: #34a853; color: white; }
.btn-warning { background: #f9ab00; color: #333; }
.btn-danger  { background: #ea4335; color: white; }
.btn-secondary { background: #e8eaed; color: #333; }
.btn-sm { padding: 5px 11px; font-size: 0.82rem; }

/* Tables */
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
th { background: #f8f9fa; padding: 10px 12px; text-align: left; border-bottom: 2px solid #e0e0e0;
     color: #555; font-weight: 600; white-space: nowrap; }
td { padding: 9px 12px; border-bottom: 1px solid #f0f0f0; vertical-align: middle; }
tr:hover td { background: #f5f8ff; }

/* Badges */
.badge { display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 0.78rem; font-weight: 600; }
.badge-active   { background: #e6f4ea; color: #1e8e3e; }
.badge-inactive { background: #fce8e6; color: #c5221f; }
.badge-onleave  { background: #fef7e0; color: #b06000; }

/* Forms */
.form-group { margin-bottom: 15px; }
label { display: block; font-size: 0.85rem; color: #555; margin-bottom: 5px; font-weight: 500; }
input[type=text], input[type=email], input[type=number], input[type=date],
input[type=tel], input[type=search], select, textarea {
  width: 100%; padding: 9px 12px; border: 1px solid #ddd; border-radius: 6px;
  font-size: 0.93rem; background: white; }
input:focus, select:focus { outline: none; border-color: #1a73e8; box-shadow: 0 0 0 2px rgba(26,115,232,.15); }
input:invalid { border-color: #ea4335; }
.field-hint { font-size: 0.78rem; color: #888; margin-top: 3px; }
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
@media(max-width:600px) { .grid-2 { grid-template-columns: 1fr; } }

/* Alerts */
.alerts { position: sticky; top: 0; z-index: 99; }
.alert { padding: 12px 16px; border-radius: 6px; margin-bottom: 12px; font-size: 0.9rem;
         display: flex; justify-content: space-between; align-items: center; }
.alert-success { background: #e6f4ea; color: #1e6e2e; border-left: 4px solid #34a853; }
.alert-error   { background: #fce8e6; color: #a50e0e; border-left: 4px solid #ea4335; }
.alert-info    { background: #e8f0fe; color: #174ea6; border-left: 4px solid #1a73e8; }
.alert button  { background: none; border: none; cursor: pointer; font-size: 1rem; opacity: .6; }

/* Stats row */
.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 14px; margin-bottom: 22px; }
.stat { background: white; border-radius: 10px; padding: 18px 14px; text-align: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.07); }
.stat .num { font-size: 2rem; font-weight: 700; color: #1a73e8; }
.stat .lbl { color: #666; font-size: 0.82rem; margin-top: 3px; }

/* Search */
.search-bar { display: flex; gap: 10px; margin-bottom: 16px; align-items: center; flex-wrap: wrap; }
.search-bar input { flex: 1; min-width: 180px; }
.search-bar select { width: 160px; }

/* Pagination */
.pagination { display: flex; gap: 6px; justify-content: center; margin-top: 18px; flex-wrap: wrap; }
.pagination a, .pagination span { padding: 6px 12px; border-radius: 5px; font-size: 0.88rem;
  border: 1px solid #ddd; background: white; text-decoration: none; color: #333; }
.pagination a:hover { background: #e8f0fe; border-color: #1a73e8; color: #1a73e8; }
.pagination .current { background: #1a73e8; color: white; border-color: #1a73e8; }

/* Toolbar */
.toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 10px; }
.dept-tabs { display: flex; gap: 6px; flex-wrap: wrap; }
.dept-tab { padding: 6px 14px; border-radius: 20px; border: 1px solid #ddd; background: white;
            text-decoration: none; font-size: 0.85rem; color: #555; }
.dept-tab:hover, .dept-tab.active { background: #1a73e8; color: white; border-color: #1a73e8; }

/* Required asterisk */
.req { color: #ea4335; }
</style>
"""

NAV = """
<nav>
  <span class="brand">HR Dashboard</span>
  <a href="/">Home</a>
  <a href="/employees">Employees</a>
  <a href="/add">+ New Employee</a>
  <a href="/activity">Activity Log</a>
  <a href="/export" class="nav-btn">Export CSV</a>
  <a href="/publish" class="nav-btn">&#9654; Publish</a>
</nav>
"""

FLASH_BLOCK = """
{% with messages = get_flashed_messages(with_categories=true) %}
  {% if messages %}<div class="alerts">{% for cat, msg in messages %}
    <div class="alert alert-{{ cat }}"><span>{{ msg }}</span>
      <button onclick="this.parentElement.remove()">&#x2715;</button>
    </div>
  {% endfor %}</div>{% endif %}
{% endwith %}
"""


def status_badge(status: str) -> str:
    cls = {'Active': 'active', 'Inactive': 'inactive', 'On Leave': 'onleave'}.get(status, 'inactive')
    return f'<span class="badge badge-{cls}">{status}</span>'


# ── routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    all_emp = get_all_employees()
    total = len(all_emp)
    active = sum(1 for r in all_emp if r[5] == 'Active')
    on_leave = sum(1 for r in all_emp if r[5] == 'On Leave')
    inactive = sum(1 for r in all_emp if r[5] == 'Inactive')
    dept_data = {d: {'total': 0, 'active': 0} for d in DEPARTMENTS}
    for r in all_emp:
        if r[2] in dept_data:
            dept_data[r[2]]['total'] += 1
            if r[5] == 'Active':
                dept_data[r[2]]['active'] += 1
    recent = all_emp[:8]

    return render_template_string(BASE_STYLE + NAV + FLASH_BLOCK + """
    <div class="container">
      <div class="stats">
        <div class="stat"><div class="num">{{ total }}</div><div class="lbl">Total Employees</div></div>
        <div class="stat"><div class="num" style="color:#34a853">{{ active }}</div><div class="lbl">Active</div></div>
        <div class="stat"><div class="num" style="color:#f9ab00">{{ on_leave }}</div><div class="lbl">On Leave</div></div>
        <div class="stat"><div class="num" style="color:#ea4335">{{ inactive }}</div><div class="lbl">Inactive</div></div>
        {% for dept, d in dept_data.items() %}
        <div class="stat"><div class="num">{{ d.total }}</div><div class="lbl">{{ dept }}<br><small style="color:#999">{{ d.active }} active</small></div></div>
        {% endfor %}
      </div>

      <div class="card">
        <div class="toolbar">
          <h2>Recent Employees</h2>
          <a href="/employees" class="btn btn-secondary btn-sm">View All &rarr;</a>
        </div>
        <div class="table-wrap">
        <table>
          <thead><tr><th>ID</th><th>Name</th><th>Department</th><th>Role</th><th>Status</th><th>Actions</th></tr></thead>
          <tbody>
          {% for r in recent %}
          <tr>
            <td>{{ r[0] }}</td><td><strong>{{ r[1] }}</strong></td><td>{{ r[2] }}</td><td>{{ r[3] }}</td>
            <td>{{ status_badge(r[5]) | safe }}</td>
            <td>
              <a href="/edit/{{ r[0] }}" class="btn btn-warning btn-sm">Edit</a>
              <a href="/documents/{{ r[0] }}" class="btn btn-primary btn-sm">Docs</a>
            </td>
          </tr>
          {% endfor %}
          </tbody>
        </table>
        </div>
      </div>
    </div>
    """, total=total, active=active, on_leave=on_leave, inactive=inactive,
         dept_data=dept_data, recent=recent, status_badge=status_badge)


@app.route('/employees')
def employees():
    dept_filter = request.args.get('dept', 'All')
    status_filter = request.args.get('status', 'All')
    search_q = request.args.get('q', '').strip().lower()
    page = max(1, request.args.get('page', 1, type=int))

    all_emp = get_all_employees()

    # Filter
    rows = all_emp
    if dept_filter != 'All':
        rows = [r for r in rows if r[2] == dept_filter]
    if status_filter != 'All':
        rows = [r for r in rows if r[5] == status_filter]
    if search_q:
        rows = [r for r in rows if any(
            search_q in str(cell).lower() for cell in (r[0], r[1], r[2], r[3], r[7] or '')
        )]

    # Paginate
    total_rows = len(rows)
    total_pages = max(1, (total_rows + PER_PAGE - 1) // PER_PAGE)
    page = min(page, total_pages)
    offset = (page - 1) * PER_PAGE
    page_rows = rows[offset:offset + PER_PAGE]

    return render_template_string(BASE_STYLE + NAV + FLASH_BLOCK + """
    <div class="container">
      <div class="card">
        <div class="toolbar">
          <h2>Employees <span style="font-size:.9rem;color:#888;font-weight:400">({{ total_rows }} found)</span></h2>
          <a href="/add" class="btn btn-success">+ New Employee</a>
        </div>

        <form method="GET" class="search-bar">
          <input type="search" name="q" value="{{ q }}" placeholder="Search name, ID, role, email...">
          <select name="dept">
            <option value="All" {% if dept=='All' %}selected{% endif %}>All Departments</option>
            {% for d in departments %}<option {% if dept==d %}selected{% endif %}>{{ d }}</option>{% endfor %}
          </select>
          <select name="status">
            <option value="All" {% if status=='All' %}selected{% endif %}>All Statuses</option>
            <option {% if status=='Active' %}selected{% endif %}>Active</option>
            <option value="On Leave" {% if status=='On Leave' %}selected{% endif %}>On Leave</option>
            <option {% if status=='Inactive' %}selected{% endif %}>Inactive</option>
          </select>
          <button type="submit" class="btn btn-primary">Search</button>
          <a href="/employees" class="btn btn-secondary">Clear</a>
        </form>

        <div class="table-wrap">
        <table>
          <thead><tr><th>ID</th><th>Name</th><th>Department</th><th>Role</th><th>Hire Date</th>
            <th>Status</th><th>Salary</th><th>Email</th><th>Actions</th></tr></thead>
          <tbody>
          {% for r in page_rows %}
          <tr>
            <td>{{ r[0] }}</td>
            <td><strong>{{ r[1] }}</strong></td>
            <td>{{ r[2] }}</td>
            <td>{{ r[3] }}</td>
            <td>{{ r[4] }}</td>
            <td>{{ status_badge(r[5]) | safe }}</td>
            <td>${{ "{:,.0f}".format(r[6]) }}</td>
            <td>{{ r[7] or '-' }}</td>
            <td style="white-space:nowrap">
              <a href="/edit/{{ r[0] }}" class="btn btn-warning btn-sm">Edit</a>
              <a href="/documents/{{ r[0] }}" class="btn btn-primary btn-sm">Docs</a>
              <a href="/delete/{{ r[0] }}" class="btn btn-danger btn-sm"
                 onclick="return confirm('Permanently delete {{ r[1] }}? This cannot be undone.')">Del</a>
            </td>
          </tr>
          {% endfor %}
          {% if not page_rows %}
          <tr><td colspan="9" style="text-align:center;color:#999;padding:30px">No employees found.</td></tr>
          {% endif %}
          </tbody>
        </table>
        </div>

        {% if total_pages > 1 %}
        <div class="pagination">
          {% if page > 1 %}<a href="?q={{ q }}&dept={{ dept }}&status={{ status }}&page={{ page-1 }}">&laquo; Prev</a>{% endif %}
          {% for p in range(1, total_pages+1) %}
            {% if p == page %}<span class="current">{{ p }}</span>
            {% elif p == 1 or p == total_pages or (p >= page-2 and p <= page+2) %}
              <a href="?q={{ q }}&dept={{ dept }}&status={{ status }}&page={{ p }}">{{ p }}</a>
            {% elif p == page-3 or p == page+3 %}<span>…</span>{% endif %}
          {% endfor %}
          {% if page < total_pages %}<a href="?q={{ q }}&dept={{ dept }}&status={{ status }}&page={{ page+1 }}">Next &raquo;</a>{% endif %}
        </div>
        {% endif %}
      </div>
    </div>
    """, page_rows=page_rows, total_rows=total_rows, total_pages=total_pages,
         page=page, q=search_q, dept=dept_filter, status=status_filter,
         departments=DEPARTMENTS, status_badge=status_badge)


@app.route('/add', methods=['GET', 'POST'])
def add_employee():
    suggested_id = get_next_employee_id()

    if request.method == 'POST':
        record = {
            'employee_id': request.form.get('employee_id', '').strip(),
            'name':        request.form.get('name', '').strip(),
            'department':  request.form.get('department', ''),
            'role':        request.form.get('role', '').strip(),
            'hire_date':   request.form.get('hire_date', ''),
            'status':      request.form.get('status', 'Active'),
            'salary':      request.form.get('salary', ''),
            'email':       request.form.get('email', '').strip(),
            'phone':       request.form.get('phone', '').strip(),
        }

        # Check duplicate ID
        if get_employee(record['employee_id']):
            flash(f"Employee ID '{record['employee_id']}' already exists. Choose a different ID.", 'error')
            return render_template_string(_add_form_html(), record=record,
                                          departments=DEPARTMENTS, suggested_id=suggested_id)

        ok, errors = validate_record(record)
        if not ok:
            for e in errors:
                flash(e, 'error')
            return render_template_string(_add_form_html(), record=record,
                                          departments=DEPARTMENTS, suggested_id=suggested_id)

        upsert_employee(record)
        flash(f"Employee {record['name']} ({record['employee_id']}) added successfully!", 'success')
        return redirect(url_for('employees'))

    return render_template_string(_add_form_html(), record={}, departments=DEPARTMENTS,
                                   suggested_id=suggested_id)


def _add_form_html():
    return BASE_STYLE + NAV + FLASH_BLOCK + """
    <div class="container">
      <div class="card" style="max-width:750px;margin:0 auto">
        <h2>Add New Employee</h2>
        <form method="POST" novalidate>
          <div class="grid-2">
            <div class="form-group">
              <label>Employee ID <span class="req">*</span></label>
              <input name="employee_id" value="{{ record.get('employee_id', suggested_id) }}"
                     placeholder="{{ suggested_id }}" required maxlength="20">
              <div class="field-hint">Suggested: {{ suggested_id }}</div>
            </div>
            <div class="form-group">
              <label>Full Name <span class="req">*</span></label>
              <input name="name" value="{{ record.get('name','') }}" placeholder="e.g. Jane Doe" required minlength="2" maxlength="100">
            </div>
            <div class="form-group">
              <label>Department <span class="req">*</span></label>
              <select name="department" required>
                {% for d in departments %}
                <option {% if record.get('department')==d %}selected{% endif %}>{{ d }}</option>
                {% endfor %}
              </select>
            </div>
            <div class="form-group">
              <label>Role / Job Title <span class="req">*</span></label>
              <input name="role" value="{{ record.get('role','') }}" placeholder="e.g. Sales Manager" required minlength="2" maxlength="100">
            </div>
            <div class="form-group">
              <label>Hire Date <span class="req">*</span></label>
              <input name="hire_date" type="date" value="{{ record.get('hire_date','') }}" required max="{{ today }}">
            </div>
            <div class="form-group">
              <label>Status <span class="req">*</span></label>
              <select name="status">
                <option {% if record.get('status','Active')=='Active' %}selected{% endif %}>Active</option>
                <option {% if record.get('status')=='On Leave' %}selected{% endif %}>On Leave</option>
                <option {% if record.get('status')=='Inactive' %}selected{% endif %}>Inactive</option>
              </select>
            </div>
            <div class="form-group">
              <label>Salary (USD) <span class="req">*</span></label>
              <input name="salary" type="number" value="{{ record.get('salary','') }}"
                     placeholder="e.g. 55000" required min="15000" max="1000000">
              <div class="field-hint">Range: $15,000 – $1,000,000</div>
            </div>
            <div class="form-group">
              <label>Email</label>
              <input name="email" type="email" value="{{ record.get('email','') }}" placeholder="jane@company.com">
            </div>
            <div class="form-group">
              <label>Phone</label>
              <input name="phone" type="tel" value="{{ record.get('phone','') }}" placeholder="555-0000" maxlength="20">
            </div>
          </div>
          <div style="display:flex;gap:10px;margin-top:6px">
            <button type="submit" class="btn btn-success">Save Employee</button>
            <a href="/employees" class="btn btn-secondary">Cancel</a>
          </div>
        </form>
      </div>
    </div>
    """ + _today_script()


def _today_script():
    from datetime import date
    return f"<script>document.querySelectorAll('input[type=date]').forEach(i=>{{if(!i.value)i.max='{date.today()}';}});</script>"


@app.route('/edit/<employee_id>', methods=['GET', 'POST'])
def edit_employee(employee_id):
    emp = get_employee(employee_id)
    if not emp:
        flash('Employee not found.', 'error')
        return redirect(url_for('employees'))

    if request.method == 'POST':
        record = {
            'employee_id': employee_id,
            'name':        request.form.get('name', '').strip(),
            'department':  request.form.get('department', ''),
            'role':        request.form.get('role', '').strip(),
            'hire_date':   request.form.get('hire_date', ''),
            'status':      request.form.get('status', 'Active'),
            'salary':      request.form.get('salary', ''),
            'email':       request.form.get('email', '').strip(),
            'phone':       request.form.get('phone', '').strip(),
        }

        ok, errors = validate_record(record)
        if not ok:
            for e in errors:
                flash(e, 'error')
            return render_template_string(_edit_form_html(), emp=list(emp),
                                          record=record, departments=DEPARTMENTS)

        upsert_employee(record)
        flash(f"{record['name']}'s record updated successfully!", 'success')
        return redirect(url_for('employees'))

    return render_template_string(_edit_form_html(), emp=emp, record={}, departments=DEPARTMENTS)


def _edit_form_html():
    return BASE_STYLE + NAV + FLASH_BLOCK + """
    <div class="container">
      <div class="card" style="max-width:750px;margin:0 auto">
        <h2>Edit Employee — {{ emp[1] }}</h2>
        <form method="POST" novalidate>
          <div class="grid-2">
            <div class="form-group">
              <label>Employee ID</label>
              <input value="{{ emp[0] }}" disabled style="background:#f5f5f5;color:#888">
            </div>
            <div class="form-group">
              <label>Full Name <span class="req">*</span></label>
              <input name="name" value="{{ record.get('name', emp[1]) }}" required minlength="2" maxlength="100">
            </div>
            <div class="form-group">
              <label>Department <span class="req">*</span></label>
              <select name="department" required>
                {% for d in departments %}
                <option {% if (record.get('department') or emp[2])==d %}selected{% endif %}>{{ d }}</option>
                {% endfor %}
              </select>
            </div>
            <div class="form-group">
              <label>Role / Job Title <span class="req">*</span></label>
              <input name="role" value="{{ record.get('role', emp[3]) }}" required minlength="2" maxlength="100">
            </div>
            <div class="form-group">
              <label>Hire Date <span class="req">*</span></label>
              <input name="hire_date" type="date" value="{{ record.get('hire_date', emp[4]) }}" required>
            </div>
            <div class="form-group">
              <label>Status <span class="req">*</span></label>
              <select name="status">
                {% set cur = record.get('status') or emp[5] %}
                <option {% if cur=='Active' %}selected{% endif %}>Active</option>
                <option value="On Leave" {% if cur=='On Leave' %}selected{% endif %}>On Leave</option>
                <option {% if cur=='Inactive' %}selected{% endif %}>Inactive</option>
              </select>
            </div>
            <div class="form-group">
              <label>Salary (USD) <span class="req">*</span></label>
              <input name="salary" type="number" value="{{ record.get('salary', emp[6]|int) }}"
                     required min="15000" max="1000000">
              <div class="field-hint">Range: $15,000 – $1,000,000</div>
            </div>
            <div class="form-group">
              <label>Email</label>
              <input name="email" type="email" value="{{ record.get('email', emp[7] or '') }}">
            </div>
            <div class="form-group">
              <label>Phone</label>
              <input name="phone" type="tel" value="{{ record.get('phone', emp[8] or '') }}" maxlength="20">
            </div>
          </div>
          <div style="display:flex;gap:10px;margin-top:6px">
            <button type="submit" class="btn btn-success">Update Record</button>
            <a href="/documents/{{ emp[0] }}" class="btn btn-primary">Manage Docs</a>
            <a href="/employees" class="btn btn-secondary">Cancel</a>
          </div>
        </form>
      </div>
    </div>
    """


@app.route('/delete/<employee_id>')
def delete(employee_id):
    emp = get_employee(employee_id)
    if emp:
        log_activity('DELETE', employee_id, f"Deleted: {emp[1]} | {emp[2]} | {emp[3]}")
        delete_employee(employee_id)
        flash(f"Employee {emp[1]} ({employee_id}) has been deleted.", 'success')
    else:
        flash('Employee not found.', 'error')
    return redirect(url_for('employees'))


@app.route('/documents/<employee_id>', methods=['GET', 'POST'])
def documents(employee_id):
    emp = get_employee(employee_id)
    if not emp:
        flash('Employee not found.', 'error')
        return redirect(url_for('employees'))

    if request.method == 'POST':
        file = request.files.get('document')
        if not file or file.filename == '':
            flash('No file selected.', 'error')
        elif not allowed_file(file.filename):
            flash(f"File type not allowed. Accepted: {', '.join(sorted(ALLOWED_EXTENSIONS)).upper()}", 'error')
        else:
            # Check file size
            file.seek(0, 2)
            size = file.tell()
            file.seek(0)
            if size > MAX_FILE_BYTES:
                flash(f"File too large. Maximum size is {MAX_FILE_BYTES // (1024*1024)} MB.", 'error')
            else:
                ext = file.filename.rsplit('.', 1)[1].lower()
                unique_name = f"{employee_id}_{uuid.uuid4().hex}.{ext}"
                save_path = os.path.join(UPLOADS_DIR, unique_name)
                try:
                    file.save(save_path)
                    save_document(employee_id, unique_name, file.filename)
                    log_activity('DOCUMENT_UPLOAD', employee_id, file.filename)
                    flash(f"'{file.filename}' uploaded successfully!", 'success')
                except Exception as e:
                    if os.path.exists(save_path):
                        os.remove(save_path)
                    flash(f"Upload failed: {str(e)}", 'error')
        return redirect(url_for('documents', employee_id=employee_id))

    docs = get_documents(employee_id)
    return render_template_string(BASE_STYLE + NAV + FLASH_BLOCK + """
    <div class="container">
      <div class="card" style="max-width:800px;margin:0 auto">
        <div class="toolbar">
          <div>
            <h2>Documents — {{ emp[1] }}</h2>
            <div style="color:#666;font-size:.88rem;margin-top:2px">{{ emp[2] }} &bull; {{ emp[3] }} &bull; {{ status_badge(emp[5]) | safe }}</div>
          </div>
          <a href="/edit/{{ emp[0] }}" class="btn btn-warning btn-sm">Edit Employee</a>
        </div>

        <form method="POST" enctype="multipart/form-data"
              style="background:#f8f9fa;border-radius:8px;padding:16px;margin-bottom:20px">
          <label style="font-weight:600;margin-bottom:8px;display:block">Upload Document</label>
          <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
            <input type="file" name="document" style="flex:1;min-width:200px"
                   accept=".pdf,.doc,.docx,.png,.jpg,.jpeg,.xlsx,.csv">
            <button type="submit" class="btn btn-primary">Upload</button>
          </div>
          <div class="field-hint" style="margin-top:6px">
            Allowed: PDF, DOC, DOCX, PNG, JPG, XLSX, CSV &bull; Max 10 MB
          </div>
        </form>

        {% if docs %}
        <div class="table-wrap">
        <table>
          <thead><tr><th>File Name</th><th>Uploaded At</th><th style="text-align:center">Actions</th></tr></thead>
          <tbody>
          {% for d in docs %}
          <tr>
            <td>{{ d[3] }}</td>
            <td>{{ d[4][:19] }}</td>
            <td style="text-align:center">
              <a href="/download/{{ d[2] }}" class="btn btn-success btn-sm">&#8595; Download</a>
              <a href="/delete-doc/{{ d[0] }}/{{ employee_id }}" class="btn btn-danger btn-sm"
                 onclick="return confirm('Delete this document?')">Delete</a>
            </td>
          </tr>
          {% endfor %}
          </tbody>
        </table>
        </div>
        {% else %}
        <p style="text-align:center;color:#999;padding:30px">No documents uploaded yet.</p>
        {% endif %}

        <div style="margin-top:16px">
          <a href="/employees" class="btn btn-secondary">&#8592; Back to Employees</a>
        </div>
      </div>
    </div>
    """, emp=emp, docs=docs, employee_id=employee_id, status_badge=status_badge)


@app.route('/delete-doc/<int:doc_id>/<employee_id>')
def delete_doc(doc_id, employee_id):
    deleted = delete_document(doc_id, UPLOADS_DIR)
    if deleted:
        log_activity('DOCUMENT_DELETE', employee_id, f"Doc ID {doc_id}")
        flash('Document deleted.', 'success')
    else:
        flash('Document not found.', 'error')
    return redirect(url_for('documents', employee_id=employee_id))


@app.route('/download/<filename>')
def download(filename):
    # Prevent path traversal — only serve files recorded in DB
    if not safe_filename_in_uploads(filename):
        flash('Invalid file request.', 'error')
        return redirect(url_for('index'))
    full_path = os.path.join(UPLOADS_DIR, filename)
    if not os.path.exists(full_path):
        flash('File not found.', 'error')
        return redirect(url_for('index'))
    return send_from_directory(UPLOADS_DIR, filename, as_attachment=True)


@app.route('/activity')
def activity():
    page = max(1, request.args.get('page', 1, type=int))
    logs, total = get_activity_log(page=page, per_page=30)
    total_pages = max(1, (total + 29) // 30)

    return render_template_string(BASE_STYLE + NAV + FLASH_BLOCK + """
    <div class="container">
      <div class="card">
        <h2>Activity Log <span style="font-size:.88rem;color:#888;font-weight:400">({{ total }} entries)</span></h2>
        <div class="table-wrap">
        <table>
          <thead><tr><th>Timestamp</th><th>Action</th><th>Employee ID</th><th>Details</th></tr></thead>
          <tbody>
          {% for row in logs %}
          <tr>
            <td style="white-space:nowrap;color:#666;font-size:.85rem">{{ row[1][:19] }}</td>
            <td><strong>{{ row[2] }}</strong></td>
            <td>{{ row[3] or '-' }}</td>
            <td style="color:#555;font-size:.88rem">{{ row[4] or '-' }}</td>
          </tr>
          {% endfor %}
          {% if not logs %}
          <tr><td colspan="4" style="text-align:center;color:#999;padding:30px">No activity yet.</td></tr>
          {% endif %}
          </tbody>
        </table>
        </div>
        {% if total_pages > 1 %}
        <div class="pagination">
          {% if page > 1 %}<a href="?page={{ page-1 }}">&laquo;</a>{% endif %}
          {% for p in range(1, total_pages+1) %}
            {% if p == page %}<span class="current">{{ p }}</span>
            {% elif p == 1 or p == total_pages or (p >= page-2 and p <= page+2) %}
              <a href="?page={{ p }}">{{ p }}</a>
            {% elif p == page-3 or p == page+3 %}<span>…</span>{% endif %}
          {% endfor %}
          {% if page < total_pages %}<a href="?page={{ page+1 }}">&raquo;</a>{% endif %}
        </div>
        {% endif %}
      </div>
    </div>
    """, logs=logs, total=total, page=page, total_pages=total_pages)


@app.route('/export')
def export():
    rows = get_all_employees()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Name', 'Department', 'Role', 'Hire Date', 'Status',
                     'Salary', 'Email', 'Phone', 'Created At', 'Updated At'])
    writer.writerows(rows)
    output.seek(0)
    from datetime import date
    filename = f"hr_employees_{date.today()}.csv"
    return Response(output.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': f'attachment; filename={filename}'})


@app.route('/publish')
def publish():
    ok, message = push_to_github()
    flash(message, 'success' if ok else 'error')
    return redirect(url_for('index'))


if __name__ == '__main__':
    initialize_db()
    print("\n  HR Admin Panel  ->  http://localhost:5000\n")
    app.run(debug=True, port=5000)
