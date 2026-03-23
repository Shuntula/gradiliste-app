import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import os

# --- KONFIGURACIJA STRANICE ---
st.set_page_config(page_title="Gradilište Log", page_icon="👷", layout="wide")

# --- POVEZIVANJE SA GOOGLE SHEETS (Preko Secrets-a) ---
def povezi_tabelu():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    # Čitamo tajne podatke koje si uneo u Streamlit Advanced Settings
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        # Proveri da li se tvoja tabela na Google Drive-u zove baš ovako:
        return client.open("Baza Gradiliste")
    except Exception as e:
        st.error(f"Greška pri povezivanju sa Google tabelom: {e}")
        return None

# --- POMOĆNE FUNKCIJE ZA PODATKE ---
def ucitaj_podatke(sheet_name):
    sh = povezi_tabelu()
    if sh:
        worksheet = sh.worksheet(sheet_name)
        data = worksheet.get_all_records()
        return pd.DataFrame(data)
    return pd.DataFrame()

def dodaj_u_tabelu(sheet_name, red):
    sh = povezi_tabelu()
    if sh:
        worksheet = sh.worksheet(sheet_name)
        worksheet.append_row(red)

def format_u_hms(ukupno_sekundi):
    sati = int(ukupno_sekundi // 3600)
    minuti = int((ukupno_sekundi % 3600) // 60)
    sekunde = int(ukupno_sekundi % 60)
    return f"{sati:02d}:{minuti:02d}:{sekunde:02d}"

def obracunaj_sate(df):
    if df.empty or 'Vreme' not in df.columns:
        return pd.DataFrame()
    
    df['Vreme'] = pd.to_datetime(df['Vreme'], format="%d.%m.%Y %H:%M:%S")
    df = df.sort_values(['Radnik', 'Vreme'])
    
    obracun = []
    for radnik in df['Radnik'].unique():
        radnik_data = df[df['Radnik'] == radnik].copy()
        dolazak_vreme = None
        
        for index, row in radnik_data.iterrows():
            if row['Akcija'] == "DOLAZAK":
                dolazak_vreme = row['Vreme']
            elif row['Akcija'] == "ODLAZAK" and dolazak_vreme is not None:
                razlika = (row['Vreme'] - dolazak_vreme).total_seconds()
                mesec = dolazak_vreme.strftime("%m-%Y")
                obracun.append([radnik, mesec, razlika])
                dolazak_vreme = None
                
    return pd.DataFrame(obracun, columns=["Radnik", "Mesec", "Sekunde"])

# --- SISTEM KOLAČIĆA (DA OSTANE PRIJAVLJEN) ---
from streamlit_cookies_manager import EncryptedCookieManager
cookies = EncryptedCookieManager(password="neka_veoma_tajna_sifra_123")
if not cookies.ready():
    st.stop()

# --- ADMIN PANEL ---
st.sidebar.title("🔐 Admin Panel")
ADMIN_PASSWORD = "admin"
admin_pass = st.sidebar.text_input("Lozinka:", type="password")

if admin_pass == ADMIN_PASSWORD:
    st.sidebar.success("✅ Admin pristup")
    if st.sidebar.checkbox("Prikaži Admin Dashboard"):
        st.header("📊 Kontrolna tabla")
        tab1, tab2, tab3, tab4 = st.tabs(["🕒 Dnevnik", "👥 Radnici", "⏱️ Sati", "🏗️ Gradilišta"])
        
        with tab4:
            st.subheader("Upravljanje gradilištima")
            novo_grad = st.text_input("Naziv novog gradilišta:")
            if st.button("Dodaj"):
                if novo_grad:
                    dodaj_u_tabelu("gradilista", [novo_grad])
                    st.success("Dodato!")
                    st.rerun()
            
            df_g = ucitaj_podatke("gradilista")
            if not df_g.empty:
                st.dataframe(df_g, use_container_width=True)

        with tab1:
            df_log = ucitaj_podatke("log")
            if not df_log.empty:
                st.dataframe(df_log.iloc[::-1], use_container_width=True)
            else:
                st.info("Dnevnik je prazan.")

        with tab2:
            df_kor = ucitaj_podatke("korisnici")
            if not df_kor.empty:
                st.dataframe(df_kor, use_container_width=True)
            else:
                st.info("Nema registrovanih radnika.")

        with tab3:
            df_log_za_sate = ucitaj_podatke("log")
            res = obracunaj_sate(df_log_za_sate)
            if not res.empty:
                izabrani_mesec = st.selectbox("Mesec:", res['Mesec'].unique())
                m_df = res[res['Mesec'] == izabrani_mesec].groupby('Radnik')['Sekunde'].sum().reset_index()
                m_df['Ukupno Vreme'] = m_df['Sekunde'].apply(format_u_hms)
                st.table(m_df[['Radnik', 'Ukupno Vreme']])
            else:
                st.info("Nema podataka za obračun sati.")

# --- GLAVNI DEO ZA RADNIKE ---
st.title("👷 Digitalna Prijava")
email_cookie = cookies.get("radnik_email")

# Učitavanje baze korisnika
df_korisnici = ucitaj_podatke("korisnici")
prijavljeno_ime = None

# Provera da li je radnik već prijavljen (preko kolačića)
if email_cookie and not df_korisnici.empty and 'Email' in df_korisnici.columns:
    match = df_korisnici[df_korisnici['Email'] == email_cookie]
    if not match.empty:
        prijavljeno_ime = match.iloc[0]['Ime']

if not prijavljeno_ime:
    st.subheader("Dobrodošli! Molimo vas da se prijavite.")
    email_in = st.text_input("Unesite vaš Email:").strip().lower()
    
    if email_in:
        postoji_u_bazi = False
        if not df_korisnici.empty and 'Email' in df_korisnici.columns:
            match = df_korisnici[df_korisnici['Email'] == email_in]
            if not match.empty:
                postoji_u_bazi = True
                if st.button(f"Prijavi me kao {match.iloc[0]['Ime']}"):
                    cookies["radnik_email"] = email_in
                    cookies.save()
                    st.rerun()
        
        if not postoji_u_bazi:
            st.info("Vaš email nije pronađen u sistemu.")
            ime_in = st.text_input("Unesite vaše Ime i Prezime za registraciju:")
            if st.button("Registruj me"):
                if ime_in and email_in:
                    dodaj_u_tabelu("korisnici", [ime_in, email_in])
                    cookies["radnik_email"] = email_in
                    cookies.save()
                    st.success("Uspešna registracija! Osvežite stranicu ili kliknite 'Prijavi me'.")
                    st.rerun()
                else:
                    st.error("Unesite ime i email!")
else:
    # --- EKRAN ZA PRIJAVU NA GRADILIŠTE ---
    st.success(f"📍 Radnik: **{prijavljeno_ime}**")
    
    df_gradilista = ucitaj_podatke("gradilista")
    if not df_gradilista.empty:
        lista_g = df_gradilista['Naziv'].tolist()
        izbor = st.selectbox("Izaberi gradilište:", lista_g)
        
        col1, col2 = st.columns(2)
        vreme_sad = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        
        if col1.button("✅ PRIJAVI SE NA POSAO", use_container_width=True):
            dodaj_u_tabelu("log", [prijavljeno_ime, "DOLAZAK", izbor, vreme_sad])
            st.balloons()
            st.success("Prijava uspešna!")
            
        if col2.button("🛑 ODJAVI SE SA POSLA", use_container_width=True):
            dodaj_u_tabelu("log", [prijavljeno_ime, "ODLAZAK", izbor, vreme_sad])
            st.warning("Odjava uspešna!")
    else:
        st.warning("Admin još nije dodao nijedno gradilište.")

    st.write("---")
    if st.button("Odjavi me sa ovog uređaja (Logout)"):
        del cookies["radnik_email"]
        cookies.save()
        st.rerun()
