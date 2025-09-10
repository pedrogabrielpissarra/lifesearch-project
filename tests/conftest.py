import sys
import os
import types

# 🔹 Mock do matplotlib para evitar erro em ambiente de teste
mock = types.ModuleType("matplotlib")
mock.use = lambda *args, **kwargs: None
mock.__version__ = "mocked"

# Dummy axis para suportar chamadas feitas em reports.py
class DummyAx:
    def axvspan(self, *a, **kw): return None
    def barh(self, *a, **kw): return []
    def plot(self, *a, **kw): return None
    def set_xlim(self, *a, **kw): return None
    def set_ylim(self, *a, **kw): return None
    def set_xlabel(self, *a, **kw): return None
    def set_ylabel(self, *a, **kw): return None
    def set_title(self, *a, **kw): return None
    def set_yticks(self, *a, **kw): return None
    def legend(self, *a, **kw): return None
    def text(self, *a, **kw): return None
    def axvspan(self, *a, **kw): return None
    def barh(self, *a, **kw): return []
    def plot(self, *a, **kw): return None
    def set_xlim(self, *a, **kw): return None
    def set_ylim(self, *a, **kw): return None
    def set_xlabel(self, *a, **kw): return None
    def set_ylabel(self, *a, **kw): return None
    def set_title(self, *a, **kw): return None
    def legend(self, *a, **kw): return None
    def text(self, *a, **kw): return None


dummy_ax = DummyAx()

# Função fake para simular salvamento de arquivos de gráfico
def fake_savefig(path, *a, **kw):
    # cria um arquivo vazio para simular a saída do matplotlib
    with open(path, "wb") as f:
        f.write(b"")
    return None

# Submódulos necessários
mock_pyplot = types.SimpleNamespace(
    subplots=lambda *a, **kw: (None, dummy_ax),
    savefig=fake_savefig,
    close=lambda *a, **kw: None,
    tight_layout=lambda *a, **kw: None,
)
mock.pyplot = mock_pyplot


# Registrar mocks no sys.modules
sys.modules["matplotlib"] = mock
sys.modules["matplotlib.pyplot"] = mock_pyplot


# 🔹 Garante que a raiz do projeto esteja no sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

