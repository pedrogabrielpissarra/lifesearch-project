import sys
import os
import types

# 🔹 Mock do matplotlib para evitar erro em ambiente de teste
mock = types.ModuleType("matplotlib")
mock.use = lambda *args, **kwargs: None
mock.__version__ = "mocked"

# Submódulos necessários
mock_pyplot = types.SimpleNamespace(
    subplots=lambda *a, **kw: (None, None),
    savefig=lambda *a, **kw: None,
    close=lambda *a, **kw: None,
    tight_layout=lambda *a, **kw: None,
)
mock.pyplot = mock_pyplot

# Registrar mocks no sys.modules
sys.modules["matplotlib"] = mock
sys.modules["matplotlib.pyplot"] = mock_pyplot

# 🔹 Garante que a raiz do projeto esteja no sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
