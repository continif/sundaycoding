import argparse
import os
import pandas as pd
import matplotlib
matplotlib.use('Agg') # Forza Matplotlib a generare immagini senza richiedere una finestra video (ottimo per i server)
import matplotlib.pyplot as plt
import geoip2.database
import csv

# --- GESTIONE ARGOMENTI ---
# diciamogli di prendere il nome dell'access file da linea di comando: python test-analisi-log.py --logfile percorso/access.log
parser = argparse.ArgumentParser(description='Analizzatore di Log per Audit di Sicurezza')
parser.add_argument('--logfile', type=str, required=True, help='Percorso del file log di Apache')
args = parser.parse_args()

# Estrae il nome del file dal percorso (es. "access.log") per usarlo come titolo nel report. Pura cosmesi.
nome_sito = os.path.basename(args.logfile)


def carica_e_pulisci_log(path_file):
    """Versione pro che gestisce formati log incoerenti e caratteri speciali."""
    # Usiamo una regex che isola i campi tra virgolette o parentesi quadre
    # Questa è molto più precisa per i log di Apache/Nginx
    regex_pattern = r'\s(?=(?:[^"]*"[^"]*")*[^"]*$)(?![^\[]*\])'

    try:
        # Carichiamo il file
        df = pd.read_csv(
            path_file,
            sep=regex_pattern,
            engine='python',
            header=None,
            names=['Server_IP', 'Client_IP', 'Ident', 'User', 'Timestamp', 'Request', 'Status', 'Size', 'Referer', 'User_Agent'],
            on_bad_lines='skip', # Ignora le righe fatte male invece di crashare
            quoting=csv.QUOTE_MINIMAL, # Gestisce le virgolette in modo standard
            escapechar='\\' # Gestisce eventuali caratteri di escape nei log
        )

        if df.empty:
            return pd.DataFrame()

        # Pulizia Timestamp, levamo le [ ] e convertiamo in datetime
        df['Timestamp'] = df['Timestamp'].str.replace('[', '', regex=False).str.replace(']', '', regex=False)
        df['Timestamp'] = pd.to_datetime(df['Timestamp'], format='%d/%b/%Y:%H:%M:%S %z', errors='coerce')

        # Eliminiamo le righe dove il timestamp è fallito (NaT)
        df = df.dropna(subset=['Timestamp'])

        # Converto in numeri quelli che me servono come numeri
        df['Size'] = pd.to_numeric(df['Size'], errors='coerce').fillna(0)
        df['Status'] = pd.to_numeric(df['Status'], errors='coerce').fillna(0).astype(int)

        # Famo l'indice sul timestamp
        df.set_index('Timestamp', inplace=True)

        print(f"Analisi completata: {len(df)} righe caricate correttamente da {path_file}")
        return df

    except Exception as e:
        print(f"Errore irreversibile leggendo {path_file}: {e}")
        return pd.DataFrame()

def arricchisci_dati_rete(df, path_country, path_asn):
    """Interroga i database MaxMind per associare ad ogni IP una Nazione e un Provider (ASN)."""
    # questi dati sono free, dovete registravve per scaricalli.
    reader_geo = geoip2.database.Reader(path_country)
    reader_asn = geoip2.database.Reader(path_asn)

    ip_unici = df['Client_IP'].unique()

    def get_info(ip):
        try:
            geo = reader_geo.country(ip).country.name
            asn_data = reader_asn.asn(ip)
            # recupero ASN e Nome Organizzazione (es: AS15169 Google LLC)
            asn = f"AS{asn_data.autonomous_system_number} {asn_data.autonomous_system_organization}"
            return geo, asn
        except:
            # sennò niente
            return "Unknown", "Unknown"

    # Mappetta comoda: calcola i dati per gli IP unici e li applica a tutto il dataset (le prestazioni... ricordate?)
    mappa = {ip: get_info(ip) for ip in ip_unici}
    df['Country'] = df['Client_IP'].map(lambda x: mappa[x][0]) # aggiungo la colonna Country
    df['ASN'] = df['Client_IP'].map(lambda x: mappa[x][1])  # aggiungo la colonna ASN

    # chiudo quello che deve essere chiuso, che non si sa mai
    reader_geo.close()
    reader_asn.close()
    return df

def rileva_anomalie_statistiche(df):
    """Identifica picchi di traffico anomali per singolo ASN usando la deviazione standard (Z-Score)."""
    # Raggruppa le richieste ogni 30 minuti divise per ASN
    asn_timeline = df.groupby([pd.Grouper(freq='30min'), 'ASN']).size().unstack(fill_value=0)

    # Calcola media e deviazione standard per ogni provider
    stats_asn = pd.DataFrame({'media': asn_timeline.mean(), 'std': asn_timeline.std()})

    anomalie = []
    for asn in asn_timeline.columns:
        if asn == "Unknown" or stats_asn.loc[asn, 'std'] == 0: continue

        serie = asn_timeline[asn]
        # Soglia 3-Sigma: identifica valori che deviano drasticamente dalla norma (99.7% di confidenza)
        # Se non sai che è leggi qua: https://it.wikipedia.org/wiki/Regola_68-95-99,7
        soglia = stats_asn.loc[asn, 'media'] + (3 * stats_asn.loc[asn, 'std'])
        picchi = serie[serie > soglia]

        for ts, val in picchi.items():
            anomalie.append({
                'Timestamp': ts, 'ASN': asn, 'Richieste': val,
                'Z_Score': (val - stats_asn.loc[asn, 'media']) / stats_asn.loc[asn, 'std']
            })

    return pd.DataFrame(anomalie).sort_values(by='Z_Score', ascending=False)

# famo fa un report dall'IA che almeno giustificamo sti 20€ de spesa
def esegui_audit_sicurezza_html(df, df_anomalie, scanners, impostori, scrapers, titolo):
    """Genera i grafici e costruisce il report finale in formato HTML."""

    # --- GENERAZIONE GRAFICI ---
    # Grafico 1: Torta delle risposte HTTP (Salute del server)
    plt.figure(figsize=(6, 4))
    df['Status'].value_counts().plot(kind='pie', autopct='%1.1f%%', colors=['#4CAF50', '#FFC107', '#F44336', '#2196F3'])
    plt.title('Distribuzione Risposte HTTP')
    plt.savefig('plot_status.png')
    plt.close()

    # Grafico 2: Linee del traffico orario (Picchi temporali)
    plt.figure(figsize=(10, 4))
    df.resample('h').size().plot(color='#2196F3', linewidth=2)
    plt.title('Andamento Traffico (Richieste per Ora)')
    plt.grid(True, alpha=0.3)
    plt.savefig('plot_traffico.png')
    plt.close()

    # --- PREPARAZIONE REGOLE HTACCESS ---
    # Associa ad ogni IP sospetto il suo ASN per aggiungere commenti descrittivi nel file .htaccess
    mappa_ip_asn = df.groupby('Client_IP')['ASN'].first().to_dict()
    set_cattivi = set(list(scanners.index) + list(impostori['Client_IP'].unique()))

    righe_htaccess = []
    for ip in sorted(set_cattivi):
        if ip != "127.0.0.1": # Sicurezza: evita di bannare l'indirizzo locale
            info_asn = mappa_ip_asn.get(ip, "ASN sconosciuto")
            righe_htaccess.append(f"    Require not ip {ip:<15} # {info_asn}")

    # --- COSTRUZIONE HTML (STRUTTURA E CSS) ---
    html_content = f"""
    <html>
    <head>
        <title>Audit Sicurezza - {titolo}</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, sans-serif; margin: 40px; background-color: #f4f7f6; }}
            .container {{ background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
            h2 {{ color: #2980b9; margin-top: 30px; border-left: 5px solid #3498db; padding-left: 10px; }}
            table {{ border-collapse: collapse; width: 100%; margin: 20px 0; font-size: 14px; }}
            th, td {{ text-align: left; padding: 12px; border-bottom: 1px solid #ddd; }}
            th {{ background-color: #3498db; color: white; }}
            .stats-grid {{ display: flex; gap: 20px; margin-bottom: 20px; }}
            .stat-card {{ background: #34495e; color: white; padding: 20px; border-radius: 8px; flex: 1; text-align: center; }}
            .plots {{ display: flex; flex-wrap: wrap; gap: 20px; justify-content: center; }}
            pre {{ background: #272822; color: #a6e22e; padding: 15px; border-radius: 5px; overflow-x: auto; font-family: 'Courier New', monospace; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Audit Sicurezza: {titolo}</h1>
            <p>Report generato il: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

            <div class="stats-grid">
                <div class="stat-card"><h3>{len(df)}</h3><p>Richieste</p></div>
                <div class="stat-card"><h3>{len(scanners)}</h3><p>Scanner</p></div>
                <div class="stat-card"><h3>{len(impostori)}</h3><p>Impostori</p></div>
                <div class="stat-card"><h3>{len(scrapers)}</h3><p>Scrapers</p></div>
            </div>

            <div class="plots">
                <img src="plot_status.png" width="400">
                <img src="plot_traffico.png" width="600">
            </div>

            <h2>[1] Top Anomalie Statistiche (Z-Score)</h2>
            {df_anomalie.head(10).to_html(classes='table', index=False) if not df_anomalie.empty else "<p>Nessuna anomalia rilevata.</p>"}

            <h2>[2] Vulnerability Scanners Rilevati</h2>
            {scanners.sort_values(by='url_sensibili', ascending=False).head(10).to_html(classes='table') if not scanners.empty else "<p>Nessuno scanner rilevato.</p>"}

            <h2>[3] Scrapers Aggressivi</h2>
            {scrapers.sort_values(by='pagine', ascending=False).to_html(classes='table') if not scrapers.empty else "<p>Nessuno scraper rilevato.</p>"}

            <h2>[4] Finti Motori di Ricerca (Impostori)</h2>
            {impostori.groupby(['ASN', 'Client_IP']).size().reset_index(name='Conteggio').to_html(classes='table', index=False) if not impostori.empty else "<p>Nessun impostore rilevato.</p>"}

            <h2>[5] Configurazione .htaccess Suggerita</h2>
            <pre>
&lt;RequireAll&gt;
    Require all granted
{chr(10).join(righe_htaccess)}
&lt;/RequireAll&gt;
            </pre>
        </div>
    </body>
    </html>
    """
    with open(f"audit_{titolo}.html", "w") as f:
        f.write(html_content)
    print(f"✅ Report HTML generato con successo: audit_{titolo}.html")


# --- FLUSSO DI ESECUZIONE ---
# 1. Carico e arricchisco i dati di rete (Nazione e ASN) per ogni IP nei log
df = carica_e_pulisci_log(args.logfile)
df = arricchisci_dati_rete(df, 'GeoLite2-Country.mmdb', 'GeoLite2-ASN.mmdb')

# 2. Analisi delle anomalie temporali
df_anomalie = rileva_anomalie_statistiche(df)

# 3. Identificazione IMPOSTORI:
#    Mo qua ho messo Google e Bing, ma ce pòi mette quelli che te pare.
#    Se lo user agent dice di essere uno de questi ma l'ASN non corrisponde a quelli ufficiali è un cattivone.
#    Non è proprio precisa, ma cmq è l'idea che conta.
ASN_BUONI = ['AS15169 Google LLC', 'AS8075 Microsoft Corporation']
impostori = df[df['User_Agent'].str.contains('Googlebot|bingbot', case=False, na=False) & (~df['ASN'].isin(ASN_BUONI))]

# 4. Identificazione SCANNERS:
#     IP con tasso di errore altissimo (>90%) o che cercano file sensibili (.env, .git)
stats_ip = df.groupby('Client_IP').agg(
    totale=('Status', 'count'),
    errori=('Status', lambda x: (x >= 400).sum()),
    url_sensibili=('Request', lambda x: x.fillna('').str.contains(r'wp-admin|wp-login.php|xmlrpc|\.env|\.git', case=False).sum())
)
stats_ip['error_rate'] = (stats_ip['errori'] / stats_ip['totale']) * 100
scanners = stats_ip[(stats_ip['error_rate'] > 90) & (stats_ip['totale'] > 5) | (stats_ip['url_sensibili'] > 0)]

# 5. Identificazione SCRAPERS:
#    So' quelli che se scaricano un botto de pagine ma nun sò motori de ricerca (es. >100 pagine ma tasso di errore basso <10%)
report_scrapers = df.groupby('ASN').agg(
    pagine=('Request', 'count'),
    error_rate=('Status', lambda x: (x >= 400).mean() * 100)
)
scrapers = report_scrapers[(report_scrapers['pagine'] > 100) & (report_scrapers['error_rate'] < 10)]

# 6. Generazione del report finale
esegui_audit_sicurezza_html(df, df_anomalie, scanners, impostori, scrapers, nome_sito)
