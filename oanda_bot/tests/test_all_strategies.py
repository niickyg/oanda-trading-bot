import glob
import importlib
import pytest


@pytest.mark.parametrize("modpath", glob.glob("strategy/*.py"))
def test_import_and_smoke(modpath):
    # Build module name and import it
    modname = modpath.replace("/", ".").rstrip(".py")
    module = importlib.import_module(modname)

    # Attempt to find a Strategy class; skip modules without one
    try:
        cls_name = next(name for name in dir(module) if name.startswith("Strategy"))
    except StopIteration:
        pytest.skip(f"No Strategy class found in {modname}")

    StratCls = getattr(module, cls_name)
    strat = StratCls({})

    # Prepare a minimal bars list
    bars = [{"mid": {"c": "1.0"}}] * 3
    sig = strat.next_signal(bars)
    assert sig in (None, "BUY", "SELL")
