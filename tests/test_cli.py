import pytest

from pv_vs_etf.cli import compute, main
from pv_vs_etf.model import AppConfig, balcony_defaults, load_config


class TestCompute:
    def test_compute_rooftop_default(self):
        res = compute(load_config(None))
        assert res["pv_irr"] is not None
        assert 0.02 < res["pv_irr"] < 0.20
        assert res["etf_net_return"] < 0.07
        assert res["pv_payback"] is not None and res["pv_payback"] < 25
        # reinvesting PV savings must beat pure ETF if PV IRR > 0
        assert res["etf_reinvest"].value_net[-1] > res["etf_lump"].value_net[-1]

    def test_compute_balcony(self):
        res = compute(balcony_defaults(AppConfig()))
        assert res["pv"].investment == pytest.approx(0.8 * 1200)
        assert res["pv_irr"] is not None
        assert res["pv_irr"] > 0.05  # balcony plants typically have high IRR


class TestCli:
    def test_main_prints_and_exits_zero(self, capsys):
        assert main(["--years", "20"]) == 0
        out = capsys.readouterr().out
        assert "PV IRR" in out
        assert "Endvermögen" in out

    def test_main_balcony_mode(self, capsys):
        assert main(["--mode", "balcony"]) == 0
        out = capsys.readouterr().out
        assert "balcony" in out

    def test_main_report(self, tmp_path, capsys):
        out_dir = tmp_path / "report_out"
        cfg = tmp_path / "config.toml"
        cfg.write_text(
            f'output_dir = "{out_dir}"\nreport_title = "Test Report"\n\n[pv]\nkwp = 8.0\n',
            encoding="utf-8",
        )
        rc = main(["--report", "--sensitivity", "--years", "20", "--config", str(cfg)])
        assert rc == 0
        report = out_dir / "report.html"
        assert report.exists()
        content = report.read_text(encoding="utf-8")
        assert "plotly" in content.lower()
        assert "Endvermögen" in content

    def test_invalid_override_returns_2(self, capsys):
        # invalid value via years=0 triggers validation error -> exit 2
        assert main(["--years", "0"]) == 2

    def test_version(self, capsys):
        with pytest.raises(SystemExit) as e:
            main(["--version"])
        assert e.value.code == 0
