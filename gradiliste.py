import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import os
import altair as alt
from streamlit_cookies_manager import EncryptedCookieManager

# --- 1. KONFIGURACIJA STRANICE ---
st.set_page_config(page_title="Gradilište Log", page_icon="logo.png", layout="wide")

# --- 2. KOLAČIĆI ---
cookies = EncryptedCookieManager(password="neka_veoma_tajna_sifra_123")
if not cookies.ready():
    st.stop()

# --- 3. REČNIK ZA MESECE ---
MESECI_SR = {
    1: "januar", 2: "februar", 3: "mart", 4: "april", 5: "maj", 6: "jun",
    7: "jul", 8: "avgust", 9: "septembar", 10: "oktobar", 11: "novembar", 12: "decembar"
}
DANI_SR = {'Monday': 'Pon', 'Tuesday': 'Uto', 'Wednesday': 'Sre', 'Thursday': 'Čet', 'Friday': 'Pet', 'Saturday': 'Sub', 'Sunday': 'Ned'}

# --- 4. INICIJALIZACIJA STANJA ---
if 'uredjivanje_cene' not in st.session_state: st.session_state.uredjivanje_cene = False
if 'unos_troska' not in st.session_state: st.session_state.unos_troska = False

# --- 5. STILIZACIJA (CSS) ---
st.markdown(f"""
    <style>
    @keyframes pulse-green {{ 0% {{ box-shadow: 0 0 0 0 rgba(40, 167, 69, 0.7); transform: scale(0.98); }} 70% {{ box-shadow: 0 0 0 20px rgba(40, 167, 69, 0); transform: scale(1); }} 100% {{ box-shadow: 0 0 0 0 rgba(40, 167, 69, 0); transform: scale(0.98); }} }}
    @keyframes pulse-red {{ 0% {{ box-shadow: 0 0 0 0 rgba(220, 53, 69, 0.7); transform: scale(0.98); }} 70% {{ box-shadow: 0 0 0 20px rgba(220, 53, 69, 0); transform: scale(1); }} 100% {{ box-shadow: 0 0 0 0 rgba(220, 53, 69, 0); transform: scale(0.98); }} }}
    @keyframes ticker {{ 0% {{ transform: translateX(100%); }} 100% {{ transform: translateX(-100%); }} }}
    
    .vega-actions {{ display: none !important; }}
    
    .ticker-wrap {{ width: 100%; overflow: hidden; background-color: #000; padding: 6px 0; margin-bottom: 25px; border-radius: 6px; border: 1.5px solid #0087bf; }}
    .ticker-text {{ display: inline-block; white-space: nowrap; font-size: 16px; font-weight: bold; color: #28a745; animation: ticker 30s linear infinite; }}
    .trepcuce-dugme > div > button {{ height: 100px !important; font-size: 24px !important; font-weight: bold !important; color: white !important; background-color: #28a745 !important; animation: pulse-green 2s infinite; border-radius: 15px !important; width: 100% !important; }}
    .odjava-dugme > div > button {{ height: 100px !important; font-size: 24px !important; font-weight: bold !important; color: white !important; background-color: #dc3545 !important; animation: pulse-red 2s infinite; border-radius: 15px !important; width: 100% !important; }}
    .trosak-dugme-plavo > div > button {{ height: 70px !important; font-size: 20px !important; color: white !important; background-color: #0087bf !important; border-radius: 15px !important; width: 100% !important; margin-top: 10px !important; border:none !important; }}
    .onemoguceno-dugme > div > button {{ height: 100px !important; background-color: #262730 !important; color: #555 !important; border: 1px solid #444 !important; border-radius: 15px !important; width: 100% !important; pointer-events: none !important; }}
    
    .label-radnik {{ font-size: 16px; color: #BBB; }}
    .ime-radnika {{ font-size: 28px; font-weight: bold; color: #FFF; }}
    .glavni-naslov {{ font-size: 28px; font-weight: bold; margin-top: 10px; color: #0087bf; display: inline-block; }}
    
    .admin-naslov {{ font-size: 28px; font-weight: bold; text-align: center; width: 100%; margin-bottom: 10px; padding: 10px; color: #FFF; background-color: #15468b; border-radius: 8px; }}
    .trosak-box {{ font-size: 22px; font-weight: bold; color: #FFF; background-color: #dc3545; padding: 5px 15px; border-radius: 10px; display: inline-block; }}
    .trosak-mesec-box {{ font-size: 22px; font-weight: bold; color: #FFF; background-color: #0087bf; padding: 5px 15px; border-radius: 10px; display: inline-block; }}
    .centriran-tekst {{ text-align: center; width: 100%; margin: 20px 0; }}
    .diskretno-dugme {{ display: flex; justify-content: center; width: 100%; margin-top: 60px !important; }}
    .diskretno-dugme > div > button {{ font-size: 13px !important; color: #0087bf !important; background-color: transparent !important; border: 1px solid #0087bf !important; padding: 5px 15px !important; opacity: 0.8; }}
    </style>
    """, unsafe_allow_html=True)

# --- 6. GOOGLE SHEETS FUNKCIJE ---
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

# --- 7. POMOĆNE FUNKCIJE ---
def obracunaj_sate_i_dane(df):
    if df.empty or 'Vreme' not in df.columns: return pd.DataFrame(), pd.DataFrame()
    df['V_DT'] = pd.to_datetime(df['Vreme'], format="%d.%m.%Y %H:%M:%S", errors='coerce')
    df = df.dropna(subset=['V_DT']).sort_values(['Radnik', 'V_DT'])
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
    df_dani = df.groupby(['Radnik', 'Mesec'])['Vreme'].apply(lambda x: x.str.slice(0,10).nunique()).reset_index(name='Radni Dani')
    return df_sati, df_dani

# --- 8. GRAFIK (EXTRA NIZAK - 100px) ---
def prikazi_grafik_nizak(df):
    if df.empty: return
    try:
        df_plot = df[df['Akcija'] == 'DOLAZAK'].copy()
        df_plot['V_DT'] = pd.to_datetime(df_plot['Vreme'], format="%d.%m.%Y %H:%M:%S", errors='coerce')
        df_plot = df_plot.dropna(subset=['V_DT'])
        df_plot['Datum'] = df_plot['V_DT'].dt.date
        
        idx = pd.date_range(datetime.now().date() - timedelta(days=6), datetime.now().date())
        sve_dnevne = df_plot.groupby('Datum')['Radnik'].nunique().reindex(idx, fill_value=0).reset_index()
        sve_dnevne.columns = ['Datum', 'Radnici']
        sve_dnevne['Danas'] = sve_dnevne['Datum'].dt.date == datetime.now().date()

        base = alt.Chart(sve_dnevne).encode(x=alt.X('Datum:T', axis=None))
        
        # Visina fiksirana na 100
        line = base.mark_line(color='#0087bf', strokeWidth=3).encode(
            y=alt.Y('Radnici:Q', title=None, axis=alt.Axis(tickMinStep=1, grid=False))
        ).properties(height=100)

        point = base.mark_point(filled=True, size=80, color='#28a745').transform_filter(
            alt.datum.Danas == True
        ).encode(y='Radnici:Q')

        st.altair_chart((line + point).configure_view(strokeOpacity=0), use_container_width=True)
    except: pass

# --- 9. PROGRAM ---
df_l, df_k, df_g, df_t = ucitaj_podatke()

if df_k is not None:
    # Grafik bez dodatnog razmaka
    prikazi_grafik_nizak(df_l)

    st.sidebar.title("🔐 Admin")
    lozinka = st.sidebar.text_input("Lozinka:", type="password")
    if lozinka == "admin" and st.sidebar.checkbox("Prikaži Dashboard"):
        # --- ADMIN ---
        br_r, br_g = 0, 0
        tr_p = pd.DataFrame()
        if not df_l.empty:
            tr = df_l.sort_values('Vreme').groupby('Radnik').last().reset_index()
            tr_p = tr[tr['Akcija'] == 'DOLAZAK']
            br_r, br_g = len(tr_p), tr_p['Gradiliste'].nunique()
        
        danas_dt = datetime.now().strftime("%d.%m.%Y")
        u_t_danas = 0 # (Proračun troškova ide ovde...)
        
        st.markdown(f"<div class='admin-naslov'>Admin Kontrola | R{br_r} G{br_g}</div>", unsafe_allow_html=True)
        vest = f"trenutno na gradilištu: {br_r} radnika &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; • &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; tvoj_ticker_ovde"
        st.markdown(f'<div class="ticker-wrap"><div class="ticker-text">{vest}</div></div>', unsafe_allow_html=True)
        tabs = st.tabs(["📅 Danas", "👥 Radnici", "🕒 Dnevnik", "💰 Dnevnice", "🏗️ Gradilišta", "💸 Troškovi"])
        st.stop()

    # --- RADNIK ---
    col_logo, col_txt = st.columns([1, 5])
    with col_logo:
        if os.path.exists("logo.png"): st.image("logo.png", width=90)
    with col_txt:
        st.markdown("<div class='glavni-naslov'>Digitalna prijava</div>", unsafe_allow_html=True)
    
    # ... (ostatak koda ostaje isti)
    p_ime = None; e_cookie = cookies.get("radnik_email")
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
                        dodaj_u_tabelu("korisnici", [i_in, e_in, 0]); cookies["radnik_email"] = e_in; cookies.save(); st.cache_data.clear(); st.rerun()
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
        if status == "ODLAZAK":
            if izbor == "-- klikni ovde i izaberi gradilište --": st.markdown('<div class="onemoguceno-dugme"><button>IZBOR OBAVEZAN</button></div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="trepcuce-dugme">', unsafe_allow_html=True)
                if st.button("✅ PRIJAVI SE NA POSAO"): dodaj_u_tabelu("log", [p_ime, "DOLAZAK", izbor, datetime.now().strftime("%d.%m.%Y %H:%M:%S")]); st.cache_data.clear(); st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="odjava-dugme">', unsafe_allow_html=True)
            if st.button("🛑 ODJAVI SE SA POSLA"): dodaj_u_tabelu("log", [p_ime, "ODLAZAK", izbor, datetime.now().strftime("%d.%m.%Y %H:%M:%S")]); st.cache_data.clear(); st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('<div class="trosak-dugme-plavo">', unsafe_allow_html=True)
        if st.button("💰 DODAJ TROŠAK"): st.session_state.unos_troska = True; st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        st.write("---")
        if st.button("Logout"): del cookies["radnik_email"]; cookies.save(); st.rerun()
