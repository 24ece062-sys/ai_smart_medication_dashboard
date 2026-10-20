from flask import Flask, jsonify, request, render_template
import sqlite3, json, os
from datetime import datetime, date, timedelta
from functools import wraps
app=Flask(__name__)
DB=os.path.join(os.path.dirname(__file__),'medication.db')
DEVICE_KEY=os.environ.get('DEVICE_API_KEY','change-this-device-key')
DAYS=['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
def connect():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c
def init_db():
 with connect() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS medicines(id INTEGER PRIMARY KEY,name TEXT NOT NULL,dosage TEXT NOT NULL,instructions TEXT DEFAULT '',start_date TEXT DEFAULT '',end_date TEXT DEFAULT '',times TEXT NOT NULL,days TEXT NOT NULL,active INTEGER DEFAULT 1,created_at TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,medicine_id INTEGER,medicine_name TEXT,scheduled_for TEXT,event_type TEXT,details TEXT DEFAULT '',created_at TEXT, UNIQUE(medicine_id,scheduled_for,event_type));
  CREATE TABLE IF NOT EXISTS appointments(id INTEGER PRIMARY KEY,doctor_name TEXT,specialty TEXT,appointment_date TEXT,appointment_time TEXT,visit_type TEXT,status TEXT DEFAULT 'Booked',created_at TEXT);
  CREATE TABLE IF NOT EXISTS caregivers(id INTEGER PRIMARY KEY,name TEXT,email TEXT DEFAULT '',phone TEXT DEFAULT '',relationship TEXT DEFAULT 'Caregiver',enabled INTEGER DEFAULT 1,created_at TEXT);
  CREATE TABLE IF NOT EXISTS device_state(id INTEGER PRIMARY KEY CHECK(id=1),last_sync TEXT DEFAULT '',last_seen TEXT DEFAULT '',sync_status TEXT DEFAULT 'Not connected',schedule_version INTEGER DEFAULT 0); INSERT OR IGNORE INTO device_state(id) VALUES(1);''')
  if not c.execute('SELECT COUNT(*) FROM medicines').fetchone()[0]:
   now=datetime.now().isoformat(timespec='seconds')
   for name,dose,times in [('Example Medicine A','1 tablet',['08:00','20:00']),('Example Medicine B','1 capsule',['13:00'])]: c.execute('INSERT INTO medicines(name,dosage,instructions,times,days,active,created_at) VALUES(?,?,?,?,?,?,?)',(name,dose,'Demo data — replace with clinician-approved instructions',json.dumps(times),json.dumps(DAYS),1,now))
  if not c.execute('SELECT COUNT(*) FROM caregivers').fetchone()[0]: c.execute('INSERT INTO caregivers(name,email,relationship,created_at) VALUES(?,?,?,?)',('Demo Caregiver','caregiver@example.com','Family member',datetime.now().isoformat(timespec='seconds')))
def meddict(r):
 d=dict(r); d['times']=json.loads(d.pop('times')); d['days']=json.loads(d.pop('days')); d['active']=bool(d['active']); return d
def device_auth(f):
 @wraps(f)
 def w(*a,**kw):
  if request.headers.get('X-Device-Key')!=DEVICE_KEY:return jsonify(error='Unauthorized device. Check X-Device-Key.'),401
  return f(*a,**kw)
 return w
@app.get('/')
def home(): return render_template('index.html')
@app.get('/api/dashboard')
def dashboard():
 with connect() as c:
  return jsonify(medicines=[meddict(r) for r in c.execute('SELECT * FROM medicines ORDER BY id DESC')],events=[dict(r) for r in c.execute('SELECT * FROM events ORDER BY created_at DESC LIMIT 100')],appointments=[dict(r) for r in c.execute('SELECT * FROM appointments ORDER BY appointment_date,appointment_time')],caregivers=[dict(r) for r in c.execute('SELECT * FROM caregivers ORDER BY id')],device=dict(c.execute('SELECT * FROM device_state WHERE id=1').fetchone()),days=DAYS)
def validate(d):
 name=str(d.get('name','')).strip(); dose=str(d.get('dosage','')).strip(); times=d.get('times'); days=d.get('days')
 if not name or not dose:return None,'Medicine name and dosage are required.'
 if not isinstance(times,list) or not times:return None,'Add at least one dose time.'
 try:
  for t in times: datetime.strptime(t,'%H:%M')
 except (ValueError,TypeError):return None,'Dose times must use HH:MM.'
 if not isinstance(days,list) or not days or any(x not in DAYS for x in days):return None,'Select at least one valid day.'
 return (name,dose,str(d.get('instructions','')).strip(),str(d.get('start_date','')),str(d.get('end_date','')),json.dumps(sorted(set(times))),json.dumps([x for x in DAYS if x in days]),1 if d.get('active',True) else 0),None
def changed(c): c.execute('UPDATE device_state SET schedule_version=schedule_version+1 WHERE id=1')
@app.post('/api/medicines')
def add_med():
 d,e=validate(request.get_json(silent=True) or {}); 
 if e:return jsonify(error=e),400
 with connect() as c:
  cur=c.execute('INSERT INTO medicines(name,dosage,instructions,start_date,end_date,times,days,active,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(*d,datetime.now().isoformat(timespec='seconds'))); changed(c)
 return jsonify(ok=True,id=cur.lastrowid),201
@app.put('/api/medicines/<int:i>')
def edit_med(i):
 d,e=validate(request.get_json(silent=True) or {})
 if e:return jsonify(error=e),400
 with connect() as c:
  if not c.execute('SELECT id FROM medicines WHERE id=?',(i,)).fetchone():return jsonify(error='Medicine not found.'),404
  c.execute('UPDATE medicines SET name=?,dosage=?,instructions=?,start_date=?,end_date=?,times=?,days=?,active=? WHERE id=?',(*d,i)); changed(c)
 return jsonify(ok=True)
@app.delete('/api/medicines/<int:i>')
def delete_med(i):
 with connect() as c:
  cur=c.execute('DELETE FROM medicines WHERE id=?',(i,));
  if not cur.rowcount:return jsonify(error='Medicine not found.'),404
  changed(c)
 return jsonify(ok=True)
@app.post('/api/device/sync')
def sync():
 now=datetime.now().isoformat(timespec='seconds')
 with connect() as c:c.execute("UPDATE device_state SET last_sync=?,sync_status='Sync requested',schedule_version=schedule_version+1 WHERE id=1",(now,))
 return jsonify(ok=True,message='Sync requested. The ESP32 must fetch /api/device/schedule to receive the schedule.')
@app.get('/api/device/schedule')
@device_auth
def device_schedule():
 with connect() as c:
  meds=[meddict(r) for r in c.execute('SELECT * FROM medicines WHERE active=1')]; state=dict(c.execute('SELECT * FROM device_state WHERE id=1').fetchone()); now=datetime.now().isoformat(timespec='seconds'); c.execute("UPDATE device_state SET last_seen=?,sync_status='Connected' WHERE id=1",(now,))
 return jsonify(version=state['schedule_version'],generated_at=now,medicines=meds,days=DAYS)
@app.post('/api/device/ack')
@device_auth
def ack():
 now=datetime.now().isoformat(timespec='seconds')
 with connect() as c:c.execute("UPDATE device_state SET last_seen=?,last_sync=?,sync_status='Connected - schedule acknowledged' WHERE id=1",(now,now))
 return jsonify(ok=True)
@app.post('/api/events')
def event():
 d=request.get_json(silent=True) or {}; typ=d.get('event_type')
 if typ not in ('dispensed','missed','failed'):return jsonify(error='event_type must be dispensed, missed, or failed.'),400
 with connect() as c:
  med=c.execute('SELECT id,name FROM medicines WHERE id=?',(d.get('medicine_id'),)).fetchone() if d.get('medicine_id') else None
  now=datetime.now().isoformat(timespec='seconds'); scheduled=d.get('scheduled_for') or datetime.now().isoformat(timespec='minutes')
  try:c.execute('INSERT INTO events(medicine_id,medicine_name,scheduled_for,event_type,details,created_at) VALUES(?,?,?,?,?,?)',(d.get('medicine_id'),d.get('medicine_name') or (med['name'] if med else 'Unknown medicine'),scheduled,typ,str(d.get('details','')),now))
  except sqlite3.IntegrityError:return jsonify(ok=True,duplicate=True)
 return jsonify(ok=True),201
@app.post('/api/missed/check')
def missed_check():
 now=datetime.now(); created=0
 with connect() as c:
  for r in c.execute('SELECT * FROM medicines WHERE active=1').fetchall():
   m=meddict(r)
   for offset in range(2):
    d=(now-timedelta(days=offset)).date();
    if DAYS[d.weekday()] not in m['days'] or (m['start_date'] and d.isoformat()<m['start_date']) or (m['end_date'] and d.isoformat()>m['end_date']):continue
    for t in m['times']:
     due=datetime.combine(d,datetime.strptime(t,'%H:%M').time())
     if due>now-timedelta(minutes=20):continue
     iso=due.isoformat(timespec='minutes')
     done=c.execute("SELECT 1 FROM events WHERE medicine_id=? AND scheduled_for=? AND event_type='dispensed'",(m['id'],iso)).fetchone()
     missed=c.execute("SELECT 1 FROM events WHERE medicine_id=? AND scheduled_for=? AND event_type='missed'",(m['id'],iso)).fetchone()
     if not done and not missed:
      c.execute('INSERT INTO events(medicine_id,medicine_name,scheduled_for,event_type,details,created_at) VALUES(?,?,?,?,?,?)',(m['id'],m['name'],iso,'missed','Prototype rule: no dispensing event within 20 minutes.',now.isoformat(timespec='seconds')));created+=1
 return jsonify(ok=True,created=created)
@app.post('/api/appointments')
def add_appt():
 d=request.get_json(silent=True) or {}
 if any(not str(d.get(k,'')).strip() for k in ('doctor_name','specialty','appointment_date','appointment_time')):return jsonify(error='Doctor, specialty, date and time are required.'),400
 try:
  if date.fromisoformat(d['appointment_date'])<date.today():return jsonify(error='Appointment date cannot be in the past.'),400
  datetime.strptime(d['appointment_time'],'%H:%M')
 except ValueError:return jsonify(error='Invalid appointment date or time.'),400
 with connect() as c:cur=c.execute('INSERT INTO appointments(doctor_name,specialty,appointment_date,appointment_time,visit_type,status,created_at) VALUES(?,?,?,?,?,?,?)',(d['doctor_name'],d['specialty'],d['appointment_date'],d['appointment_time'],d.get('visit_type','In person'),'Booked',datetime.now().isoformat(timespec='seconds')))
 return jsonify(ok=True,id=cur.lastrowid),201
@app.delete('/api/appointments/<int:i>')
def cancel_appt(i):
 with connect() as c:
  cur=c.execute("UPDATE appointments SET status='Cancelled' WHERE id=?",(i,))
  if not cur.rowcount:return jsonify(error='Appointment not found.'),404
 return jsonify(ok=True)
@app.post('/api/caregivers')
def add_caregiver():
 d=request.get_json(silent=True) or {}; name=str(d.get('name','')).strip()
 if not name:return jsonify(error='Caregiver name is required.'),400
 with connect() as c:cur=c.execute('INSERT INTO caregivers(name,email,phone,relationship,enabled,created_at) VALUES(?,?,?,?,1,?)',(name,d.get('email',''),d.get('phone',''),d.get('relationship','Caregiver'),datetime.now().isoformat(timespec='seconds')))
 return jsonify(ok=True,id=cur.lastrowid),201
@app.patch('/api/caregivers/<int:i>')
def toggle_caregiver(i):
 with connect() as c:
  cur=c.execute('UPDATE caregivers SET enabled=? WHERE id=?',(1 if (request.get_json(silent=True) or {}).get('enabled') else 0,i))
  if not cur.rowcount:return jsonify(error='Caregiver not found.'),404
 return jsonify(ok=True)
@app.delete('/api/caregivers/<int:i>')
def delete_caregiver(i):
 with connect() as c:
  cur=c.execute('DELETE FROM caregivers WHERE id=?',(i,))
  if not cur.rowcount:return jsonify(error='Caregiver not found.'),404
 return jsonify(ok=True)
@app.get('/api/health')
def health():return jsonify(ok=True)
init_db()
if __name__=='__main__':app.run(host='0.0.0.0',port=5000,debug=True)
