import os
import sys

# Garante que os modulos locais (core/, modules/) do bundle sejam importaveis
_meipass = getattr(sys, "_MEIPASS", None)
if _meipass and _meipass not in sys.path:
    sys.path.insert(0, _meipass)
