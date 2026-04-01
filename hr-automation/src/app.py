import os
import sys
import uuid
import subprocess

sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, render_template_string, request, redirect, url_for, flash, send_from_directory
from storage import (initialize_db, get_all_employees, get_employee, upsert_employee,
                     delete_employee, get_employees_by_department, save_document,
                     get_documents, DEPARTMENTS, log_activity)

app = Flask(__name__)
app.secret_key = 'hr-secret-key-2024'

UPLOADS_DIR = os.path.join(os.path.dirname(__file__), '..', 'uploads')
os.makedirs(UPLOADS_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'png', 'jpg', 'jpeg', 'xlsx', 'csv'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def push_to_github():
    try:
        repo = os.path.join(os.path.dirname(__file__), '..', '..')
        subprocess.run(['python', os.path.join(os.path.dirname(__file__), 'generate_html.py')], check=True)
        subprocess.run(['git', '-C', repo, 'add', 'docs/'], check=True)
        subprocess.run(['git', '-C', repo, 'commit', '-m', 'Update HR dashboard'], check=True)
        subprocess.run(['git', '-C', repo, 'push', 'origin', 'main'], check=True)
        return True
    except Exception as e:
        return False

BASE_STYLE = """
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Segoe UI', sans-serif; background: #f0f4f8; color: #333; }
nav { background: #1a73e8; color: white; padding: 14px 40px; display: flex; align-items: center; gap: 24px; }
nav a { color: white; text-decoration: none; font-size: 0.95rem; opacity: 0.85; }
nav a:hover, nav a.active { opacity: 1; font-weight: 600; }
nav .brand { font-size: 1.2rem; font-weight: 700; margin-right: auto; }
.container { max-width: 1100px; margin: 30px auto; padding: 0 20px; }
.card { background: white; border-radius: 10px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.07); margin-bottom: 24px; }
h2 { font-size: 1.3rem; margin-bottom: 20px; color: #333; }
.btn { display: inline-block; padding: 9px 18px; border-radius: 6px; font-size: 0.9rem; cursor: pointer; border: none; text-decoration: none; }
.btn-primary { background: #1a73e8; color: white; }
.btn-success { background: #34a853; color: white; }
.btn-warning { background: #fbbc04; color: #333; }
.btn-danger { background: #ea4335; color: white; }
.btn:hover { opacity: 0.88; }
.btn-sm { padding: 5px 12px; font-size: 0.82rem; }
table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
th { background: #f8f9fa; padding: 10px 12px; text-align: left; border-bottom: 2px solid #e0e0e0; color: #555; }
td { padding: 10px 12px; border-bottom: 1px solid #f0f0f0; }
tr:hover td { background: #f8f9ff; }
.badge { padding: 3px 10px; border-radius: 12px; font-size: 0.8rem; font-weight: 600; }
.badge-active { background: #e6f4ea; color: #34a853; }
.badge-inactive { background: #fce8e6; color: #ea4335; }
.badge-leave { background: #fef7e0; color: #f9ab00; }
.form-group { margin-bottom: 16px; }
label { display: block; font-size: 0.88rem; color: #555; margin-bottom: 5px; font-weight: 500; }
input, select { width: 100%; padding: 9px 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 0.95rem; }
input:focus, select:focus { outline: none; border-color: #1a73e8; }
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.alert { padding: 12px 16px; border-radius: 6px; margin-bottom: 16px; font-size: 0.9rem; }
.alert-success { background: #e6f4ea; color: #2d7a3a; }
.alert-error { background: #fce8e6; color: #c0392b; }
.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 16px; margin-bottom: 24px; }
.stat { background: white; border-radius: 10px; padding: 20px; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.07); }
.stat h3 { font-size: 2rem; color: #1a73e8; }
.stat p { color: #666; font-size: 0.85rem; margin-top: 4px; }
</style>
"""

NAV = """
<nav>
  <span class="brand">HR Dashboard</span>
  <a href="/">Home</a>
  <a href="/employees">Employees</a>
  <a href="/add">+ Add Employee</a>
  <a href="/publish" style="background:rgba(255,255,255,0.2); padding:7px 14px; border-radius:6px;">Publish to GitHub</a>
</nav>
"""

@app.route('/')
def index():
    all_emp = get_all_employees()
    total = len(all_emp)
    active = sum(1 for r in all_emp if r[5] == 'Active')
    on_leave = sum(1 for r in all_emp if r[5] == 'On Leave')
    dept_counts = {d: len([r for r in all_emp if r[2] == d]) for d in DEPARTMENTS}

    return render_template_string(BASE_STYLE + NAV + """
    <div class="container">
      {% with messages = get_flashed_messages(with_categories=true) %}
        {% for cat, msg in messages %}
          <div class="alert alert-{{ cat }}">{{ msg }}</div>
        {% endfor %}
      {% endwith %}

      <div class="stats">
        <div class="stat"><h3>{{ total }}</h3><p>Total Employees</p></div>
        <div class="stat"><h3 style="color:#34a853">{{ active }}</h3><p>Active</p></div>
        <div class="stat"><h3 style="color:#f9ab00">{{ on_leave }}</h3><p>On Leave</p></div>
        {% for dept, count in dept_counts.items() %}
        <div class="stat"><h3>{{ count }}</h3><p>{{ dept }}</p></div>
        {% endfor %}
      </div>

      <div class="card">
        <h2>Recent Employees</h2>
        <table>
          <thead><tr><th>ID</th><th>Name</th><th>Department</th><th>Role</th><th>Status</th><th>Actions</th></tr></thead>
          <tbody>
          {% for r in employees %}
          <tr>
            <td>{{ r[0] }}</td><td>{{ r[1] }}</td><td>{{ r[2] }}</td><td>{{ r[3] }}</td>
            <td><span class="badge badge-{{ r[5].lower().replace(' ','') }}">{{ r[5] }}</span></td>
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
    """, total=total, active=active, on_leave=on_leave,
         dept_counts=dept_counts, employees=all_emp[:10])


@app.route('/employees')
def employees():
    dept_filter = request.args.get('dept', 'All')
    all_emp = get_all_employees()
    if dept_filter != 'All':
        rows = [r for r in all_emp if r[2] == dept_filter]
    else:
        rows = all_emp

    return render_template_string(BASE_STYLE + NAV + """
    <div class="container">
      <div class="card">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
          <h2>All Employees ({{ rows|length }})</h2>
          <a href="/add" class="btn btn-primary">+ Add Employee</a>
        </div>
        <div style="margin-bottom:16px; display:flex; gap:8px; flex-wrap:wrap;">
          <a href="/employees" class="btn btn-sm {% if dept=='All' %}btn-primary{% else %}btn-warning{% endif %}">All</a>
          {% for d in departments %}
          <a href="/employees?dept={{ d }}" class="btn btn-sm {% if dept==d %}btn-primary{% else %}btn-warning{% endif %}">{{ d }}</a>
          {% endfor %}
        </div>
        <table>
          <thead><tr><th>ID</th><th>Name</th><th>Dept</th><th>Role</th><th>Hire Date</th><th>Status</th><th>Salary</th><th>Actions</th></tr></thead>
          <tbody>
          {% for r in rows %}
          <tr>
            <td>{{ r[0] }}</td><td>{{ r[1] }}</td><td>{{ r[2] }}</td><td>{{ r[3] }}</td>
            <td>{{ r[4] }}</td>
            <td><span class="badge badge-{{ r[5].lower().replace(' ','') }}">{{ r[5] }}</span></td>
            <td>${{ "{:,.0f}".format(r[6]) }}</td>
            <td>
              <a href="/edit/{{ r[0] }}" class="btn btn-warning btn-sm">Edit</a>
              <a href="/documents/{{ r[0] }}" class="btn btn-primary btn-sm">Docs</a>
              <a href="/delete/{{ r[0] }}" class="btn btn-danger btn-sm" onclick="return confirm('Delete this employee?')">Del</a>
            </td>
          </tr>
          {% endfor %}
          </tbody>
        </table>
      </div>
    </div>
    """, rows=rows, dept=dept_filter, departments=DEPARTMENTS)


@app.route('/add', methods=['GET', 'POST'])
def add_employee():
    if request.method == 'POST':
        record = {
            'employee_id': request.form['employee_id'].strip(),
            'name': request.form['name'].strip(),
            'department': request.form['department'],
            'role': request.form['role'].strip(),
            'hire_date': request.form['hire_date'],
            'status': request.form['status'],
            'salary': request.form['salary'],
            'email': request.form.get('email', '').strip(),
            'phone': request.form.get('phone', '').strip(),
        }
        upsert_employee(record)
        flash(f"Employee {record['name']} added successfully!", 'success')
        return redirect(url_for('employees'))

    return render_template_string(BASE_STYLE + NAV + """
    <div class="container">
      <div class="card" style="max-width:700px; margin:0 auto;">
        <h2>Add New Employee</h2>
        <form method="POST">
          <div class="grid-2">
            <div class="form-group">
              <label>Employee ID *</label>
              <input name="employee_id" placeholder="e.g. E011" required>
            </div>
            <div class="form-group">
              <label>Full Name *</label>
              <input name="name" placeholder="Full name" required>
            </div>
            <div class="form-group">
              <label>Department *</label>
              <select name="department" required>
                {% for d in departments %}<option>{{ d }}</option>{% endfor %}
              </select>
            </div>
            <div class="form-group">
              <label>Role *</label>
              <input name="role" placeholder="Job title" required>
            </div>
            <div class="form-group">
              <label>Hire Date *</label>
              <input name="hire_date" type="date" required>
            </div>
            <div class="form-group">
              <label>Status *</label>
              <select name="status">
                <option>Active</option>
                <option>Inactive</option>
                <option>On Leave</option>
              </select>
            </div>
            <div class="form-group">
              <label>Salary *</label>
              <input name="salary" type="number" placeholder="e.g. 55000" required>
            </div>
            <div class="form-group">
              <label>Email</label>
              <input name="email" type="email" placeholder="email@company.com">
            </div>
            <div class="form-group">
              <label>Phone</label>
              <input name="phone" placeholder="555-0000">
            </div>
          </div>
          <button type="submit" class="btn btn-success">Save Employee</button>
          <a href="/employees" class="btn btn-warning" style="margin-left:8px;">Cancel</a>
        </form>
      </div>
    </div>
    """, departments=DEPARTMENTS)


@app.route('/edit/<employee_id>', methods=['GET', 'POST'])
def edit_employee(employee_id):
    emp = get_employee(employee_id)
    if not emp:
        flash('Employee not found.', 'error')
        return redirect(url_for('employees'))

    if request.method == 'POST':
        record = {
            'employee_id': employee_id,
            'name': request.form['name'].strip(),
            'department': request.form['department'],
            'role': request.form['role'].strip(),
            'hire_date': request.form['hire_date'],
            'status': request.form['status'],
            'salary': request.form['salary'],
            'email': request.form.get('email', '').strip(),
            'phone': request.form.get('phone', '').strip(),
        }
        upsert_employee(record)
        flash(f"{record['name']}'s record updated successfully!", 'success')
        return redirect(url_for('employees'))

    return render_template_string(BASE_STYLE + NAV + """
    <div class="container">
      <div class="card" style="max-width:700px; margin:0 auto;">
        <h2>Edit Employee — {{ emp[1] }}</h2>
        <form method="POST">
          <div class="grid-2">
            <div class="form-group">
              <label>Employee ID</label>
              <input value="{{ emp[0] }}" disabled style="background:#f5f5f5;">
            </div>
            <div class="form-group">
              <label>Full Name *</label>
              <input name="name" value="{{ emp[1] }}" required>
            </div>
            <div class="form-group">
              <label>Department *</label>
              <select name="department" required>
                {% for d in departments %}
                <option {% if d == emp[2] %}selected{% endif %}>{{ d }}</option>
                {% endfor %}
              </select>
            </div>
            <div class="form-group">
              <label>Role *</label>
              <input name="role" value="{{ emp[3] }}" required>
            </div>
            <div class="form-group">
              <label>Hire Date *</label>
              <input name="hire_date" type="date" value="{{ emp[4] }}" required>
            </div>
            <div class="form-group">
              <label>Status *</label>
              <select name="status">
                <option {% if emp[5]=='Active' %}selected{% endif %}>Active</option>
                <option {% if emp[5]=='Inactive' %}selected{% endif %}>Inactive</option>
                <option {% if emp[5]=='On Leave' %}selected{% endif %}>On Leave</option>
              </select>
            </div>
            <div class="form-group">
              <label>Salary *</label>
              <input name="salary" type="number" value="{{ emp[6] }}" required>
            </div>
            <div class="form-group">
              <label>Email</label>
              <input name="email" type="email" value="{{ emp[7] or '' }}">
            </div>
            <div class="form-group">
              <label>Phone</label>
              <input name="phone" value="{{ emp[8] or '' }}">
            </div>
          </div>
          <button type="submit" class="btn btn-success">Update Record</button>
          <a href="/employees" class="btn btn-warning" style="margin-left:8px;">Cancel</a>
        </form>
      </div>
    </div>
    """, emp=emp, departments=DEPARTMENTS)


@app.route('/delete/<employee_id>')
def delete(employee_id):
    delete_employee(employee_id)
    flash('Employee deleted.', 'success')
    return redirect(url_for('employees'))


@app.route('/documents/<employee_id>', methods=['GET', 'POST'])
def documents(employee_id):
    emp = get_employee(employee_id)
    if not emp:
        flash('Employee not found.', 'error')
        return redirect(url_for('employees'))

    if request.method == 'POST':
        file = request.files.get('document')
        if file and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            unique_name = f"{employee_id}_{uuid.uuid4().hex[:8]}.{ext}"
            file.save(os.path.join(UPLOADS_DIR, unique_name))
            save_document(employee_id, unique_name, file.filename)
            log_activity('DOCUMENT_UPLOAD', employee_id, file.filename)
            flash(f"Document '{file.filename}' uploaded successfully!", 'success')
        else:
            flash('Invalid file type. Allowed: PDF, DOC, DOCX, PNG, JPG, XLSX, CSV', 'error')
        return redirect(url_for('documents', employee_id=employee_id))

    docs = get_documents(employee_id)
    return render_template_string(BASE_STYLE + NAV + """
    <div class="container">
      <div class="card" style="max-width:750px; margin:0 auto;">
        <h2>Documents — {{ emp[1] }} ({{ emp[0] }})</h2>
        <p style="color:#666; margin-bottom:20px;">Department: {{ emp[2] }} | Role: {{ emp[3] }}</p>

        <form method="POST" enctype="multipart/form-data" style="margin-bottom:24px; padding:16px; background:#f8f9fa; border-radius:8px;">
          <label style="display:block; margin-bottom:8px; font-weight:600;">Upload Document</label>
          <div style="display:flex; gap:10px; align-items:center;">
            <input type="file" name="document" accept=".pdf,.doc,.docx,.png,.jpg,.jpeg,.xlsx,.csv" style="flex:1;">
            <button type="submit" class="btn btn-primary">Upload</button>
          </div>
          <small style="color:#999; margin-top:6px; display:block;">Allowed: PDF, DOC, DOCX, PNG, JPG, XLSX, CSV</small>
        </form>

        {% with messages = get_flashed_messages(with_categories=true) %}
          {% for cat, msg in messages %}
            <div class="alert alert-{{ cat }}">{{ msg }}</div>
          {% endfor %}
        {% endwith %}

        {% if docs %}
        <table>
          <thead><tr><th>File Name</th><th>Uploaded At</th><th>Download</th></tr></thead>
          <tbody>
          {% for d in docs %}
          <tr>
            <td>{{ d[3] }}</td>
            <td>{{ d[4][:19] }}</td>
            <td><a href="/download/{{ d[2] }}" class="btn btn-success btn-sm">Download</a></td>
          </tr>
          {% endfor %}
          </tbody>
        </table>
        {% else %}
        <p style="color:#999; text-align:center; padding:30px;">No documents uploaded yet.</p>
        {% endif %}

        <br><a href="/employees" class="btn btn-warning">Back to Employees</a>
      </div>
    </div>
    """, emp=emp, docs=docs)


@app.route('/download/<filename>')
def download(filename):
    return send_from_directory(UPLOADS_DIR, filename, as_attachment=True)


@app.route('/publish')
def publish():
    success = push_to_github()
    if success:
        flash('Dashboard published to GitHub Pages successfully!', 'success')
    else:
        flash('Failed to publish. Check your git credentials.', 'error')
    return redirect(url_for('index'))


if __name__ == '__main__':
    initialize_db()
    print("\n HR Admin Panel running at: http://localhost:5000\n")
    app.run(debug=True, port=5000)
