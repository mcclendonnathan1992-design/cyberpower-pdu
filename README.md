# CyberPower PDU Automation

A Python automation module for controlling CyberPower rack PDUs over SNMP. The project provides a small object-oriented interface for reading outlet state, switching outlets on or off, and validating behavior through mocked pytest tests.

## Why this project matters

This repository demonstrates infrastructure automation, hardware-adjacent test engineering, and safe validation practices. The unit tests mock SNMP interactions so the project can be validated without access to a physical PDU.

## Key capabilities

- Control CyberPower PDU outlets over SNMPv1
- Load one or more PDU definitions from JSON configuration
- Turn individual outlets on or off
- Read outlet state with SNMP GET
- Validate outlet index boundaries
- Run offline unit tests with mocked SNMP calls
- Designed for reuse from test harnesses, CI jobs, and infrastructure scripts

## Project layout

```text
.
├── cyberpower_pdu.py        # Main PDU controller class
├── test_cyberpower_pdu.py   # Mocked unit tests; no physical PDU required
└── README.md
```

## Setup

```bash
# 1. Clone the repository
git clone https://github.com/mcclendonnathan1992-design/cyberpower-pdu.git
cd cyberpower-pdu

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate      # macOS/Linux
# .venv\Scripts\activate       # Windows PowerShell

# 3. Install dependencies
pip install pysnmp pytest
```

## Example configuration

Create a local `devices.json` file. Do not commit real community strings, IP addresses, or production network details.

```json
{
  "pdus": [
    {
      "name": "LAB-PDU-1",
      "ip": "192.0.2.10",
      "read_community": "READ_COMMUNITY_PLACEHOLDER",
      "write_community": "WRITE_COMMUNITY_PLACEHOLDER",
      "timeout": 10,
      "retries": 1
    }
  ]
}
```

## Usage example

```python
from cyberpower_pdu import CyberPowerPDU

pdu = CyberPowerPDU.from_config("devices.json", name="LAB-PDU-1")

print(pdu.get(1))      # "ON", "OFF", or None
pdu.on(1)              # Turn outlet 1 on
pdu.off(1)             # Turn outlet 1 off
print(pdu.list_outlets())
```

## Run tests

```bash
pytest test_cyberpower_pdu.py -v
```

The tests mock SNMP GET/SET behavior and can run without a physical CyberPower PDU.

## Security notes

- Do not commit production SNMP community strings.
- Prefer restricted lab networks and non-default community strings.
- Treat PDU control as privileged infrastructure access.
- Keep real device inventory files outside the repository or add them to `.gitignore`.

## Engineering practices demonstrated

- Object-oriented Python interface design
- Config-driven infrastructure automation
- Mocked hardware interactions for safe tests
- pytest fixtures and patching
- Defensive input validation for outlet indexes
- Clear separation between implementation and tests

## Resume bullet

Built a Python-based CyberPower PDU automation module using SNMP and pytest, including mocked unit tests that validate outlet state reads, on/off commands, configuration loading, and boundary handling without requiring physical hardware.
