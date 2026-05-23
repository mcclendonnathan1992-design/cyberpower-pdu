"""
CyberPower PDU Controller — pysnmp 7.1.16 / Ubuntu 22.04 / OOP
================================================================
Replaces Windows SnmpSoft executables with pure-Python pysnmp.
Loads device configs from a JSON file.
Designed to be imported and called from other scripts (GitLab CI / test harness).

SNMPv1 only. Outlet values: 1 = ON, 2 = OFF

Version: 2.0.0
"""

__version__ = "2.0.0"

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Optional

from pysnmp.hlapi.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    get_cmd,
    set_cmd,
)

# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("cyberpower_pdu")


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
OUTLET_OIDS = [
    "1.3.6.1.4.1.3808.1.1.3.3.3.1.1.4.1",
    "1.3.6.1.4.1.3808.1.1.3.3.3.1.1.4.2",
    "1.3.6.1.4.1.3808.1.1.3.3.3.1.1.4.3",
    "1.3.6.1.4.1.3808.1.1.3.3.3.1.1.4.4",
    "1.3.6.1.4.1.3808.1.1.3.3.3.1.1.4.5",
    "1.3.6.1.4.1.3808.1.1.3.3.3.1.1.4.6",
    "1.3.6.1.4.1.3808.1.1.3.3.3.1.1.4.7",
    "1.3.6.1.4.1.3808.1.1.3.3.3.1.1.4.8",
]

STATE_ON  = 1
STATE_OFF = 2
STATE_TXT = {STATE_ON: "ON", STATE_OFF: "OFF"}


# --------------------------------------------------------------------------- #
# CyberPowerPDU — main class
# --------------------------------------------------------------------------- #
class CyberPowerPDU:
    """
    Controls a single CyberPower PDU over SNMPv1.

    Usage (from another script):
        pdu = CyberPowerPDU.from_config("devices.json", name="PDU-1")
        pdu.on(3)           # turn outlet 3 on
        pdu.off(3)          # turn outlet 3 off
        pdu.on_all()        # turn all outlets on
        pdu.off_all()       # turn all outlets off
        states = pdu.list_outlets()   # {1: "ON", 2: "OFF", ...}
        state  = pdu.get(1)           # "ON" | "OFF" | None
    """

    def __init__(
        self,
        ip: str,
        read_community: str = "public",
        write_community: str = "private",
        timeout: float = 10.0,
        retries: int = 1,
        name: str = "",
        outlet_oids: list[str] | None = None,
    ):
        self.ip              = ip
        self.read_community  = read_community
        self.write_community = write_community
        self.timeout         = timeout
        self.retries         = retries
        self.name            = name or ip
        self.outlet_oids     = outlet_oids or OUTLET_OIDS

    # ------------------------------------------------------------------ #
    # Class-level factory: load from JSON config
    # ------------------------------------------------------------------ #
    @classmethod
    def from_config(cls, config_path: str | Path, name: str) -> "CyberPowerPDU":
        """
        Load a named PDU from a devices.json file.

        devices.json format:
        {
          "pdus": [
            {
              "name": "PDU-1",
              "ip": "10.10.99.12",
              "read_community": "public",
              "write_community": "private",
              "timeout": 10,
              "retries": 1
            }
          ]
        }
        """
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Device config not found: {path}")

        with path.open() as f:
            config = json.load(f)

        for entry in config.get("pdus", []):
            if entry.get("name") == name:
                return cls(
                    ip              = entry["ip"],
                    read_community  = entry.get("read_community", "public"),
                    write_community = entry.get("write_community", "private"),
                    timeout         = entry.get("timeout", 10.0),
                    retries         = entry.get("retries", 1),
                    name            = entry["name"],
                    outlet_oids     = entry.get("outlet_oids", OUTLET_OIDS),
                )
        raise ValueError(f"PDU '{name}' not found in {path}")

    @classmethod
    def all_from_config(cls, config_path: str | Path) -> list["CyberPowerPDU"]:
        """Load every PDU defined in the config file."""
        path = Path(config_path)
        with path.open() as f:
            config = json.load(f)
        return [
            cls(
                ip              = entry["ip"],
                read_community  = entry.get("read_community", "public"),
                write_community = entry.get("write_community", "private"),
                timeout         = entry.get("timeout", 10.0),
                retries         = entry.get("retries", 1),
                name            = entry.get("name", entry["ip"]),
                outlet_oids     = entry.get("outlet_oids", OUTLET_OIDS),
            )
            for entry in config.get("pdus", [])
        ]

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _validate_outlet(self, idx: int) -> str:
        if idx < 1 or idx > len(self.outlet_oids):
            raise ValueError(
                f"Outlet index {idx} out of range (1–{len(self.outlet_oids)})"
            )
        return self.outlet_oids[idx - 1]

    async def _async_get(self, oid: str) -> Optional[int]:
        engine = SnmpEngine()
        try:
            error_indication, error_status, error_index, var_binds = await get_cmd(
                engine,
                CommunityData(self.read_community, mpModel=0),  # mpModel=0 → SNMPv1
                await UdpTransportTarget.create(
                    (self.ip, 161),
                    timeout=self.timeout,
                    retries=self.retries,
                ),
                ContextData(),
                ObjectType(ObjectIdentity(oid)),
            )
        finally:
            engine.close_dispatcher()

        if error_indication:
            logger.error("[%s] GET error: %s", self.name, error_indication)
            return None
        if error_status:
            logger.error(
                "[%s] GET error status: %s at %s",
                self.name,
                error_status.prettyPrint(),
                error_index,
            )
            return None

        _, val = var_binds[0]
        return int(val)

    async def _async_set(self, oid: str, state: int) -> bool:
        from pysnmp.proto.rfc1902 import Integer

        engine = SnmpEngine()
        try:
            error_indication, error_status, error_index, var_binds = await set_cmd(
                engine,
                CommunityData(self.write_community, mpModel=0),
                await UdpTransportTarget.create(
                    (self.ip, 161),
                    timeout=self.timeout,
                    retries=self.retries,
                ),
                ContextData(),
                ObjectType(ObjectIdentity(oid), Integer(state)),
            )
        finally:
            engine.close_dispatcher()

        if error_indication:
            logger.error("[%s] SET error: %s", self.name, error_indication)
            return False
        if error_status:
            logger.error(
                "[%s] SET error status: %s at %s",
                self.name,
                error_status.prettyPrint(),
                error_index,
            )
            return False
        return True

    def _run(self, coro):
        """Run an async coroutine from synchronous code."""
        return asyncio.run(coro)

    # ------------------------------------------------------------------ #
    # Public API — synchronous, safe to call from any script
    # ------------------------------------------------------------------ #
    def get(self, outlet: int) -> Optional[str]:
        """
        Return outlet state as "ON", "OFF", or None on error.

        pdu.get(1)  →  "ON"
        """
        oid   = self._validate_outlet(outlet)
        value = self._run(self._async_get(oid))
        state = STATE_TXT.get(value)
        logger.info("[%s] Outlet %d: %s", self.name, outlet, state or "READ FAILED")
        return state

    def on(self, outlet: int) -> bool:
        """
        Turn a single outlet ON. Returns True on success.

        pdu.on(3)
        """
        oid = self._validate_outlet(outlet)
        ok  = self._run(self._async_set(oid, STATE_ON))
        if ok:
            # Read-back verify
            after = self._run(self._async_get(oid))
            if after == STATE_ON:
                logger.info("[%s] Outlet %d → ON", self.name, outlet)
                return True
            logger.warning(
                "[%s] Outlet %d SET ON did not verify (read-back=%s)",
                self.name, outlet, after,
            )
            return False
        return False

    def off(self, outlet: int) -> bool:
        """
        Turn a single outlet OFF. Returns True on success.

        pdu.off(3)
        """
        oid = self._validate_outlet(outlet)
        ok  = self._run(self._async_set(oid, STATE_OFF))
        if ok:
            after = self._run(self._async_get(oid))
            if after == STATE_OFF:
                logger.info("[%s] Outlet %d → OFF", self.name, outlet)
                return True
            logger.warning(
                "[%s] Outlet %d SET OFF did not verify (read-back=%s)",
                self.name, outlet, after,
            )
            return False
        return False

    def on_all(self) -> dict[int, bool]:
        """
        Turn all outlets ON. Returns {outlet_index: success_bool}.

        results = pdu.on_all()
        """
        return {i: self.on(i) for i in range(1, len(self.outlet_oids) + 1)}

    def off_all(self) -> dict[int, bool]:
        """
        Turn all outlets OFF. Returns {outlet_index: success_bool}.

        results = pdu.off_all()
        """
        return {i: self.off(i) for i in range(1, len(self.outlet_oids) + 1)}

    def list_outlets(self) -> dict[int, Optional[str]]:
        """
        Return state of all outlets as {1: "ON", 2: "OFF", ...}.

        states = pdu.list_outlets()
        """
        return {i: self.get(i) for i in range(1, len(self.outlet_oids) + 1)}

    def __repr__(self) -> str:
        return f"CyberPowerPDU(name={self.name!r}, ip={self.ip!r})"


# --------------------------------------------------------------------------- #
# CLI — optional, mirrors original script interface
# --------------------------------------------------------------------------- #
def _build_parser():
    import argparse

    ap = argparse.ArgumentParser(
        description="CyberPower PDU control via pysnmp 7.x (Ubuntu/Linux)"
    )
    ap.add_argument(
        "--config",
        default=str(Path(__file__).parent / "devices.json"),
        help="Path to devices.json (default: ./devices.json)",
    )
    ap.add_argument(
        "--pdu",
        default=None,
        help="PDU name from config (omit to use first PDU)",
    )

    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("list")

    p_get = sub.add_parser("get")
    p_get.add_argument("outlet", type=int)

    p_on = sub.add_parser("on")
    p_on.add_argument("outlet", type=int)

    p_off = sub.add_parser("off")
    p_off.add_argument("outlet", type=int)

    sub.add_parser("on_all")
    sub.add_parser("off_all")

    ap.set_defaults(cmd="list")
    return ap


def main():
    ap    = _build_parser()
    args  = ap.parse_args()
    pdus  = CyberPowerPDU.all_from_config(args.config)

    if not pdus:
        print("No PDUs found in config.")
        sys.exit(1)

    if args.pdu:
        matches = [p for p in pdus if p.name == args.pdu]
        if not matches:
            print(f"PDU '{args.pdu}' not found in config.")
            sys.exit(1)
        pdu = matches[0]
    else:
        pdu = pdus[0]

    print(f"Using: {pdu}")

    if args.cmd == "list":
        states = pdu.list_outlets()
        for idx, state in states.items():
            print(f"  Outlet {idx}: {state or 'READ FAILED'}")

    elif args.cmd == "get":
        state = pdu.get(args.outlet)
        print(f"  Outlet {args.outlet}: {state or 'READ FAILED'}")

    elif args.cmd == "on":
        ok = pdu.on(args.outlet)
        sys.exit(0 if ok else 1)

    elif args.cmd == "off":
        ok = pdu.off(args.outlet)
        sys.exit(0 if ok else 1)

    elif args.cmd == "on_all":
        results = pdu.on_all()
        failed  = [i for i, ok in results.items() if not ok]
        if failed:
            print(f"Failed outlets: {failed}")
            sys.exit(1)

    elif args.cmd == "off_all":
        results = pdu.off_all()
        failed  = [i for i, ok in results.items() if not ok]
        if failed:
            print(f"Failed outlets: {failed}")
            sys.exit(1)


if __name__ == "__main__":
    main()
