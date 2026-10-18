"""Required offline Guardrails integration; install requirements-security-shadow.txt first."""

from evals.scorers.security_shadow import APPROVED_PACKAGES, scan_local


def test_real_validator_runs_without_network_or_temp_leak(tmp_path, monkeypatch):
    monkeypatch.setattr("tempfile.tempdir", str(tmp_path))
    result = scan_local("Mật khẩu giả cho kiểm thử.\npassword = 'KnoraCanary_188_x8k2'\n")
    assert result["status"] == "detected", result
    assert result["packages"] == APPROVED_PACKAGES
    assert result["diagnostics"]["blocked_network_attempts"] == 0
    assert list(tmp_path.iterdir()) == []
