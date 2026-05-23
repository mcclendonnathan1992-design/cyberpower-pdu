"""
CyberPower PDU — Live Connectivity Smoke Test
=============================================
Run this ONLY when connected to the work network with real PDUs reachable.
This is NOT a unit test — it makes real SNMP calls.

Usage:
    python smoke_test_pdu.py                    # tests all PDUs in devices.json
    python smoke_test_pdu.py --pdu PDU-1        # tests one PDU
    python smoke_test_pdu.py --read-only        # skips SET commands (safe)

What it checks:
    1. SNMP GET reachability for every PDU
    2. Reads state of outlet 1 on each PDU
    3. (Unless --read-only) SET outlet 1 OFF then ON and verifies read-back
"""

import argparse
import sys
import time
from pathlib import Path

# Adjust this path if smoke_test_pdu.py is not in the same folder as cyberpower_pdu.py
sys.path.insert(0, str(Path(__file__).parent))

from cyberpower_pdu import CyberPowerPDU


def test_pdu(pdu: CyberPowerPDU, read_only: bool) -> bool:
    print(f"\n{'='*55}")
    print(f"  Testing: {pdu.name}  ({pdu.ip})")
    print(f"{'='*55}")
    passed = True

    # ---- 1. GET all outlets ----
    print("\n[1] Reading all outlet states...")
    states = pdu.list_outlets()
    if not any(v is not None for v in states.values()):
        print("  FAIL — Could not read any outlet. Check IP, community string, UDP/161.")
        return False

    for idx, state in states.items():
        mark = "✓" if state is not None else "✗"
        print(f"  {mark} Outlet {idx}: {state or 'READ FAILED'}")

    # ---- 2. GET single outlet ----
    print("\n[2] Single GET on outlet 1...")
    state = pdu.get(1)
    if state is None:
        print("  FAIL — GET outlet 1 returned None.")
        passed = False
    else:
        print(f"  OK — Outlet 1 is {state}")

    if read_only:
        print("\n  [--read-only mode] Skipping SET tests.")
        return passed

    # ---- 3. SET outlet 1 OFF then ON ----
    original_state = state

    print("\n[3] SET outlet 1 → OFF...")
    ok = pdu.off(1)
    if ok:
        print("  OK — Outlet 1 confirmed OFF.")
    else:
        print("  FAIL — SET OFF did not verify.")
        passed = False

    time.sleep(2)  # brief pause between commands

    print("\n[4] SET outlet 1 → ON...")
    ok = pdu.on(1)
    if ok:
        print("  OK — Outlet 1 confirmed ON.")
    else:
        print("  FAIL — SET ON did not verify.")
        passed = False

    # Restore original state if it was OFF
    if original_state == "OFF":
        print("\n[5] Restoring outlet 1 to original state (OFF)...")
        pdu.off(1)

    return passed


def main():
    ap = argparse.ArgumentParser(description="Live PDU connectivity smoke test")
    ap.add_argument(
        "--config",
        default=str(Path(__file__).parent / "devices.json"),
        help="Path to devices.json",
    )
    ap.add_argument("--pdu", default=None, help="Test only this named PDU")
    ap.add_argument(
        "--read-only",
        action="store_true",
        help="Skip SET commands — safe for production environments",
    )
    args = ap.parse_args()

    print("\nCyberPower PDU Smoke Test")
    print(f"Config: {args.config}")
    print(f"Mode:   {'READ-ONLY' if args.read_only else 'READ + WRITE'}")

    pdus = CyberPowerPDU.all_from_config(args.config)
    if not pdus:
        print("No PDUs found in config.")
        sys.exit(1)

    if args.pdu:
        pdus = [p for p in pdus if p.name == args.pdu]
        if not pdus:
            print(f"PDU '{args.pdu}' not found in config.")
            sys.exit(1)

    results = {}
    for pdu in pdus:
        results[pdu.name] = test_pdu(pdu, args.read_only)

    print(f"\n{'='*55}")
    print("  SUMMARY")
    print(f"{'='*55}")
    all_passed = True
    for name, ok in results.items():
        mark = "PASS ✓" if ok else "FAIL ✗"
        print(f"  {mark}  {name}")
        if not ok:
            all_passed = False

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
