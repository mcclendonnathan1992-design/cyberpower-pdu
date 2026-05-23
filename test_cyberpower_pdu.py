"""
CyberPower PDU — Unit Tests (no network, no real PDU required)
==============================================================
All SNMP calls are mocked. Tests run fully offline on any machine
that has pysnmp installed.

Run:
    pytest test_cyberpower_pdu.py -v
"""

import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

SAMPLE_CONFIG = {
    "pdus": [
        {
            "name": "PDU-1",
            "ip": "10.10.99.12",
            "read_community": "public",
            "write_community": "private",
            "timeout": 10,
            "retries": 1,
        },
        {
            "name": "PDU-2",
            "ip": "10.10.99.13",
            "read_community": "public",
            "write_community": "private",
            "timeout": 10,
            "retries": 1,
        },
    ]
}


@pytest.fixture
def config_file(tmp_path):
    """Write a temporary devices.json and return its path."""
    p = tmp_path / "devices.json"
    p.write_text(json.dumps(SAMPLE_CONFIG))
    return p


@pytest.fixture
def pdu(config_file):
    """Return a CyberPowerPDU loaded from the temp config."""
    from cyberpower_pdu import CyberPowerPDU
    return CyberPowerPDU.from_config(config_file, name="PDU-1")


# --------------------------------------------------------------------------- #
# Helper: build a fake pysnmp var_bind response
# --------------------------------------------------------------------------- #
def _fake_varbind(value: int):
    """Return a (oid, int-value) tuple that mimics pysnmp var_binds."""
    mock_val = MagicMock()
    mock_val.__int__ = lambda self: value
    mock_val.__index__ = lambda self: value
    # int(mock_val) must return the value
    type(mock_val).__int__ = lambda self: value
    return [("1.3.6.1.4.1.3808.1.1.3.3.3.1.1.4.1", mock_val)]


def _snmp_get_response(value: int):
    """Simulate a successful SNMP GET: (no error, no status, 0, varbinds)."""
    mock_val = MagicMock()
    # Make int(mock_val) return value
    mock_val.__class__ = type(
        "Integer",
        (),
        {"__int__": lambda self: value, "__index__": lambda self: value},
    )
    return (None, None, 0, [("oid", mock_val)])


# --------------------------------------------------------------------------- #
# Config loading tests
# --------------------------------------------------------------------------- #

class TestConfigLoading:

    def test_load_single_pdu_by_name(self, config_file):
        from cyberpower_pdu import CyberPowerPDU
        pdu = CyberPowerPDU.from_config(config_file, name="PDU-1")
        assert pdu.ip == "10.10.99.12"
        assert pdu.name == "PDU-1"
        assert pdu.read_community == "public"
        assert pdu.write_community == "private"

    def test_load_second_pdu_by_name(self, config_file):
        from cyberpower_pdu import CyberPowerPDU
        pdu = CyberPowerPDU.from_config(config_file, name="PDU-2")
        assert pdu.ip == "10.10.99.13"

    def test_load_all_pdus(self, config_file):
        from cyberpower_pdu import CyberPowerPDU
        pdus = CyberPowerPDU.all_from_config(config_file)
        assert len(pdus) == 2
        assert pdus[0].name == "PDU-1"
        assert pdus[1].name == "PDU-2"

    def test_missing_config_file_raises(self, tmp_path):
        from cyberpower_pdu import CyberPowerPDU
        with pytest.raises(FileNotFoundError):
            CyberPowerPDU.from_config(tmp_path / "missing.json", name="PDU-1")

    def test_missing_pdu_name_raises(self, config_file):
        from cyberpower_pdu import CyberPowerPDU
        with pytest.raises(ValueError, match="PDU-99"):
            CyberPowerPDU.from_config(config_file, name="PDU-99")

    def test_default_outlet_oids_loaded(self, pdu):
        from cyberpower_pdu import OUTLET_OIDS
        assert pdu.outlet_oids == OUTLET_OIDS
        assert len(pdu.outlet_oids) == 8

    def test_custom_outlet_oids_in_config(self, tmp_path):
        from cyberpower_pdu import CyberPowerPDU
        custom_oids = ["1.3.6.1.4.1.3808.1.1.3.3.3.1.1.4.1"]
        config = {"pdus": [{"name": "X", "ip": "1.2.3.4", "outlet_oids": custom_oids}]}
        p = tmp_path / "custom.json"
        p.write_text(json.dumps(config))
        pdu = CyberPowerPDU.from_config(p, name="X")
        assert pdu.outlet_oids == custom_oids


# --------------------------------------------------------------------------- #
# Outlet index validation tests
# --------------------------------------------------------------------------- #

class TestOutletValidation:

    def test_valid_outlet_index_low(self, pdu):
        oid = pdu._validate_outlet(1)
        assert oid == "1.3.6.1.4.1.3808.1.1.3.3.3.1.1.4.1"

    def test_valid_outlet_index_high(self, pdu):
        oid = pdu._validate_outlet(8)
        assert oid == "1.3.6.1.4.1.3808.1.1.3.3.3.1.1.4.8"

    def test_outlet_index_zero_raises(self, pdu):
        with pytest.raises(ValueError):
            pdu._validate_outlet(0)

    def test_outlet_index_too_high_raises(self, pdu):
        with pytest.raises(ValueError):
            pdu._validate_outlet(9)

    def test_outlet_index_negative_raises(self, pdu):
        with pytest.raises(ValueError):
            pdu._validate_outlet(-1)


# --------------------------------------------------------------------------- #
# GET tests (mocked SNMP)
# --------------------------------------------------------------------------- #

class TestGetOutlet:

    def _make_get_mock(self, return_value: int):
        """Return an AsyncMock that simulates a successful SNMP GET."""
        mock_int = MagicMock()
        type(mock_int).__int__ = lambda self: return_value

        async def fake_get(*args, **kwargs):
            return (None, None, 0, [("oid", mock_int)])

        return fake_get

    def test_get_returns_on(self, pdu):
        with patch("cyberpower_pdu.get_cmd", new=self._make_get_mock(1)), \
             patch("cyberpower_pdu.UdpTransportTarget.create", new_callable=AsyncMock) as mock_transport:
            mock_transport.return_value = MagicMock()
            result = pdu.get(1)
        assert result == "ON"

    def test_get_returns_off(self, pdu):
        with patch("cyberpower_pdu.get_cmd", new=self._make_get_mock(2)), \
             patch("cyberpower_pdu.UdpTransportTarget.create", new_callable=AsyncMock) as mock_transport:
            mock_transport.return_value = MagicMock()
            result = pdu.get(1)
        assert result == "OFF"

    def test_get_snmp_error_returns_none(self, pdu):
        async def fake_get_error(*args, **kwargs):
            return ("Timeout", None, 0, [])

        with patch("cyberpower_pdu.get_cmd", new=fake_get_error), \
             patch("cyberpower_pdu.UdpTransportTarget.create", new_callable=AsyncMock) as mock_transport:
            mock_transport.return_value = MagicMock()
            result = pdu.get(1)
        assert result is None

    def test_get_invalid_outlet_raises(self, pdu):
        with pytest.raises(ValueError):
            pdu.get(99)


# --------------------------------------------------------------------------- #
# SET / on / off tests (mocked SNMP)
# --------------------------------------------------------------------------- #

class TestSetOutlet:

    def _make_set_then_get_mock(self, set_succeeds: bool, readback_value: int):
        """
        Mock both set_cmd and get_cmd:
        - set_cmd returns success or error
        - get_cmd (read-back) returns readback_value
        """
        async def fake_set(*args, **kwargs):
            if set_succeeds:
                return (None, None, 0, [])
            return ("Timeout", None, 0, [])

        mock_int = MagicMock()
        type(mock_int).__int__ = lambda self: readback_value

        async def fake_get(*args, **kwargs):
            return (None, None, 0, [("oid", mock_int)])

        return fake_set, fake_get

    def test_on_success(self, pdu):
        fake_set, fake_get = self._make_set_then_get_mock(True, 1)
        with patch("cyberpower_pdu.set_cmd", new=fake_set), \
             patch("cyberpower_pdu.get_cmd", new=fake_get), \
             patch("cyberpower_pdu.UdpTransportTarget.create", new_callable=AsyncMock) as m:
            m.return_value = MagicMock()
            result = pdu.on(1)
        assert result is True

    def test_off_success(self, pdu):
        fake_set, fake_get = self._make_set_then_get_mock(True, 2)
        with patch("cyberpower_pdu.set_cmd", new=fake_set), \
             patch("cyberpower_pdu.get_cmd", new=fake_get), \
             patch("cyberpower_pdu.UdpTransportTarget.create", new_callable=AsyncMock) as m:
            m.return_value = MagicMock()
            result = pdu.off(1)
        assert result is True

    def test_on_set_fails_returns_false(self, pdu):
        fake_set, fake_get = self._make_set_then_get_mock(False, 2)
        with patch("cyberpower_pdu.set_cmd", new=fake_set), \
             patch("cyberpower_pdu.get_cmd", new=fake_get), \
             patch("cyberpower_pdu.UdpTransportTarget.create", new_callable=AsyncMock) as m:
            m.return_value = MagicMock()
            result = pdu.on(1)
        assert result is False

    def test_on_readback_mismatch_returns_false(self, pdu):
        # SET succeeds but read-back shows still OFF
        fake_set, fake_get = self._make_set_then_get_mock(True, 2)
        with patch("cyberpower_pdu.set_cmd", new=fake_set), \
             patch("cyberpower_pdu.get_cmd", new=fake_get), \
             patch("cyberpower_pdu.UdpTransportTarget.create", new_callable=AsyncMock) as m:
            m.return_value = MagicMock()
            result = pdu.on(1)
        assert result is False

    def test_on_invalid_outlet_raises(self, pdu):
        with pytest.raises(ValueError):
            pdu.on(0)

    def test_off_invalid_outlet_raises(self, pdu):
        with pytest.raises(ValueError):
            pdu.off(9)


# --------------------------------------------------------------------------- #
# on_all / off_all / list_outlets tests
# --------------------------------------------------------------------------- #

class TestBulkOperations:

    def test_on_all_returns_dict_of_8(self, pdu):
        with patch.object(pdu, "on", return_value=True) as mock_on:
            results = pdu.on_all()
        assert len(results) == 8
        assert all(v is True for v in results.values())
        assert mock_on.call_count == 8

    def test_off_all_returns_dict_of_8(self, pdu):
        with patch.object(pdu, "off", return_value=True) as mock_off:
            results = pdu.off_all()
        assert len(results) == 8
        assert mock_off.call_count == 8

    def test_list_outlets_returns_dict_of_8(self, pdu):
        with patch.object(pdu, "get", return_value="ON"):
            states = pdu.list_outlets()
        assert len(states) == 8
        assert all(v == "ON" for v in states.values())

    def test_on_all_partial_failure(self, pdu):
        # Outlets 1-7 succeed, outlet 8 fails
        def side_effect(idx):
            return idx != 8
        with patch.object(pdu, "on", side_effect=side_effect):
            results = pdu.on_all()
        assert results[7] is True
        assert results[8] is False

    def test_outlet_indices_are_1_based(self, pdu):
        """Ensure on_all calls outlets 1 through 8, not 0 through 7."""
        called_with = []
        with patch.object(pdu, "on", side_effect=lambda i: called_with.append(i) or True):
            pdu.on_all()
        assert called_with == list(range(1, 9))


# --------------------------------------------------------------------------- #
# repr test
# --------------------------------------------------------------------------- #

class TestRepr:

    def test_repr_contains_name_and_ip(self, pdu):
        r = repr(pdu)
        assert "PDU-1" in r
        assert "10.10.99.12" in r
