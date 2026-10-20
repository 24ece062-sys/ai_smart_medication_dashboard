# AI Smart Medication Management Dashboard (Prototype)

A Flask + SQLite starter project featuring medicine CRUD, editable dose times and weekdays, a sync request and ESP32 schedule API, dose-event history, basic missed-dose checking, appointment records, and caregiver contact/preferences.

## Run in VS Code (Windows)
1. Extract the ZIP and open the `ai_smart_medication_dashboard` folder in VS Code.
2. Open **Terminal → New Terminal**.
3. Create and activate a virtual environment:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, use Command Prompt and run `.venv\Scripts\activate.bat`.

4. Install and start:

```powershell
python -m pip install -r requirements.txt
python app.py
```

5. Open **http://127.0.0.1:5000** in your browser. SQLite database `medication.db` is created automatically. Two sample medicines and one demo caregiver are added the first time.

## Project files
- `app.py` — Flask API and SQLite database
- `templates/index.html` — dashboard pages and forms
- `static/style.css` — responsive healthcare UI
- `static/app.js` — navigation, API calls, rendering and form actions

## ESP32 endpoints
- `GET /api/device/schedule` — get active schedules. Requires header `X-Device-Key`.
- `POST /api/device/ack` — acknowledge schedule received. Requires header `X-Device-Key`.
- `POST /api/events` — record `dispensed`, `missed`, or `failed` events.
- `POST /api/device/sync` — dashboard creates a sync request; the ESP32 must poll the schedule endpoint to receive it.

The default demo key is `change-this-device-key`. Set a different key before connecting hardware. PowerShell example:

```powershell
$env:DEVICE_API_KEY="your-long-random-device-key"
python app.py
```

For an ESP32 on the same Wi-Fi, use your computer's LAN IPv4 address (not `127.0.0.1`) in the ESP32 URL and allow Python through your private-network firewall if needed.

Example `POST /api/events` JSON:

```json
{
  "medicine_id": 1,
  "event_type": "dispensed",
  "scheduled_for": "2026-10-09T08:00",
  "details": "IR sensor detected an item passing the outlet"
}
```

## Prototype limitations and safety
- The sync button only requests synchronization. ESP32 firmware still needs to poll `/api/device/schedule`, apply a validated schedule, and call `/api/device/ack`.
- Caregiver contacts and alert preferences are saved, but email/SMS/push notifications are not implemented.
- Appointments are manually entered records, not real-time doctor availability or external booking.
- Missed-dose logic is a simple local-time demo rule. Test carefully; it is not a clinically validated adherence system.
- An IR sensor detects an item passing the dispenser outlet; it cannot prove the patient swallowed it.
- This educational prototype has no login, role-based access, production security, or privacy safeguards. Do not use real patient data or expose it to the public internet as-is.
- The website organizes schedules entered by a user; it does not prescribe medicines. Follow the clinician's prescription.
