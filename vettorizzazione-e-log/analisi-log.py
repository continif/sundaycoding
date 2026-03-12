import argparse
import os
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import geoip2.database
import csv

# --- GESTIONE ARGOMENTI ---
parser = argparse.ArgumentParser(description='Analizzatore di Log per Audit di Sicurezza')
parser.add_argument('--logfile', type=str, required=True, help='Percorso del file log di Apache')
args = parser.parse_args()

nome_sito = os.path.basename(args.logfile)

def carica_e_pulisci_log(path_file):
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

def arricchisci_dati_rete(df, path_country, path_asn):
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

def cerca_bastardi(df):
    """Cerchiamo i ladri di account!"""
    if df.empty: return pd.DataFrame()
    pattern_sensibile = r'\.env|\.git|wp-config|config\.php|\.htaccess|etc/passwd'
    mask = df['Request'].str.contains(pattern_sensibile, case=False, na=False) # usiamo le funzioni native invece di fare noiosissimi for.
    bastardi = df[mask].copy()
    if not bastardi.empty:
        return bastardi.groupby(['Client_IP', 'Country', 'ASN']).agg(
            tentativi=('Request', 'count'),
            cosa_cercavano=('Request', lambda x: ', '.join(x.unique()[:3]))
        ).sort_values(by='tentativi', ascending=False)
    return pd.DataFrame()

def rileva_rompicojons(df, limite_tentativi=5, secondi=30):
    """Cerchiamo quelli che provano a fare login con il brute force!"""
    if df.empty: return pd.DataFrame()
    pattern_login = r'wp-login\.php|wp-admin|/login'
    df_login = df[df['Request'].str.contains(pattern_login, case=False, na=False)].copy() # tiriamo fuori le url del login (qui Wordpress)
    if df_login.empty: return pd.DataFrame()

    df_pro = df_login.groupby(['Client_IP', 'Timestamp', 'Country', 'ASN']).size().reset_index(name='count_istantaneo') # Raggruppiamo e contiamo
    df_pro = df_pro.sort_values(['Client_IP', 'Timestamp']) # Ordiniamo sennò tira fuori dati a cazzo

    frequenza = f'{secondi}s'
    df_pro['velocita'] = df_pro.groupby('Client_IP').rolling(frequenza, on='Timestamp')['count_istantaneo'].sum().values # rolling ci salva le chiappette!

    rompicojons = df_pro[df_pro['velocita'] > limite_tentativi] # questi sono quelli che hanno sbagliato più di 5 volte in 30 secondi
    if not rompicojons.empty:
        return rompicojons.groupby(['Client_IP', 'Country', 'ASN']).agg(
            max_velocita_rilevata=('velocita', 'max'),
            totale_martellate=('count_istantaneo', 'sum')
        ).sort_values(by='max_velocita_rilevata', ascending=False) # raggruppiamo per tentativi e frequenza
    return pd.DataFrame() # non c'è niente di strano, mejo così!

def genera_scudo_htaccess(bastardi, rompicojons):
    """Prepara il codice per l'.htaccess"""
    ip_map = {}
    if not bastardi.empty:
        temp_b = bastardi.reset_index()
        for _, row in temp_b.iterrows(): ip_map[row['Client_IP']] = row['ASN']
    if not rompicojons.empty:
        temp_r = rompicojons.reset_index()
        for _, row in temp_r.iterrows(): ip_map[row['Client_IP']] = row['ASN']

    if not ip_map: return ""
    linee = ["<RequireAll>", "    Require all granted"]
    for ip in sorted(ip_map.keys()):
        linee.append(f"    Require not ip {ip:<15} # {ip_map[ip]}")
    linee.append("</RequireAll>")
    return "\n".join(linee)

def salva_report_html(bastardi, rompicojons, nome_file="report_sicurezza.html"):
    """Prepara il report"""
    stile_css = """
    <style>
        body { font-family: 'Segoe UI', sans-serif; margin: 40px; background: #f8f9fa; }
        .container { max-width: 1100px; margin: auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
        h1 { color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }
        h2 {
            color: #2980b9;
            margin-top: 30px;
            border-left: 5px solid #3498db;
            padding-left: 10px;
        }
        table { border-collapse: collapse; width: 100%; margin: 20px 0; font-size: 0.9em; }
        th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }
        th { background-color: #2c3e50; color: white; }
        tr:nth-child(even) { background-color: #f9f9f9; }

        /* Lo stile della card Gemini-like */
        .code-card { background-color: #1e1e1e; border-radius: 8px; overflow: hidden; margin: 20px 0; box-shadow: 0 10px 30px rgba(0,0,0,0.3); }
        .code-header { background-color: #333; padding: 8px 16px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #444; }
        .code-title { color: #aaa; font-size: 12px; font-family: monospace; }
        #copy-btn { background: transparent; border: none; cursor: pointer; color: #aaa; display: flex; align-items: center; transition: 0.2s; }
        #copy-btn:hover { color: #fff; }
        .htaccess-block { padding: 15px; overflow-x: auto; }
        .htaccess-block pre { margin: 0; color: #b5cea8; font-family: 'Fira Code', monospace; font-size: 13px; }

        footer { margin-top: 50px; text-align: center; font-size: 0.8em; color: #7f8c8d; }
    </style>
    """

    # JavaScript per la copia
    script_js = """
    <script>
    function copyHtaccess() {
        const text = document.getElementById('htaccess-code').innerText;
        navigator.clipboard.writeText(text).then(() => {
            const btn = document.getElementById('copy-btn');
            const originalColor = btn.style.color;
            btn.style.color = '#4ade80';
            setTimeout(() => btn.style.color = originalColor, 1500);
        });
    }
    </script>
    """

    html_content = f"<html><head><title>Audit {nome_sito}</title>{stile_css}{script_js}</head><body>"
    html_content += "<div class='container'>"
    html_content += f"<h1>Report Analisi Sicurezza: {nome_sito}</h1>"

    if not bastardi.empty:
        html_content += "<h2>I Bastardi (Tentativi Furto Dati)</h2>"
        html_content += bastardi.to_html()
    if not rompicojons.empty:
        html_content += "<h2>I Rompicojons (Brute Force Detection)</h2>"
        html_content += rompicojons.to_html()

    scudo = genera_scudo_htaccess(bastardi, rompicojons)
    if scudo:
        scudo_safe = scudo.replace('<', '&lt;').replace('>', '&gt;')
        icon_svg = '<svg xmlns="http://www.w3.org/2000/svg" height="18px" viewBox="0 -960 960 960" width="18px" fill="currentColor"><path d="M360-240q-33 0-56.5-23.5T280-320v-480q0-33 23.5-56.5T360-880h360q33 0 56.5 23.5T800-800v480q0-33-23.5 56.5T720-240H360Zm0-80h360v-480H360v480ZM200-80q-33 0-56.5-23.5T120-160v-560h80v560h440v80H200Zm160-320v-480 480Z"/></svg>'

        html_content += "<h2>[5] Configurazione .htaccess Suggerita</h2>"
        html_content += f"""
        <div class="code-card">
            <div class="code-header">
                <span class="code-title">da aggiungere al file .htaccess</span>
                <button id="copy-btn" onclick="copyHtaccess()" title="Copia codice">{icon_svg}</button>
            </div>
            <div class="htaccess-block"><pre id="htaccess-code">{scudo_safe}</pre></div>
        </div>
        """

    html_content += "<footer>Powered by Sunday Coding & Gemini AI</footer></div></body></html>"

    with open(nome_file, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"\n[OK] Report HTML generato: {nome_file}")

# --- ESECUZIONE ---
df = carica_e_pulisci_log(args.logfile)
if not df.empty:
    df = arricchisci_dati_rete(df, 'GeoLite2-Country.mmdb', 'GeoLite2-ASN.mmdb')
    i_bastardi = cerca_bastardi(df)
    i_rompicojons = rileva_rompicojons(df, limite_tentativi=10, secondi=60)

    if not i_bastardi.empty or not i_rompicojons.empty:
        salva_report_html(i_bastardi, i_rompicojons, f"report_{nome_sito}.html")
    else:
        print("Tutto tranquillo, niente da segnalare.")
