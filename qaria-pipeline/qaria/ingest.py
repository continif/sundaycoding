"""
ingest.py — Ingestion qualità aria Milano (S03E01).

Scarica i dati grezzi dal portale CKAN del Comune di Milano e li salva
nel layer raw/ in modo immutabile e atomico.

Pattern chiave:
  - raw layer immutabile: i bytes esatti come arrivano, mai modificati
  - salvataggio atomico: file .tmp + rename, niente file troncati
  - naming a catena: qaria_<timestamp>_<hash8>.raw.csv
  - metadata JSONL: un record per ogni fetch, in fetches.jsonl
  - classificazione errori per 'kind': timeout, http, duplicate_raw, ...
"""

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import requests

from . import paths

log = logging.getLogger("ingest")

# Endpoint CKAN del portale Open Data di Milano.
# NB: il resource_id può cambiare nel tempo. Se il download fallisce,
# la pipeline genera dati sintetici (vedi _genera_dati_sintetici) così
# il lettore può comunque vedere tutta la pipeline funzionare.
CKAN_BASE = "https://dati.comune.milano.it/api/3/action"
DATASET_ID = "qualita-aria-stazioni"  # esempio; il fetch reale è opzionale

TIMEOUT_SEC = 30


def _timestamp() -> str:
    """Timestamp UTC ordinabile lessicograficamente (= cronologicamente)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")


def _hash8(contenuto: bytes) -> str:
    """Primi 8 caratteri dello SHA-256 del contenuto. Identifica il dato."""
    return hashlib.sha256(contenuto).hexdigest()[:8]


def _salva_atomico(path: Path, contenuto: bytes) -> None:
    """
    Salvataggio atomico: scrive su .tmp, poi rinomina.
    Garantisce che nessun lettore veda mai un file a metà.
    (Vedi lo speciale pubblico 'Python e il mistero dei file scomparsi'.)
    """
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("wb") as f:
        f.write(contenuto)
        f.flush()
        os.fsync(f.fileno())  # forza la scrittura su disco fisico
    os.replace(tmp, path)  # rename atomico


def _genera_dati_sintetici() -> bytes:
    """
    Genera un CSV sintetico ma realistico, per far girare la pipeline
    anche senza connessione o se il portale CKAN è cambiato.

    Riproduce le caratteristiche del dataset reale, inclusi i casi
    'difficili' che la pipeline deve saper gestire:
      - stazione 6 con alcuni zeri sentinel (C6H6=0, CO_8h=0)
      - formato long: una riga per (stazione, data, inquinante)
    """
    import random
    from datetime import date, timedelta

    random.seed(42)  # riproducibile
    oggi = date.today()

    stazioni = [2, 3, 4, 5, 6, 7]
    inquinanti = ["C6H6", "CO_8h", "NO2", "O3", "PM10", "PM25", "SO2"]

    righe = ["stazione_id;data;inquinante;valore"]
    for delta in range(7):  # ultimi 7 giorni
        giorno = (oggi - timedelta(days=delta)).isoformat()
        for sid in stazioni:
            for inq in inquinanti:
                # Stazione 6: sensore "rotto" su benzene e CO -> zeri sentinel
                if sid == 6 and inq in ("C6H6", "CO_8h"):
                    valore = "0"
                else:
                    base = {
                        "C6H6": 2.5, "CO_8h": 0.8, "NO2": 45, "O3": 60,
                        "PM10": 30, "PM25": 18, "SO2": 5,
                    }[inq]
                    valore = f"{base * random.uniform(0.5, 1.8):.1f}"
                righe.append(f"{sid};{giorno};{inq};{valore}")

    return ("\n".join(righe) + "\n").encode("utf-8")


def _scarica_da_ckan() -> bytes | None:
    """
    Tenta il download reale dal CKAN di Milano.
    Ritorna i bytes del CSV, oppure None se il download non riesce
    (in tal caso il chiamante userà i dati sintetici).
    """
    try:
        # Step 1: package_show per scoprire le risorse del dataset.
        r = requests.get(
            f"{CKAN_BASE}/package_show",
            params={"id": DATASET_ID},
            timeout=TIMEOUT_SEC,
        )
        r.raise_for_status()
        package = r.json()
        resources = package.get("result", {}).get("resources", [])
        csv_resources = [res for res in resources if res.get("format", "").upper() == "CSV"]
        if not csv_resources:
            log.warning("Nessuna risorsa CSV trovata nel dataset CKAN")
            return None

        # Step 2: scarica il primo CSV disponibile.
        url = csv_resources[0]["url"]
        r2 = requests.get(url, timeout=TIMEOUT_SEC)
        r2.raise_for_status()
        return r2.content

    except requests.exceptions.RequestException as e:
        log.warning(f"Download CKAN fallito ({e}), userò dati sintetici")
        return None


def run() -> dict:
    """
    Entry point dell'ingestion.

    Ritorna un dict con almeno 'status' ('ok' | 'error') e, in caso
    di errore, un 'kind' che classifica il tipo di problema.
    """
    paths.ensure_dirs()
    fetch_ts = datetime.now(timezone.utc)

    try:
        # Tenta il download reale; in mancanza, dati sintetici.
        contenuto = _scarica_da_ckan()
        usato_sintetico = contenuto is None
        if usato_sintetico:
            contenuto = _genera_dati_sintetici()

        h = _hash8(contenuto)
        nome = f"qaria_{_timestamp()}_{h}.raw.csv"
        out_path = paths.RAW_DIR / nome

        # Deduplicazione: se esiste già un raw con lo stesso hash di oggi,
        # è lo stesso dato. Non lo riscriviamo (raw è immutabile).
        esistenti = list(paths.RAW_DIR.glob(f"qaria_*_{h}.raw.csv"))
        if esistenti:
            log.info(f"Dato già presente (hash {h}), skip: {esistenti[0].name}")
            return {
                "status": "ok",
                "kind": "duplicate_raw",
                "raw_path": str(esistenti[0]),
                "note": "dato identico già scaricato",
            }

        _salva_atomico(out_path, contenuto)
        log.info(f"Salvato raw: {out_path.name} ({len(contenuto)} bytes)")

        # Audit JSONL
        record = {
            "pipeline": paths.PIPELINE_NAME,
            "fetch_ts_utc": fetch_ts.isoformat(),
            "raw_path": str(out_path),
            "size_bytes": len(contenuto),
            "sha256_8": h,
            "fonte": "sintetica" if usato_sintetico else "ckan",
            "status": "ok",
        }
        meta_path = paths.META_DIR / "fetches.jsonl"
        with meta_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        return {"status": "ok", "raw_path": str(out_path), "fonte": record["fonte"]}

    except Exception as e:
        log.exception(f"Errore imprevisto in ingestion: {e}")
        return {"status": "error", "kind": "unknown", "msg": str(e)}


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    print(json.dumps(run(), indent=2, default=str))
