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
        st.header("📊 Admin Kontrola")
        tab_danas, tab_dnevnik, tab_radnici, tab_sati, tab_gradilista = st.tabs([
            "📅 Danas", "🕒 Dnevnik", "👥 Radnici", "⏱️ Sati", "🏗️ Gradilišta"
        ])
        
        df_l = ucitaj_podatke("log")

        with tab_danas:
            st.subheader("Trenutno stanje na gradilištima")
            if not df_l.empty:
                # Filtriranje za današnji datum
                danasnji_datum = datetime.now().strftime("%d.%m.%Y")
                df_danas = df_l[df_l['Vreme'].str.contains(danasnji_datum)].copy()
                
                # Logika za trenutno prisutne (poslednja akcija svakog radnika)
                trenutno_prisutni = df_l.sort_values('Vreme').groupby('Radnik').last().reset_index()
                prisutni_mask = trenutno_prisutni['Akcija'] == 'DOLAZAK'
                df_prisutni = trenutno_prisutni[prisutni_mask][['Radnik', 'Gradiliste', 'Vreme']]
                
                # Metrika (veliki broj na vrhu)
                st.metric("Ukupno radnika na terenu", len(df_prisutni))
                
                if not df_prisutni.empty:
                    st.write("Spisak ljudi koji su se prijavili, a nisu se još odjavili:")
                    st.dataframe(df_prisutni, use_container_width=True)
                else:
                    st.info("Trenutno nema prijavljenih radnika na terenu.")
                
                st.divider()
                st.write("Sve današnje aktivnosti (Dolasci i Odlasci):")
                st.dataframe(df_danas.iloc[::-1], use_container_width=True)
            else:
                st.info("Nema podataka u dnevniku.")

        with tab_dnevnik:
            st.dataframe(df_l.iloc[::-1] if not df_l.empty else df_l, use_container_width=True)
            
        with tab_gradilista:
            novo = st.text_input("Naziv novog gradilišta:")
            if st.button("Dodaj"): 
                if novo: dodaj_u_tabelu("gradilista", [novo]); st.rerun()
            st.dataframe(ucitaj_podatke("gradilista"), use_container_width=True)
            
        with tab_radnici:
            st.dataframe(ucitaj_podatke("korisnici"), use_container_width=True)
            
        with tab_sati:
            if not df_l.empty:
                res = obracunaj_sate(df_l)
                if not res.empty:
                    m = st.selectbox("Izaberi mesec:", res['Mesec'].unique())
                    finalni = res[res['Mesec'] == m].groupby('Radnik')['Sekunde'].sum().reset_index()
                    finalni['Ukupno Vreme'] = finalni['Sekunde'].apply(format_u_hms)
                    st.table(finalni[['Radnik', 'Ukupno Vreme']])
        st.stop()

# --- RADNIČKO OKRUŽENJE ---
st.title("👷 Digitalna Prijava")
email_cookie = cookies.get("radnik_email")
df_korisnici = ucitaj_podatke("korisnici")
prijavljeno_ime = None

if email_cookie and not df_korisnici.empty:
    match = df_korisnici[df_korisnici['Email'] == email_cookie]
    if not match.empty: prijavljeno_ime = match.iloc[0]['Ime']

if not prijavljeno_ime:
    st.subheader("Registracija / Prijava")
    email_in = st.text_input("Unesite vaš Email:").strip().lower()
    if email_in:
        postoji = False
        if not df_korisnici.empty and 'Email' in df_korisnici.columns:
            match = df_korisnici[df_korisnici['Email'] == email_in]
            if not match.empty:
                postoji = True
                if st.button(f"Prijavi me kao {match.iloc[0]['Ime']}"):
                    cookies["radnik_email"] = email_in; cookies.save(); st.rerun()
        if not postoji:
            ime_in = st.text_input("Ime i Prezime:")
            if st.button("Registruj me"):
                if ime_in and email_in:
                    dodaj_u_tabelu("korisnici", [ime_in, email_in])
                    cookies["radnik_email"] = email_in; cookies.save(); st.rerun()
else:
    status = dobij_poslednji_status(prijavljeno_ime)
    st.write(f"### Radnik: **{prijavljeno_ime}**")
    
    df_g = ucitaj_podatke("gradilista")
    if not df_g.empty:
        lista_g = ["-- KLIKNI OVDE I IZABERI GRADILIŠTE --"] + df_g['Naziv'].tolist()
        izbor = st.selectbox("🚩 GDE SE NALAZITE TRENUTNO?", lista_g)
        
        if izbor == "-- KLIKNI OVDE I IZABERI GRADILIŠTE --":
            st.info("Obavezno izaberite lokaciju iznad kako bi se pojavilo dugme za prijavu.")

        st.write("---")
        vreme_sad = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        col1, col2 = st.columns(2)
        
        with col1:
            if izbor == "-- KLIKNI OVDE I IZABERI GRADILIŠTE --":
                st.markdown('<div class="onemoguceno-dugme">', unsafe_allow_html=True)
                st.button("IZBOR GRADILIŠTA OBAVEZAN", key="no_site")
                st.markdown('</div>', unsafe_allow_html=True)
            elif status == "ODLAZAK":
                st.markdown('<div class="trepcuce-dugme">', unsafe_allow_html=True)
                if st.button("✅ PRIJAVI SE NA POSAO"):
                    dodaj_u_tabelu("log", [prijavljeno_ime, "DOLAZAK", izbor, vreme_sad])
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="onemoguceno-dugme">', unsafe_allow_html=True)
                st.button("VEĆ STE PRIJAVLJENI", key="dis_pri")
                st.markdown('</div>', unsafe_allow_html=True)

        with col2:
            if status == "DOLAZAK":
                st.markdown('<div class="odjava-dugme">', unsafe_allow_html=True)
                if st.button("🛑 ODJAVI SE SA POSLA"):
                    dodaj_u_tabelu("log", [prijavljeno_ime, "ODLAZAK", izbor, vreme_sad])
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="onemoguceno-dugme">', unsafe_allow_html=True)
                st.button("NISTE PRIJAVLJENI", key="dis_odj")
                st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.warning("Admin još nije dodao gradilišta.")

    st.write("---")
    if st.button("Logout sa uređaja"):
        del cookies["radnik_email"]; cookies.save(); st.rerun()
