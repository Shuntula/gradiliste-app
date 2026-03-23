import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from streamlit_cookies_manager import EncryptedCookieManager

# --- POVEZIVANJE SA GOOGLE SHEETS ---
def povezi_tabelu():
    # Ovde definišemo dozvole za Google Drive i Sheets
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # IZMENA: Čitamo iz Secrets (koji smo podesili u Advanced Settings)
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    
    client = gspread.authorize(creds)
    # Proveri da li se tvoja tabela na Google-u zove baš ovako:
    return client.open("Baza Gradiliste")

# --- KONFIGURACIJA ---
ADMIN_PASSWORD = "admin"
cookies = EncryptedCookieManager(password="neka_veoma_tajna_sifra_123")
if not cookies.ready():
    st.stop()

# --- POMOĆNE FUNKCIJE ---
def format_u_hms(ukupno_sekundi):
    sati = int(ukupno_sekundi // 3600)
    minuti = int((ukupno_sekundi % 3600) // 60)
    sekunde = int(ukupno_sekundi % 60)
    return f"{sati:02d}:{minuti:02d}:{sekunde:02d}"

def ucitaj_podatke(sheet_name):
    sh = povezi_tabelu()
    worksheet = sh.worksheet(sheet_name)
    return pd.DataFrame(worksheet.get_all_records())

def dodaj_u_tabelu(sheet_name, red):
    sh = povezi_tabelu()
    worksheet = sh.worksheet(sheet_name)
    worksheet.append_row(red)

# --- OBRAČUN SATI ---
def obracunaj_sate(df):
    if df.empty: return pd.DataFrame()
    df['Vreme'] = pd.to_datetime(df['Vreme'], format="%d.%m.%Y %H:%M:%S")
    df = df.sort_values(['Radnik', 'Vreme'])
    obracun = []
    for radnik in df['Radnik'].unique():
        radnik_data = df[df['Radnik'] == radnik]
        dolazak_vreme = None
        for _, row in radnik_data.iterrows():
            if row['Akcija'] == "DOLAZAK":
                dolazak_vreme = row['Vreme']
            elif row['Akcija'] == "ODLAZAK" and dolazak_vreme is not None:
                razlika = (row['Vreme'] - dolazak_vreme).total_seconds()
                mesec = dolazak_vreme.strftime("%m-%Y")
                obracun.append([radnik, mesec, razlika])
                dolazak_vreme = None
    return pd.DataFrame(obracun, columns=["Radnik", "Mesec", "Sekunde"])

# --- UI DIZAJN ---
st.set_page_config(page_title="Gradilište", page_icon="👷", layout="wide")

# --- ADMIN PANEL ---
st.sidebar.title("🔐 Admin Panel")
admin_pass = st.sidebar.text_input("Lozinka:", type="password")

if admin_pass == ADMIN_PASSWORD:
    st.sidebar.success("✅ Admin pristup")
    if st.sidebar.checkbox("Prikaži Admin Dashboard"):
        st.header("📊 Kontrolna tabla")
        t1, t2, t3, t4 = st.tabs(["🕒 Dnevnik", "👥 Radnici", "⏱️ Sati", "🏗️ Gradilišta"])
        
        with t4: # Gradilišta
            novo = st.text_input("Novo gradilište:")
            if st.button("Dodaj"):
                dodaj_u_tabelu("gradilista", [novo])
                st.rerun()
            lista_g = ucitaj_podatke("gradilista")
            st.dataframe(lista_g)

        with t1: # Dnevnik
            df_log = ucitaj_podatke("log")
            st.dataframe(df_log.iloc[::-1], use_container_width=True)

        with t3: # Obračun
            res = obracunaj_sate(df_log)
            if not res.empty:
                mesec = st.selectbox("Mesec:", res['Mesec'].unique())
                m_df = res[res['Mesec'] == mesec].groupby('Radnik')['Sekunde'].sum().reset_index()
                m_df['Vreme'] = m_df['Sekunde'].apply(format_u_hms)
                st.table(m_df[['Radnik', 'Vreme']])

# --- RADNICI ---
st.title("👷 Digitalna Prijava")
email_cookie = cookies.get("radnik_email")

# Provera korisnika u Google tabeli
df_korisnici = ucitaj_podatke("korisnici")
prijavljeno_ime = None
if email_cookie:
    match = df_korisnici[df_korisnici['Email'] == email_cookie]
    if not match.empty:
        prijavljeno_ime = match.iloc[0]['Ime']

if not prijavljeno_ime:
    email_in = st.text_input("Email:").strip().lower()
    if email_in:
        match = df_korisnici[df_korisnici['Email'] == email_in]
        if not match.empty:
            if st.button(f"Prijavi me kao {match.iloc[0]['Ime']}"):
                cookies["radnik_email"] = email_in
                cookies.save()
                st.rerun()
        else:
            ime_in = st.text_input("Ime i Prezime:")
            if st.button("Registruj me"):
                dodaj_u_tabelu("korisnici", [ime_in, email_in])
                cookies["radnik_email"] = email_in
                cookies.save()
                st.rerun()
else:
    st.success(f"📍 Radnik: {prijavljeno_ime}")
    gradilista = ucitaj_podatke("gradilista")['Naziv'].tolist()
    if gradilista:
        izbor = st.selectbox("Izaberi gradilište:", gradilista)
        c1, c2 = st.columns(2)
        vreme_sad = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        if c1.button("✅ PRIJAVA"):
            dodaj_u_tabelu("log", [prijavljeno_ime, "DOLAZAK", izbor, vreme_sad])
            st.toast("Prijavljeni!")
        if c2.button("🛑 ODJAVA"):
            dodaj_u_tabelu("log", [prijavljeno_ime, "ODLAZAK", izbor, vreme_sad])
            st.toast("Odjavljeni!")
    
    if st.button("Logout"):
        del cookies["radnik_email"]
        cookies.save()
        st.rerun()
