import pandas as pd
from contextlib import contextmanager
import time

@contextmanager
def timer(etichetta):
    """Mi creo un decorator per calcolare il tempo di esecuzione di una operazione."""
    inizio = time.perf_counter()
    yield
    fine = time.perf_counter()
    print(f"\n[{etichetta}] Tempo: {fine - inizio:.6f} s\n")
