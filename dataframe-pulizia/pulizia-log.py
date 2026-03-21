import argparse
import os
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import geoip2.database
import csv
import time
import functools
import requests
from bs4 import BeautifulSoup
import datetime


# --- GESTIONE ARGOMENTI ---
parser = argparse.ArgumentParser(description='Analizzatore di Log per Audit di Sicurezza')
parser.add_argument('--logfile', type=str, required=True, help='Percorso del file log di Apache')
parser.add_argument('--sitemap', type=str, required=False, help='URL della sitemap_index.xml del sito')
args = parser.parse_args()

nome_sito = os.path.basename(args.logfile)

def timing(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        inizio = time.perf_counter()
        risultato = func(*args, **kwargs)
        fine = time.perf_counter()
        print(f"--- [TIMER] Tempo impiegato: {fine - inizio:.4f} secondi ---")
        return risultato
    return wrapper

@timing
def carica_e_pulisci_log(path_file):
    # Niente di nuovo, l'ho preso dallo script dell'altra volta.
    regex_pattern = r'\s(?=(?:[^"]*"[^"]*")*[^"]*$)(?![^\[]*\])'
    try:
        df = pd.read_csv(
            path_file,
            sep=regex_pattern,
            engine='python',
            header=None,
            names=['Server_IP', 'Client_IP', 'Ident', 'User', 'Timestamp', 'Request', 'Status', 'Size', 'Referer', 'User_Agent'],
            on_bad_lines='skip',
            quoting=csv.QUOTE_MINIMAL,
            escapechar='\\'
        )
        if df.empty: return pd.DataFrame()

        df['Timestamp'] = df['Timestamp'].str.replace('[', '', regex=False).str.replace(']', '', regex=False)
        df['Timestamp'] = pd.to_datetime(df['Timestamp'], format='%d/%b/%Y:%H:%M:%S %z', errors='coerce')
        df = df.dropna(subset=['Timestamp'])
        df['Size'] = pd.to_numeric(df['Size'], errors='coerce').fillna(0)
        df['Status'] = pd.to_numeric(df['Status'], errors='coerce').fillna(0).astype(int)
        df.set_index('Timestamp', inplace=True)

        print(f"Analisi completata: {len(df)} righe caricate correttamente")
        return df
    except Exception as e:
        print(f"Errore: {e}")
        return pd.DataFrame()

@timing
def arricchisci_dati_rete(df, path_country, path_asn):
    # Pure questo l'ho preso dallo script dell'altra volta.
    try:
        reader_geo = geoip2.database.Reader(path_country)
        reader_asn = geoip2.database.Reader(path_asn)
        ip_unici = df['Client_IP'].unique()

        def get_info(ip):
            try:
                geo = reader_geo.country(ip).country.name
                asn_data = reader_asn.asn(ip)
                asn = f"AS{asn_data.autonomous_system_number} {asn_data.autonomous_system_organization}"
                return geo, asn
            except: return "Unknown", "Unknown"

        mappa = {ip: get_info(ip) for ip in ip_unici}
        df['Country'] = df['Client_IP'].map(lambda x: mappa[x][0])
        df['ASN'] = df['Client_IP'].map(lambda x: mappa[x][1])
        reader_geo.close()
        reader_asn.close()
        return df
    except Exception as e:
        print(f"Errore database GeoIP: {e}. Saltiamo l'arricchimento.")
        df['Country'], df['ASN'] = "Unknown", "Unknown"
        return df


# --- PULIZIA E SETUP ---
@timing
def workshop_pulizia_dati(df):
    """
    Dimostrazione pratica di:
    1. Settaggio dati vuoti (fillna/replace)
    2. Estrazione dati (str.extract)
    3. Cancellazione dati (drop/filter)
    """
    if df.empty: return df

    # --- 1. DATI VUOTI ---
    # In molti log, i dati mancanti sono indicati con "-".
    # Li normalizziamo in NaN e poi mettiamo dei valori un po' più intelligenti di "-".
    df = df.replace('-', pd.NA)

    # Riempio i vuoti, tipo se l'utente non è loggato ci metto 'guest' che fa figo.
    df['User'] = df['User'].fillna('guest')

    # Se il Referer è vuoto ci metto "Direct"
    df['Referer'] = df['Referer'].fillna('"Direct"')

    # --- 2. ESTRAZIONE DATI (AKA: FEATURE ENGINEERING) ---
    # Uso str.extract per creare colonne strutturate da una stringa formattata (la Request)
    # Piglio il metodo (GET/POST) e ci faccio una colonna
    df['HTTP_Method'] = df['Request'].str.replace('"', '').str.split().str[0].fillna('UNKNOWN')

    # Prendo l'estensione e ci faccio una colonna, se manca metto 'html'
    df['File_Ext'] = df['Request'].str.extract(r'\.([a-z0-9]+)(?:[\s\?]|$)').fillna('html')

    # --- 3. CANCELLAZIONE E FILTRAGGIO ---
    # Butto via la spazzatura, tipo le richieste in Timeout (408) e quelle con 0 byte (maledetti!)
    # Droppo tutto!
    df.drop(df[df['Status'] == 408].index, inplace=True)

    # Leviamo le richieste inutili o dei bot che sono note, tipo le favicon e quelle a robots.txt
    df = df[~df['Request'].str.contains('favicon.ico|robots.txt', case=False, na=False)]

    print(f"Pulizia completata. Righe rimanenti: {len(df)}")
    return df

@timing
def analizza_e_aggrega(df):
    """Analisi aggregata con gestione sicura dei valori mancanti."""

    # Funzioncina per controllare i valori... (Ah! Quanto amo Python!)
    def get_prevalente(x):
        m = x.mode()
        return m.iloc[0] if not m.empty else 'N/A'

    analisi = df.groupby('ASN').agg(
        pagine_richiamate=('Request', 'count'),
        peso_medio=('Size', 'mean'),
        # ...che uso qua:
        metodo_prevalente=('HTTP_Method', get_prevalente)
    ).sort_values(by='pagine_richiamate', ascending=False)

    return analisi

# --- ESECUZIONE ---
# 1. Caricamento e pulizia base
df = carica_e_pulisci_log(args.logfile)

if not df.empty:
    # 2. Arricchimento, ma solo di dati, niente soldi
    df = arricchisci_dati_rete(df, 'GeoLite2-Country.mmdb', 'GeoLite2-ASN.mmdb')

    # 3. Workshop di Pulizia Avanzata
    df = workshop_pulizia_dati(df)

    # 4. Aggregazione, calcoli... roba per mostrare che funziona tutto
    risultato = analizza_e_aggrega(df)

    print("\n--- ANTEPRIMA DATI PULITI ---")
    print(df[['Client_IP', 'ASN', 'HTTP_Method', 'File_Ext']].head())

    print("\n--- REPORT SINTETICO ---")
    print(risultato.head(10))

    # DataFrame "purgato"
    df.to_csv(f"purgato_{nome_sito}.csv")
