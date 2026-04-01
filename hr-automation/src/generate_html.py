import os
import sys
from html import escape
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from storage import get_all_employees, get_employees_by_department, DEPARTMENTS, DB_PATH

DOCS_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'docs')
OUTPUT = os.path.join(DOCS_DIR, 'index.html')


def fetch_summary():
    all_rows = get_all_employees()
    summary = {'total': len(all_rows), 'active': 0}
    for dept in DEPARTMENTS:
        rows = [r for r in all_rows if r[2] == dept]
        active = [r for r in rows if r[5] == 'Active']
        summary[dept] = {'total': len(rows), 'active': len(active)}
        summary['active'] += len(active)
    return summary, all_rows


def rows_to_html_table(rows, table_id):
    if not rows:
        return '<p class="no-data">No employees found.</p>'
    html = f'<table id="{table_id}"><thead><tr>'
    headers = ['ID', 'Name', 'Department', 'Role', 'Hire Date', 'Status', 'Salary', 'Email', 'Phone']
    for h in headers:
        html += f'<th>{h}</th>'
    html += '</tr></thead><tbody>'
    for r in rows:
        status_class = 'active' if r[5] == 'Active' else ('leave' if r[5] == 'On Leave' else 'inactive')
        salary = f"${float(r[6]):,.0f}" if r[6] else '-'
        html += f'''<tr>
            <td>{escape(str(r[0]))}</td>
            <td>{escape(str(r[1]))}</td>
            <td>{escape(str(r[2]))}</td>
            <td>{escape(str(r[3]))}</td>
            <td>{escape(str(r[4]))}</td>
            <td><span class="badge {status_class}">{escape(str(r[5]))}</span></td>
            <td>{salary}</td>
            <td>{escape(str(r[7])) if r[7] else '-'}</td>
            <td>{escape(str(r[8])) if r[8] else '-'}</td>
        </tr>'''
    html += '</tbody></table>'
    return html


def generate():
    os.makedirs(DOCS_DIR, exist_ok=True)
    summary, all_rows = fetch_summary()
    generated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    dept_tabs = ''
    dept_panels = ''
    for dept in DEPARTMENTS:
        dept_rows = [r for r in all_rows if r[2] == dept]
        dept_tabs += f'<button class="tab-btn" onclick="showTab(\'{dept}\')">{dept} <span class="count">{len(dept_rows)}</span></button>'
        dept_panels += f'<div id="tab-{dept}" class="tab-panel">{rows_to_html_table(dept_rows, f"table-{dept}")}</div>'

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>HR Automation Dashboard</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', sans-serif; background: #f0f4f8; color: #333; }}
  header {{ background: #1a73e8; color: white; padding: 20px 40px; display: flex; justify-content: space-between; align-items: center; }}
  header h1 {{ font-size: 1.6rem; }}
  header small {{ opacity: 0.8; font-size: 0.85rem; }}
  .container {{ max-width: 1200px; margin: 30px auto; padding: 0 20px; }}

  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 30px; }}
  .card {{ background: white; border-radius: 10px; padding: 20px; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.07); }}
  .card h2 {{ font-size: 2.2rem; color: #1a73e8; }}
  .card p {{ color: #666; font-size: 0.9rem; margin-top: 4px; }}
  .card.sales h2 {{ color: #34a853; }}
  .card.finance h2 {{ color: #fbbc04; }}
  .card.operations h2 {{ color: #ea4335; }}

  .section {{ background: white; border-radius: 10px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.07); margin-bottom: 24px; }}
  .section h3 {{ font-size: 1.1rem; margin-bottom: 16px; color: #444; }}

  input[type=search] {{ width: 100%; padding: 10px 14px; border: 1px solid #ddd; border-radius: 6px; font-size: 0.95rem; margin-bottom: 16px; outline: none; }}
  input[type=search]:focus {{ border-color: #1a73e8; }}

  .tabs {{ display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }}
  .tab-btn {{ padding: 8px 18px; border: 2px solid #ddd; border-radius: 20px; background: white; cursor: pointer; font-size: 0.9rem; transition: all 0.2s; }}
  .tab-btn:hover, .tab-btn.active {{ background: #1a73e8; color: white; border-color: #1a73e8; }}
  .tab-panel {{ display: none; }}
  .tab-panel.active {{ display: block; }}
  .count {{ background: rgba(255,255,255,0.3); border-radius: 10px; padding: 1px 7px; font-size: 0.8rem; margin-left: 4px; }}
  .tab-btn.active .count {{ background: rgba(255,255,255,0.3); }}
  .tab-btn .count {{ background: #e8f0fe; color: #1a73e8; }}

  table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
  th {{ background: #f8f9fa; text-align: left; padding: 10px 12px; border-bottom: 2px solid #e0e0e0; color: #555; font-weight: 600; }}
  td {{ padding: 10px 12px; border-bottom: 1px solid #f0f0f0; }}
  tr:hover td {{ background: #f8f9ff; }}

  .badge {{ padding: 3px 10px; border-radius: 12px; font-size: 0.8rem; font-weight: 600; }}
  .badge.active {{ background: #e6f4ea; color: #34a853; }}
  .badge.inactive {{ background: #fce8e6; color: #ea4335; }}
  .badge.leave {{ background: #fef7e0; color: #f9ab00; }}
  .no-data {{ color: #999; text-align: center; padding: 30px; }}

  footer {{ text-align: center; padding: 20px; color: #999; font-size: 0.85rem; }}
</style>
</head>
<body>

<header>
  <h1>HR Automation Dashboard</h1>
  <small>Last updated: {generated_at}</small>
</header>

<div class="container">
  <div class="cards">
    <div class="card">
      <h2>{summary['total']}</h2>
      <p>Total Employees</p>
    </div>
    <div class="card">
      <h2>{summary['active']}</h2>
      <p>Active Employees</p>
    </div>
    <div class="card sales">
      <h2>{summary['Sales']['total']}</h2>
      <p>Sales ({summary['Sales']['active']} active)</p>
    </div>
    <div class="card finance">
      <h2>{summary['Finance']['total']}</h2>
      <p>Finance ({summary['Finance']['active']} active)</p>
    </div>
    <div class="card operations">
      <h2>{summary['Operations']['total']}</h2>
      <p>Operations ({summary['Operations']['active']} active)</p>
    </div>
  </div>

  <div class="section">
    <h3>All Employees</h3>
    <input type="search" id="search" placeholder="Search by name, role, department..." onkeyup="filterTable()">
    {rows_to_html_table(all_rows, 'table-all')}
  </div>

  <div class="section">
    <h3>By Department</h3>
    <div class="tabs">
      {dept_tabs}
    </div>
    {dept_panels}
  </div>
</div>

<footer>HR Automation System &mdash; Generated {generated_at}</footer>

<script>
  function filterTable() {{
    const q = document.getElementById('search').value.toLowerCase();
    const rows = document.querySelectorAll('#table-all tbody tr');
    rows.forEach(r => {{
      r.style.display = r.textContent.toLowerCase().includes(q) ? '' : 'none';
    }});
  }}

  function showTab(dept) {{
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('tab-' + dept).classList.add('active');
    event.target.classList.add('active');
  }}

  // Show first tab by default
  document.querySelector('.tab-btn').click();
</script>
</body>
</html>'''

    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"Dashboard generated: {OUTPUT}")
    return OUTPUT


if __name__ == '__main__':
    generate()
