from __future__ import annotations

from vpnforge.services import bbr
from vpnforge.shell import CommandResult


class BbrRunner:
    def __init__(self, *, available: bool = True, active: bool = True):
        self.available = available
        self.active = active
        self.commands: list[list[str]] = []

    def run(self, command, **kwargs):
        command = list(command)
        self.commands.append(command)
        if command[-1] == "net.ipv4.tcp_available_congestion_control":
            value = "reno cubic bbr\n" if self.available else "reno cubic\n"
            return CommandResult(0, value)
        if command[-1] == "net.ipv4.tcp_congestion_control":
            return CommandResult(0, "bbr\n" if self.active else "cubic\n")
        if command[-1] == "net.core.default_qdisc":
            return CommandResult(0, "fq\n" if self.active else "fq_codel\n")
        return CommandResult(0)


def test_apply_bbr_writes_owned_sysctl_config(monkeypatch, paths, tmp_path):
    monkeypatch.setenv("VPNFORGE_SYSCTL_DIR", str(tmp_path / "sysctl.d"))
    monkeypatch.setattr(bbr, "is_linux", lambda: True)
    monkeypatch.setattr(bbr, "is_root", lambda: True)
    runner = BbrRunner()

    status = bbr.apply_bbr(paths, runner)

    assert status.active is True
    assert bbr.bbr_config_path(paths).read_text(encoding="utf-8") == bbr.BBR_CONFIG
    assert ["sysctl", "--system"] in runner.commands


def test_disabling_bbr_removes_only_vpnforge_config(monkeypatch, paths, tmp_path):
    monkeypatch.setenv("VPNFORGE_SYSCTL_DIR", str(tmp_path / "sysctl.d"))
    config = bbr.bbr_config_path(paths)
    config.parent.mkdir(parents=True)
    config.write_text(bbr.BBR_CONFIG, encoding="utf-8")
    unrelated = config.parent / "10-custom.conf"
    unrelated.write_text("net.ipv4.ip_forward=1\n", encoding="utf-8")

    assert bbr.configure_bbr(paths, False, BbrRunner()) is None

    assert not config.exists()
    assert unrelated.is_file()


def test_apply_bbr_rejects_unsupported_kernel(monkeypatch, paths, tmp_path):
    monkeypatch.setenv("VPNFORGE_SYSCTL_DIR", str(tmp_path / "sysctl.d"))
    monkeypatch.setattr(bbr, "is_linux", lambda: True)
    monkeypatch.setattr(bbr, "is_root", lambda: True)
    runner = BbrRunner(available=False, active=False)

    try:
        bbr.apply_bbr(paths, runner)
    except RuntimeError as error:
        assert "does not provide TCP BBR" in str(error)
    else:
        raise AssertionError("Expected unsupported kernel error")
    assert ["modprobe", "tcp_bbr"] in runner.commands
