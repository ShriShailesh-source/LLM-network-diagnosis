# LLM Network Diagnosis

An offline-first computer-networks project that treats an LLM diagnosis as
untrusted input and validates a proposed Cisco-style fix against a deterministic
network state model.

## Architecture

```text
Cisco-style evidence / fixture
        -> log_preprocessor.py
Structured event -> ai_engine.py (Gemini or injected deterministic client)
        -> Validation/validator.py
        -> ACCEPTED safe recommendation or REJECTED explanation
        -> evaluation.py metrics
```

The validator never executes commands. It only recommends or rejects them.

## Implemented modules

- `log_preprocessor.py` normalizes interface, OSPF adjacency, and interface
  brief evidence into `ParsedLogEvent` records.
- `ai_engine.py` provides a strict Pydantic diagnosis contract and optional
  Gemini integration. Tests and the demo inject a deterministic client; pytest
  never calls a live API.
- `Validation/topology.py` models three routers, six interfaces, three links,
  IP addresses, interface states, and an OSPF Area 0-style neighbor snapshot.
  This is a deterministic state model, not live OSPF.
- `Validation/rules.py` checks required fields and confidence, device and
  interface existence, supported command syntax, IP validity, current state,
  and fault/fix correspondence.
- `demo.py` runs the Packet Tracer evidence through both an accepted and a
  deliberately rejected recommendation.
- `evaluation.py` generates and executes deterministic cases and exports
  `evaluation.json`, `evaluation.csv`, and `summary.json`.
- `dashboard.py` is a small standard-library HTTP dashboard/API. It validates
  submitted diagnoses but does not execute them.

## Evidence and Packet Tracer

`logs/packet_tracer_router0.txt` is the existing Packet Tracer transcript. It
shows Router0 `GigabitEthernet0/1` administratively down and is mapped to the
simulated `R1`. `logs/simulated_ospf_and_ip.txt` contains clearly labelled
fixture evidence for OSPF adjacency loss and interface state. These files are
fixtures, not live collection.

The deterministic lab topology is:

```text
R1 -------- R2
 \          /
  \        /
      R3
```

Supported evaluation fault types are `interface_down`,
`ospf_neighbor_down`, and `incorrect_ip`. The validator also retains support
for the earlier IP, duplex, speed, and interface-disable fault names.

## Running the project

Use the repository's Python environment:

```powershell
python demo.py
python -m evaluation --count 10
python -m evaluation --count 500
python -m uvicorn dashboard:app --reload
```

The dashboard is available at <http://127.0.0.1:8000>. `GET /health` checks
readiness, `GET /` serves the dashboard page, and `POST /api/validate` accepts
the diagnosis fields plus optional
`interface_state` and `current_config` JSON values.

To use the live Gemini path, install dependencies from `requirements.txt` and
set `GEMINI_API_KEY`. No API key is needed for the demo, evaluation, or tests.

## Tests

```powershell
python -m pytest -q
```

The tests cover parsing, the strict diagnosis schema, topology and validation
boundaries, accepted/rejected fault-fix pairs, and the end-to-end demo.

## Evaluation metrics

The evaluation reports diagnosis correctness, valid-fix acceptance rate,
invalid-fix rejection rate, false-acceptance rate, false-rejection rate,
overall validation accuracy, accepted/rejected totals, and per-fault results.
All percentages are calculated from executed cases; no presentation values are
hardcoded.

## Limitations and future scope

Current network evidence is fixture-based, the topology is simulated, and
validation supports a deliberately small safe command allowlist. There is no
live device, SNMP, syslog collector, command execution, or genuine OSPF
control-plane simulation. Future work can add read-only collectors, richer
device adapters, authenticated deployment approval, and a real dashboard
frontend while retaining the validator as the authority.
