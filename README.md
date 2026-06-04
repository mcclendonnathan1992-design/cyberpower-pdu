# CyberPower PDU Automation

A Python infrastructure-automation module for controlling CyberPower rack PDUs over SNMP. The project provides an object-oriented interface for reading outlet state, switching outlets on or off, loading device configuration, and validating behavior through mocked pytest tests.

## Business problem

Integration and lab teams often need to power-cycle devices, recover failed hardware, or reset test fixtures during regression runs. Doing that manually slows down test execution, introduces inconsistent recovery steps, and creates operational risk when engineers are working with shared lab infrastructure.

This project solves that problem by creating a scriptable PDU control layer that can be reused by test harnesses, CI jobs, or operator tools to manage outlet state in a repeatable way.

## What I built

I built a Python class that loads CyberPower PDU definitions from JSON and exposes simple methods such as `get()`, `on()`, `off()`, and `list_outlets()` for outlet control.

One engineering decision I made was to mock all SNMP operations in the pytest suite. That makes the tests safe to run anywhere and validates the control logic without requiring access to physical power hardware.

## Services, tools, and why they were used

| Service / Tool | Why it was used |
|---|---|
| Python | Core automation language for infrastructure-control logic. |
| pysnmp | Provides SNMP GET/SET communication with CyberPower PDU devices. |
| JSON | Stores device inventory in a simple, portable configuration format. |
| pytest | Validates configuration loading, outlet validation, and control behavior. |
| unittest.mock | Mocks SNMP communication so tests do not touch live equipment. |
| SNMPv1 OIDs | Maps outlet indexes to CyberPower outlet-control object identifiers. |

## Architecture

```text
devices.json
  |
  |-- PDU name, IP address, SNMP communities, timeout, retries
  v
CyberPowerPDU.from_config()
  |
  |-- Load selected PDU definition
  |-- Validate outlet index
  |-- Map outlet number to outlet OID
  |
  |-- GET path
  |     Read outlet state over SNMP
  |
  |-- SET path
  |     Set outlet state and verify readback
  v
Operator script, test harness, or CI workflow
```

## Key architectural decisions

| Decision | Reason | Problem solved |
|---|---|---|
| Wrap SNMP behavior in a class | Keep device state and operations together | Makes the code reusable from test harnesses and scripts |
| Load PDUs from JSON | Separate device inventory from code | Allows different lab devices without editing source code |
| Validate outlet indexes before SNMP calls | Fail safely before touching hardware | Prevents invalid outlet commands |
| Use mocked SNMP tests | Validate logic without live equipment | Makes regression testing safe and portable |
| Verify SET operations with readback | Confirm command effect after action | Reduces false assumptions about infrastructure state |

## Deployment

```bash
git clone https://github.com/mcclendonnathan1992-design/cyberpower-pdu.git
cd cyberpower-pdu
python -m venv .venv
source .venv/bin/activate      # macOS/Linux
# .venv\Scripts\activate       # Windows PowerShell
pip install -r requirements.txt
```

## Example sanitized configuration

Do not commit real SNMP community strings, production IP addresses, or lab inventory files.

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
print(pdu.get(1))
pdu.on(1)
pdu.off(1)
print(pdu.list_outlets())
```

## Test strategy

```bash
pytest test_cyberpower_pdu.py -v
```

The test suite mocks SNMP GET/SET behavior and validates:

- Device configuration loading
- PDU selection by name
- Outlet index boundary checks
- ON/OFF command behavior
- Failed SET handling
- Readback mismatch handling
- Missing config-file behavior

## What the infrastructure solves

- Allows test harnesses to control lab power state programmatically.
- Reduces manual intervention during device recovery and regression setup.
- Creates a safer validation path by testing logic without touching live hardware.
- Provides a reusable infrastructure-control layer for larger automation platforms.

## Task–Tool–Impact bullets

- Built a Python SNMP automation module using `pysnmp` and object-oriented design to control CyberPower PDU outlets from scripts, test harnesses, or CI workflows.
- Implemented mocked pytest coverage using `unittest.mock` and async SNMP stubs to validate outlet reads, on/off commands, error handling, and readback verification without requiring physical hardware.
- Designed JSON-based device configuration loading to separate lab inventory from source code and support reusable infrastructure automation across multiple PDUs.
- Added outlet-index validation and SET/readback verification to reduce the risk of invalid commands and improve confidence in infrastructure state changes.

## Public-repo hygiene

- Do not commit production SNMP community strings.
- Use placeholder IP ranges such as `192.0.2.0/24` in examples.
- Treat PDU control as privileged infrastructure access.
- Keep real device inventory files outside the repository or ignored by Git.

## Resume alignment

This project supports roles involving Python automation, lab infrastructure control, pytest mocking, networked systems validation, and repeatable secure test environments.
