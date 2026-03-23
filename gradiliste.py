import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from streamlit_cookies_manager import EncryptedCookieManager

# --- KONFIGURACIJA STRANICE ---
st.set_page_config(page_title="Gradilište Log", page_icon="👷", layout="wide")

# --- STILIZACIJA (Dizajn i Treptanje) ---
st.markdown("""
    <style>
    @keyframes blinking {
        0% { background-color: #28a745; box-shadow: 0 0 5px #28a745; }
        50% { background-color: #58d68d; box-shadow: 0 0 20px #58d68d; }
        100% { background-color: #28a745; box-shadow: 0 0 5px #28a745; }
    }
    .trepcuce-dugme > div > button {
        height: 100px !important; font-size: 24px !important; font-weight: bold !important;
        color: white !important; animation: blinking 1.5s infinite;
        border: none !important; border-radius: 15px !important; width: 100% !important;
    }
    .onemoguceno-dugme > div > button {
        height: 100px !important; background-color: #e0e0e0 !important;
        color: #9e9e9e !important; border: 1px solid #bdbdbd !important;
        width: 100% !important; pointer-events: none !important;
    }
    .odjava-dugme > div > button {
        height: 100px !important; font-size: 24px !important; font-weight: bold !important;
        background-color: #dc3545 !important; color: white !important;
        border-radius: 15px !important; width: 100% !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- POVEZIVANJE ---
def povezi_tabelu():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client.open("Baza Gradiliste")
    except Exception as e:
        st.error(f"Greška: {e}"); return None

def ucitaj_podatke(sheet_name):
    sh = povezi_tabelu()
    if sh:
        try: return pd.DataFrame(sh.worksheet(sheet_name).get_all_records())
        except: return pd.DataFrame()
    return pd.DataFrame()

def dodaj_u_tabelu(sheet_name, red):
    sh = povezi_tabelu()
    if sh: sh.worksheet(sheet_name).append_row(red)

def dobij_poslednji_status(ime):
    df_log = ucitaj_podatke("log")
    if df_log.empty: return "ODLAZAK"
    radnik_log = df_log[df_log['Radnik'] == ime]
    if radnik_log.empty: return "ODLAZAK"
    return radnik_log.iloc[-1]['Akcija']

def format_u_hms(ukupno_sekundi):
    sati, ostalo = divmod(int(ukupno_sekundi), 3600)
    minuti, sekunde = divmod(ostalo, 60)
    return f"{sati:02d}:{minuti:02d}:{sekunde:02d}"

def obracunaj_sate(df):
    if df.empty or 'Vreme' not in df.columns: return pd.DataFrame()
    df['Vreme_DT'] = pd.to_datetime(df['Vreme'], format="%d.%m.%Y %H:%M:%S", errors='coerce')
    df = df.dropna(subset=['Vreme_DT']).sort_values(['Radnik', 'Vreme_DT'])
    obracun = []
    for radnik in df['Radnik'].unique():
        radnik_data = df[df['Radnik'] == radnik]
        dolazak_vreme = None
        for _, row in radnik_data.iterrows():
            if row['Akcija'] == "DOLAZAK": dolazak_vreme = row['Vreme_DT']
            elif row['Akcija'] == "ODLAZAK" and dolazak_vreme is not None:
                razlika = (row['Vreme_DT'] - dolazak_vreme).total_seconds()
                if razlika > 0: obracun.append([radnik, dolazak_vreme.strftime("%m-%Y"), razlika])
                dolazak_vreme = None
    return pd.DataFrame(obracun, columns=["Radnik", "Mesec", "Sekunde"])

# --- KOLAČIĆI ---
cookies = EncryptedCookieManager(password="neka_veoma_tajna_sifra_123")
if not cookies.ready(): st.stop()

# --- ADMIN OKRUŽENJE ---
st.sidebar.title("🔐 Admin")
if st.sidebar.text_input("Lozinka:", type="password") == "admin":
    if st.sidebar.checkbox("Prikaži Admin Dashboard"):
        df_l = ucitaj_podatke("log")
        
        # Kalkulacija R i G na osnovu AKTIVNIH prijava
        broj_r = 0
        broj_g_aktivno = 0
        df_prisutni_admin = pd.DataFrame()
        
        if not df_l.empty:
            # Pronađi poslednju akciju svakog radnika
            trenutno = df_l.sort_values('Vreme').groupby('Radnik').last().reset_index()
            # Filtriraj samo one koji su prijavljeni (DOLAZAK)
            df_prisutni_admin = trenutno[trenutno['Akcija'] == 'DOLAZAK']
            
            broj_r = len(df_prisutni_admin)
            # Prebroj jedinstvena gradilišta među prijavljenim radnicima
            broj_g_aktivno = df_prisutni_admin['Gradiliste'].nunique()
        
        # DINAMIČKI NASLOV (R - radnici, G - aktivna gradilišta)
        st.header(f"📊 Admin Kontrola | R{broj_r} G{broj_g_aktivno}")
        
        tab_danas, tab_dnevnik, tab_radnici, tab_sati, tab_gradilista = st.tabs([
            "📅 Danas", "🕒 Dnevnik",
