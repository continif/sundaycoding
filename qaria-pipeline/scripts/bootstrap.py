#!/usr/bin/env python
"""
bootstrap.py — Prepara i dati di riferimento per la pipeline.

Crea l'anagrafica delle stazioni di rilevamento in data/reference/.
Nel mondo reale questa verrebbe scaricata dal portale CKAN di Milano
(dataset separato), ma per far girare la pipeline subito la generiamo
con coordinate realistiche delle vere centraline milanesi.

Uso:
    python scripts/bootstrap.py
"""

import sys
from pathlib import Path

# Aggiunge la root al path per importare qaria.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qaria import paths

# Anagrafica delle stazioni. Coordinate realistiche di centraline milanesi.
ANAGRAFICA = """stazione_id;nome;indirizzo;zona;latitudine;longitudine;tipologia
2;Milano - Pascal Città Studi;Via Pascal;est;45.4783;9.2335;urbana
3;Milano - Verziere;Largo Marinai d'Italia;centro;45.4636;9.1968;urbana
4;Milano - Senato;Corso Venezia;centro;45.4709;9.1989;traffico
5;Milano - Liguria;Via Liguria;sud;45.4419;9.1719;urbana
6;Milano - Marche;Viale Marche;nord;45.5024;9.1897;traffico
7;Milano - Cenisio;Via Cenisio;nordovest;45.4889;9.1631;urbana
"""


def main():
    paths.ensure_dirs()
    paths.ANAGRAFICA_PATH.write_text(ANAGRAFICA, encoding="utf-8")
    print(f"Anagrafica stazioni creata: {paths.ANAGRAFICA_PATH}")
    print("Ora puoi lanciare: python run_pipeline.py")


if __name__ == "__main__":
    main()
