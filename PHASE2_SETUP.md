# Phase 2: Gemini diagnosis setup

The engine uses Google's Gemini API with Pydantic structured output. It never
executes a proposed command; the result is intended for Shailesh's independent
configuration validation layer.

## 1. Install the dependencies

From the project directory in PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## 2. Verify the integration offline

No API key or network request is needed for these checks:

```powershell
python -m unittest -v test_log_preprocessor test_ai_engine
python run_ai_engine.py
```

The runner defaults to a mock. For the sample interface-down event, the mock
returns an empty `candidate_command` and zero confidence because the log does
not establish whether the interface was intentionally shut down. Do not treat
an interface-down event by itself as proof that `no shutdown` is appropriate.

## 3. Create a Gemini API key

Open [Google AI Studio](https://aistudio.google.com/app/apikey), sign in, and
create an API key for the Gemini API. Keep it private: do not paste it into
Python files, commit it, or share it in logs/screenshots. Check the current
Gemini API pricing, quotas, and availability for your account before making
live requests.

## 4. Set the key in the same PowerShell session

In VS Code, open **Terminal → New Terminal**, navigate to the project folder,
and replace the placeholder below with the key you just created. The key goes
in the terminal command—not in `ai_engine.py`, `run_ai_engine.py`, or this
guide:

```powershell
cd C:\Users\rashm\network-troubleshoot-ai
$env:GEMINI_API_KEY = "paste-your-Gemini-key-here"
```

Do not include angle brackets. This sets the key only for that PowerShell
session and child processes. Do not put your actual key in this guide or in
source control.

## 5. Make the first live Gemini API call

Run this in the same terminal where you set the key:

```powershell
& ".\.venv\Scripts\python.exe" run_ai_engine.py --live
```

`--live` explicitly sends the sample event to Gemini and prints the validated
contract JSON. The engine reads `GEMINI_API_KEY` at call time and reports a
clear error if it is missing. Without `--live`, the mock runner makes no API
request. The live runner prints a status line before the call; each request has
a 60-second timeout and one attempt so connection issues don't leave it
silently waiting through retries. The model defaults to `gemini-3.8-flash`; optionally set
`$env:GEMINI_MODEL = "model-name"` in the same terminal to select another
Gemini model enabled for your account.

## 6. Connect Phase 1 to the engine

```python
from ai_engine import diagnose_event
from log_preprocessor import parse_logs

events = parse_logs(raw_log_text, device_id="router1")
for event in events:
    diagnosis = diagnose_event(event)
    print(diagnosis.model_dump_json())
```

Supply a device ID in `parse_logs` when the log does not contain a hostname:
the handoff contract requires a non-empty `device_id`. Pass each result to the
configuration validation layer for review; do not apply the generated command
directly to a device.
