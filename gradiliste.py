import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import os
from streamlit_cookies_manager import EncryptedCookieManager

# --- KONFIGURACIJA STRANICE ---
st.set_page_config(page_title="Gradilište Log", page_icon="🏗️", layout="wide")

# --- REČNIK ZA MESECE ---
MESECI_SR = {
    1: "januar", 2: "februar", 3: "mart", 4: "april", 5: "maj", 6: "jun",
    7: "jul", 8: "avgust", 9: "septembar", 10: "oktobar", 11: "novembar", 12: "decembar"
}

# --- KOLAČIĆI ---
cookies = EncryptedCookieManager(password="neka_veoma_tajna_sifra_123")
if not cookies.ready():
    st.stop()

# --- STILIZACIJA (CSS) ---
st.markdown("""
    <style>
    @keyframes pulse-green { 0% { box-shadow: 0 0 0 0 rgba(40, 167, 69, 0.7); transform: scale(0.98); } 70% { box-shadow: 0 0 0 20px rgba(40, 167, 69, 0); transform: scale(1); } 100% { box-shadow: 0 0 0 0 rgba(40, 167, 69, 0); transform: scale(0.98); } }
    @keyframes pulse-red { 0% { box-shadow: 0 0 0 0 rgba(220, 53, 69, 0.7); transform: scale(0.98); } 70% { box-shadow: 0 0 0 20px rgba(220, 53, 69, 0); transform: scale(1); } 100% { box-shadow: 0 0 0 0 rgba(220, 53, 69, 0); transform: scale(0.98); } }
    @keyframes ticker { 0% { transform: translateX(100%); } 100% { transform: translateX(-100%); } }
    
    .ticker-wrap { width: 100%; overflow: hidden; background-color: #111; padding: 10px 0; margin-bottom: 30px; border-radius: 5px; border: 1px solid #333; }
    .ticker-text { display: inline-block; white-space: nowrap; font-size: 18px; font-weight: bold; color: #28a745; animation: ticker 30s linear infinite; }
    
    .trepcuce-dugme > div > button { height: 100px !important; font-size: 24px !important; font-weight: bold !important; color: white !important; background-color: #28a745 !important; animation: pulse-green 2s infinite; border-radius: 15px !important; width: 100% !important; }
    .odjava-dugme > div > button { height: 100px !important; font-size: 24px !important; font-weight: bold !important; color: white !important; background-color: #dc3545 !important; animation: pulse-red 2s infinite; border-radius: 15px !important; width: 100% !important; }
    .trosak-dugme-plavo > div > button { height: 70px !important; font-size: 20px !important; color: white !important; background-color: #007bff !important; border-radius: 15px !important; width: 100% !important; margin-top: 10px !important; }
    .onemoguceno-dugme > div > button { height: 100px !important; background-color: #262730 !important; color: #555 !important; border: 1px solid #444 !important; border-radius: 15px !important; width: 100% !important; pointer-events: none !important; }
    
    .label-radnik { font-size: 16px; color: #BBB; }
    .ime-radnika { font-size: 28px; font-weight: bold; color: #FFF; }
    
    /* NASLOV 28px */
    .glavni-naslov { font-size: 28px; font-weight: bold; margin-left: 10px; display: inline-block; vertical-align: middle; }
    
    .admin-naslov { font-size: 28px; font-weight: bold; text-align: center; width: 100%; margin-bottom: 10px; padding: 10px; }
    .trosak-box { font-size: 22px; font-weight: bold; color: #FF4B4B; padding: 5px 15px; border: 2px solid #FF4B4B; border-radius: 10px; display: inline-block; }
    .trosak-mesec-box { font-size: 22px; font-weight: bold; color: #FFA500; padding: 5px 15px; border: 2px solid #FFA500; border-radius: 10px; display: inline-block; }
    .centriran-tekst { text-align: center; width: 100%; margin: 20px 0; }
    .diskretno-dugme { display: flex; justify-content: center; width: 100%; margin-top: 60px !important; }
    .diskretno-dugme > div > button { font-size: 13px !important; color: #888 !important; background-color: transparent !important; border: 1px solid #444 !important; padding: 5px 15px !important; opacity: 0.7; }
    </style>
    """, unsafe_allow_html=True)

# --- POVEZIVANJE SA GOOGLE ---
def povezi_google():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        return gspread.authorize(creds)
    except: return None

@st.cache_data(ttl=5)
def ucitaj_podatke():
    client = povezi_google()
    if not client: return None, None, None, None
    sh = client.open("Baza Gradiliste")
    def get_df(name):
        try:
            data = sh.worksheet(name).get_all_records()
            return pd.DataFrame(data) if data else pd.DataFrame()
        except: return pd.DataFrame()
    return get_df("log"), get_df("korisnici"), get_df("gradilista"), get_df("troskovi")

def dodaj_u_tabelu(sheet_name, red):
    client = povezi_google()
    if client: client.open("Baza Gradiliste").worksheet(sheet_name).append_row(red)

# --- ANALITIKA ---
def obracunaj_sate_i_dane(df):
    if df.empty or 'Vreme' not in df.columns: return pd.DataFrame(), pd.DataFrame()
    df['V_DT'] = pd.to_datetime(df['Vreme'], format="%d.%m.%Y %H:%M:%S", errors='coerce')
    df = df.dropna(subset=['V_DT']).sort_values(['Radnik', 'V_DT'])
    
    # Naziv meseca za grupisanje
    df['Mesec'] = df['V_DT'].dt.month.map(MESECI_SR) + " " + df['V_DT'].dt.year.astype(str)
    
    sati = []
    for r in df['Radnik'].unique():
        rd = df[df['Radnik'] == r]
        dv = None
        for _, row in rd.iterrows():
            if row['Akcija'] == "DOLAZAK": dv = row['V_DT']
            elif row['Akcija'] == "ODLAZAK" and dv:
                diff = (row['V_DT'] - dv).total_seconds()
                if diff > 0: sati.append([r, row['Mesec'], diff])
                dv = None
    
    df_sati = pd.DataFrame(sati, columns=["Radnik", "Mesec", "Sekunde"])
    # Bitno: Koristimo ime kolone 'Mesec'
    df_dani = df.groupby(['Radnik', 'Mesec'])['Vreme'].apply(lambda x: x.str.slice(0,10).nunique()).reset_index(name='Radni Dani')
    return df_sati, df_dani

# --- PROGRAM ---
df_l, df_k, df_g, df_t = ucitaj_podatke()

if df_k is not None:
    st.sidebar.title("🔐 Admin")
    lozinka = st.sidebar.text_input("Lozinka:", type="password")
    if lozinka == "admin" and st.sidebar.checkbox("Prikaži Dashboard"):
        # --- ADMIN OKRUŽENJE ---
        br_r, br_g = 0, 0
        tr_p = pd.DataFrame()
        if not df_l.empty:
            tr = df_l.sort_values('Vreme').groupby('Radnik').last().reset_index()
            tr_p = tr[tr['Akcija'] == 'DOLAZAK']
            br_r, br_g = len(tr_p), tr_p['Gradiliste'].nunique()
        
        danas_dt = datetime.now().strftime("%d.%m.%Y")
        r_danas_imena = df_l[(df_l['Akcija'] == 'DOLAZAK') & (df_l['Vreme'].str.contains(danas_dt))]['Radnik'].unique() if not df_l.empty else []
        trosak_d = df_k[df_k['Ime'].isin(r_danas_imena)]['Cena'].astype(float).sum() if not df_k.empty and 'Cena' in df_k.columns else 0
        trosak_r = df_t[df_t['Vreme'].str.contains(danas_dt)]['Iznos'].astype(float).sum() if not df_t.empty else 0
        u_t_danas = trosak_d + trosak_r

        st.markdown(f"<div class='admin-naslov'>📊 Admin Kontrola | R{br_r} G{br_g}</div>", unsafe_allow_html=True)
        vest = f"trenutno na gradilištu: {br_r} radnika &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; • &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; današnji trošak: {u_t_danas:,.0f} RSD"
        st.markdown(f'<div class="ticker-wrap"><div class="ticker-text">{vest} &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; • &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; {vest}</div></div>', unsafe_allow_html=True)

        tabs = st.tabs(["📅 Danas", "👥 Radnici", "🕒 Dnevnik", "💰 Dnevnice", "🏗️ Gradilišta", "💸 Troškovi"])
        # (Admin tabovi ostaju isti...)
        st.stop()

    # --- RADNIČKO OKRUŽENJE ---
    # LOGO I NASLOV
    col_logo, col_txt = st.columns([1, 8])
    with col_logo:
        if os.path.exists("logo.png"):
            st.image("logo.png", width=60)
    with col_txt:
        st.markdown("<div class='glavni-naslov'>Digitalna prijava</div>", unsafe_allow_html=True)
    
    p_ime = None
    e_cookie = cookies.get("radnik_email")
    if e_cookie and not df_k.empty:
        match = df_k[df_k['Email'] == e_cookie]
        if not match.empty: p_ime = match.iloc[0]['Ime']

    if not p_ime:
        e_in = st.text_input("Email:").strip().lower()
        if e_in:
            match = df_k[df_k['Email'] == e_in] if not df_k.empty else pd.DataFrame()
            if not match.empty:
                if st.button(f"Prijavi me kao {match.iloc[0]['Ime']}"): cookies["radnik_email"] = e_in; cookies.save(); st.rerun()
            else:
                i_in = st.text_input("Ime i Prezime:")
                if st.button("Registruj me"):
                    if i_in and e_in:
                        dodaj_u_tabelu("korisnici", [i_in, e_in, 0])
                        cookies["radnik_email"] = e_in; cookies.save(); st.rerun()
    else:
        if st.session_state.get('unos_troska', False):
            # (Unos troška ostaje isti...)
            st.subheader("💰 Unos troška")
            if st.button("⬅️ Nazad"): st.session_state.unos_troska = False; st.rerun()
            kat = st.selectbox("Kategorija:", ["GORIVO", "HRANA", "MATERIJAL", "DRUGO"])
            izn = st.number_input("Iznos RSD:", min_value=0, step=50)
            grad_t = st.selectbox("Gradilište:", df_g['Naziv'].tolist() if not df_g.empty else ["Nema"])
            if st.button("✅ SAČUVAJ"):
                if izn > 0:
                    dodaj_u_tabelu("troskovi", [p_ime, grad_t, kat, izn, datetime.now().strftime("%d.%m.%Y %H:%M:%S")])
                    st.session_state.unos_troska = False; st.rerun()
        else:
            status, posl_g = "ODLAZAK", None
            if not df_l.empty:
                r_l = df_l[df_l['Radnik'] == p_ime]
                if not r_l.empty: status, posl_g = r_l.iloc[-1]['Akcija'], r_l.iloc[-1]['Gradiliste']
            
            st.markdown(f"<span class='label-radnik'>radnik:</span> <span class='ime-radnika'>{p_ime}</span>", unsafe_allow_html=True)
            l_g = ["-- klikni ovde i izaberi gradilište --"] + df_g['Naziv'].tolist() if not df_g.empty else ["Nema"]
            def_idx = l_g.index(posl_g) if posl_g in l_g else 0
            izbor = st.selectbox("🚩 gde se nalazite trenutno?", l_g, index=def_idx)
            
            st.write("---")
            v_sad = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
            
            if status == "ODLAZAK":
                if izbor == "-- klikni ovde i izaberi gradilište --": st.markdown('<div class="onemoguceno-dugme"><button>IZBOR OBAVEZAN</button></div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="trepcuce-dugme">', unsafe_allow_html=True)
                    if st.button("✅ PRIJAVI SE NA POSAO"): dodaj_u_tabelu("log", [p_ime, "DOLAZAK", izbor, v_sad]); st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="odjava-dugme">', unsafe_allow_html=True)
                if st.button("🛑 ODJAVI SE SA POSLA"): dodaj_u_tabelu("log", [p_ime, "ODLAZAK", izbor, v_sad]); st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('<div class="trosak-dugme-plavo">', unsafe_allow_html=True)
            if st.button("💰 DODAJ TROŠAK"): st.session_state.unos_troska = True; st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

            # --- FIKSIRAN PREGLED DNEVNICA ZA RADNIKA ---
            st.write("---")
            with st.expander("📊 Moja evidencija rada"):
                if not df_l.empty:
                    _, df_dani_radnik = obracunaj_sate_i_dane(df_l)
                    m_radnika = df_dani_radnik[df_dani_radnik['Radnik'] == p_ime]
                    if not m_radnika.empty:
                        tekuci_m_ime = MESECI_SR[datetime.now().month] + " " + str(datetime.now().year)
                        # Provera u koloni 'Mesec' (ne Mesec_Ime više)
                        d_sad = m_radnika[m_radnika['Mesec'] == tekuci_m_ime]
                        b_d_sad = d_sad['Radni Dani'].values[0] if not d_sad.empty else 0
                        st.info(f"📅 U mesecu **{tekuci_m_ime}** imate: **{b_d_sad} radnih dana**")
                        st.write("Pregled po mesecima:")
                        s_m = m_radnika['Mesec'].unique()
                        iz_m = st.selectbox("Izaberite mesec:", s_m, index=len(s_m)-1)
                        d_iz = m_radnika[m_radnika['Mesec'] == iz_m]['Radni Dani'].values[0]
                        st.write(f"U mesecu **{iz_m}** imali ste: **{d_iz} dana**.")
                    else:
                        st.write("Nema podataka o radnim danima.")

        st.write("---")
        if st.button("Logout"): del cookies["radnik_email"]; cookies.save(); st.rerun()
