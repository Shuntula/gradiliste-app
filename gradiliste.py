import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from streamlit_cookies_manager import EncryptedCookieManager

# --- KONFIGURACIJA STRANICE ---
st.set_page_config(page_title="Gradilište Log", page_icon="👷", layout="wide")

# --- STILIZACIJA ---
st.markdown("""
    <style>
    /* Brzo treptanje za dugme PRIJAVI SE */
    @keyframes blinking {
        0% { background-color: #28a745; box-shadow: 0 0 5px #28a745; }
        50% { background-color: #58d68d; box-shadow: 0 0 20px #58d68d; }
        100% { background-color: #28a745; box-shadow: 0 0 5px #28a745; }
    }
    
    /* Blago pulsiranje za status PRIJAVLJENI STE */
    @keyframes subtle-green {
        0% { background-color: #1e7e34; opacity: 1; }
        50% { background-color: #28a745; opacity: 0.8; }
        100% { background-color: #1e7e34; opacity: 1; }
    }

    .trepcuce-dugme > div > button {
        height: 100px !important; font-size: 24px !important; font-weight: bold !important;
        color: white !important; animation: blinking 1.5s infinite;
        border: none !important; border-radius: 15px !important; width: 100% !important;
    }

    .blago-trepcuce-zeleno > div > button {
        height: 100px !important; font-size: 22px !important; font-weight: bold !important;
        color: white !important; animation: subtle-green 3s infinite;
        border: none !important; border-radius: 15px !important; width: 100% !important;
        pointer-events: none !important;
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

    .label-radnik { font-size: 16px; color: #BBB; }
    .ime-radnika { font-size: 28px; font-weight: bold; color: #FFF; }
    </style>
    """, unsafe_allow_html=True)

# --- POVEZIVANJE ---
@st.cache_resource
def povezi_google():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

@st.cache_data(ttl=10)
def ucitaj_sve_podatke():
    client = povezi_google()
    sh = client.open("Baza Gradiliste")
    df_l = pd.DataFrame(sh.worksheet("log").get_all_records())
    df_k = pd.DataFrame(sh.worksheet("korisnici").get_all_records())
    df_g = pd.DataFrame(sh.worksheet("gradilista").get_all_records())
    return df_l, df_k, df_g

def dodaj_u_tabelu(sheet_name, red):
    client = povezi_google()
    sh = client.open("Baza Gradiliste")
    sh.worksheet(sheet_name).append_row(red)
    st.cache_data.clear()

# --- POMOĆNE FUNKCIJE ---
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

# Učitavanje podataka
try:
    df_l, df_k, df_g = ucitaj_sve_podatke()
except Exception as e:
    st.error(f"Greška pri učitavanju: {e}"); st.stop()

# --- ADMIN OKRUŽENJE ---
st.sidebar.title("🔐 Admin")
if st.sidebar.text_input("Lozinka:", type="password") == "admin":
    if st.sidebar.checkbox("Prikaži Admin Dashboard"):
        broj_r, broj_g_aktivno, df_prisutni_admin = 0, 0, pd.DataFrame()
        if not df_l.empty:
            trenutno = df_l.sort_values('Vreme').groupby('Radnik').last().reset_index()
            df_prisutni_admin = trenutno[trenutno['Akcija'] == 'DOLAZAK']
            broj_r = len(df_prisutni_admin)
            broj_g_aktivno = df_prisutni_admin['Gradiliste'].nunique()
        
        st.header(f"📊 Admin Kontrola | R{broj_r} G{broj_g_aktivno}")
        tabs = st.tabs(["📅 Danas", "🕒 Dnevnik", "👥 Radnici", "⏱️ Sati", "🏗️ Gradilišta"])
        
        with tabs[0]:
            st.metric("Aktivnih radnika", broj_r)
            if not df_prisutni_admin.empty:
                st.dataframe(df_prisutni_admin[['Radnik', 'Gradiliste', 'Vreme']], use_container_width=True)
            else: st.info("Nema prijavljenih.")
        with tabs[1]: st.dataframe(df_l.iloc[::-1], use_container_width=True)
        
        with tabs[4]: # GRADILIŠTA SA BROJAČEM PRIJAVA
            st.subheader("Baza gradilišta")
            novo = st.text_input("Dodaj novo gradilište:")
            if st.button("Dodaj"): 
                if novo: dodaj_u_tabelu("gradilista", [novo]); st.rerun()
            
            if not df_g.empty:
                # Logika za sabiranje jedinstvenih dnevnih prijava
                if not df_l.empty:
                    temp_l = df_l.copy()
                    temp_l['Datum'] = temp_l['Vreme'].str.slice(0, 10) # Izvlači samo DD.MM.YYYY
                    # Filtriramo samo dolaske i uklanjamo duplikate (isti radnik, isto gradilište, isti dan)
                    dolasci = temp_l[temp_l['Akcija'] == 'DOLAZAK'].drop_duplicates(subset=['Radnik', 'Gradiliste', 'Datum'])
                    statistika_g = dolasci.groupby('Gradiliste').size().reset_index(name='Ukupno Prijave')
                    
                    # Spajamo sa glavnom listom gradilišta
                    prikaz_g = pd.merge(df_g, statistika_g, left_on='Naziv', right_on='Gradiliste', how='left')
                    prikaz_g['Ukupno Prijave'] = prikaz_g['Ukupno Prijave'].fillna(0).astype(int)
                    st.dataframe(prikaz_g[['Naziv', 'Ukupno Prijave']], use_container_width=True)
                else:
                    df_g['Ukupno Prijave'] = 0
                    st.dataframe(df_g[['Naziv', 'Ukupno Prijave']], use_container_width=True)
            
        with tabs[2]: st.dataframe(df_k, use_container_width=True)
        with tabs[3]:
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
prijavljeno_ime = None

if email_cookie and not df_k.empty:
    match = df_k[df_k['Email'] == email_cookie]
    if not match.empty: prijavljeno_ime = match.iloc[0]['Ime']

if not prijavljeno_ime:
    st.subheader("Registracija / Prijava")
    email_in = st.text_input("Unesite vaš Email:").strip().lower()
    if email_in:
        match = df_k[df_k['Email'] == email_in] if not df_k.empty else pd.DataFrame()
        if not match.empty:
            if st.button(f"Prijavi me kao {match.iloc[0]['Ime']}"):
                cookies["radnik_email"] = email_in; cookies.save(); st.rerun()
        else:
            ime_in = st.text_input("Ime i Prezime:")
            if st.button("Registruj me"):
                if ime_in and email_in:
                    dodaj_u_tabelu("korisnici", [ime_in, email_in])
                    cookies["radnik_email"] = email_in; cookies.save(); st.rerun()
else:
    status = "ODLAZAK"
    poslednje_gradiliste = None
    if not df_l.empty:
        radnik_logs = df_l[df_l['Radnik'] == prijavljeno_ime]
        if not radnik_logs.empty:
            poslednji_red = radnik_logs.iloc[-1]
            status = poslednji_red['Akcija']
            poslednje_gradiliste = poslednji_red['Gradiliste']

    st.markdown(f"<span class='label-radnik'>radnik:</span> <span class='ime-radnika'>{prijavljeno_ime}</span>", unsafe_allow_html=True)
    
    if not df_g.empty:
        lista_g = ["-- klikni ovde i izaberi gradilište --"] + df_g['Naziv'].tolist()
        default_index = 0
        if poslednje_gradiliste in lista_g:
            default_index = lista_g.index(poslednje_gradiliste)
            
        izbor = st.selectbox("🚩 gde se nalazite trenutno?", lista_g, index=default_index)
        
        if izbor == "-- klikni ovde i izaberi gradilište --":
            st.info("izaberite lokaciju da se pojavi dugme.")

        st.write("---")
        vreme_sad = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        col1, col2 = st.columns(2)
        
        with col1:
            if izbor == "-- klikni ovde i izaberi gradilište --":
                st.markdown('<div class="onemoguceno-dugme"><button>IZBOR OBAVEZAN</button></div>', unsafe_allow_html=True)
            elif status == "ODLAZAK":
                st.markdown('<div class="trepcuce-dugme">', unsafe_allow_html=True)
                if st.button("✅ PRIJAVI SE NA POSAO"):
                    dodaj_u_tabelu("log", [prijavljeno_ime, "DOLAZAK", izbor, vreme_sad])
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="blago-trepcuce-zeleno">', unsafe_allow_html=True)
                st.button("✅ PRIJAVLJENI STE", key="dis_pri")
                st.markdown('</div>', unsafe_allow_html=True)

        with col2:
            if status == "DOLAZAK":
                st.markdown('<div class="odjava-dugme">', unsafe_allow_html=True)
                if st.button("🛑 ODJAVI SE SA POSLA"):
                    dodaj_u_tabelu("log", [prijavljeno_ime, "ODLAZAK", izbor, vreme_sad])
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="onemoguceno-dugme"><button>NISTE PRIJAVLJENI</button></div>', unsafe_allow_html=True)

    st.write("---")
    if st.button("Logout"):
        del cookies["radnik_email"]; cookies.save(); st.rerun()
