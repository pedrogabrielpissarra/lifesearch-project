import sys
import os
import types

# Mock from matplotlib to avoid GUI issues during tests
mock = types.ModuleType("matplotlib")
mock.use = lambda *args, **kwargs: None
mock.__version__ = "mocked"

# Dummy bar to simulate bar objects returned by barh
class DummyBar:
    def get_width(self): return 42.0
    def get_y(self): return 1.0
    def get_height(self): return 0.5

class DummyAx:
    def axvspan(self, *a, **kw): return None
    def barh(self, *a, **kw): return [DummyBar()]  
    def plot(self, *a, **kw): return None
    def set_xlim(self, *a, **kw): return None
    def set_ylim(self, *a, **kw): return None
    def set_xlabel(self, *a, **kw): return None
    def set_ylabel(self, *a, **kw): return None
    def set_title(self, *a, **kw): return None
    def set_yticks(self, *a, **kw): return None
    def legend(self, *a, **kw): return None
    def text(self, *a, **kw): return None

dummy_ax = DummyAx()

# Fake savefig to avoid actual file creation
def fake_savefig(path, *a, **kw):
    with open(path, "wb") as f:
        f.write(b"")
    return None

# Submodule pyplot mock
mock_pyplot = types.SimpleNamespace(
    subplots=lambda *a, **kw: (None, dummy_ax),
    savefig=fake_savefig,
    close=lambda *a, **kw: None,
    tight_layout=lambda *a, **kw: None,
)
mock.pyplot = mock_pyplot

# Register the mock in sys.modules
sys.modules["matplotlib"] = mock
sys.modules["matplotlib.pyplot"] = mock_pyplot

# Ensure the parent directory is in sys.path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
