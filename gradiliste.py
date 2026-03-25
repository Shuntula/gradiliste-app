import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from streamlit_cookies_manager import EncryptedCookieManager

# --- KONFIGURACIJA STRANICE ---
st.set_page_config(page_title="Gradilište Log", page_icon="👷", layout="wide")

# --- KOLAČIĆI ---
cookies = EncryptedCookieManager(password="neka_veoma_tajna_sifra_123")
if not cookies.ready():
    st.info("Inicijalizacija sistema...")
    st.stop()

# --- INICIJALIZACIJA STANJA ---
if 'uredjivanje_cene' not in st.session_state: st.session_state.uredjivanje_cene = False
if 'unos_troska' not in st.session_state: st.session_state.unos_troska = False

# --- STILIZACIJA (CSS) ---
st.markdown("""
    <style>
    @keyframes pulse-green { 0% { box-shadow: 0 0 0 0 rgba(40, 167, 69, 0.7); transform: scale(0.98); } 70% { box-shadow: 0 0 0 20px rgba(40, 167, 69, 0); transform: scale(1); } 100% { box-shadow: 0 0 0 0 rgba(40, 167, 69, 0); transform: scale(0.98); } }
    @keyframes pulse-red { 0% { box-shadow: 0 0 0 0 rgba(220, 53, 69, 0.7); transform: scale(0.98); } 70% { box-shadow: 0 0 0 20px rgba(220, 53, 69, 0); transform: scale(1); } 100% { box-shadow: 0 0 0 0 rgba(220, 53, 69, 0); transform: scale(0.98); } }
    
    .trepcuce-dugme > div > button { height: 100px !important; font-size: 24px !important; font-weight: bold !important; color: white !important; background-color: #28a745 !important; animation: pulse-green 2s infinite; border-radius: 15px !important; width: 100% !important; }
    .odjava-dugme > div > button { height: 100px !important; font-size: 24px !important; font-weight: bold !important; color: white !important; background-color: #dc3545 !important; animation: pulse-red 2s infinite; border-radius: 15px !important; width: 100% !important; }
    .trosak-dugme-plavo > div > button { height: 70px !important; font-size: 20px !important; color: white !important; background-color: #007bff !important; border-radius: 15px !important; width: 100% !important; margin-top: 10px !important; }
    .onemoguceno-dugme > div > button { height: 100px !important; background-color: #262730 !important; color: #555 !important; border: 1px solid #444 !important; border-radius: 15px !important; width: 100% !important; pointer-events: none !important; }
    
    .label-radnik { font-size: 16px; color: #BBB; }
    .ime-radnika { font-size: 28px; font-weight: bold; color: #FFF; }
    
    /* POVEĆAN NASLOV ADMINA */
    .admin-naslov { 
        font-size: 32px; /* Povećano sa 22px */
        font-weight: bold; 
        text-align: center; 
        width: 100%; 
        margin-bottom: 50px; 
        padding: 10px; 
        border-bottom: 1px solid #333; 
    }
    
    .trosak-box { font-size: 22px; font-weight: bold; color: #FF4B4B; padding: 5px 15px; border: 2px solid #FF4B4B; border-radius: 10px; display: inline-block; }
    .trosak-mesec-box { font-size: 22px; font-weight: bold; color: #FFA500; padding: 5px 15px; border: 2px solid #FFA500; border-radius: 10px; display: inline-block; }
    .centriran-tekst { text-align: center; width: 100%; margin: 20px 0; }
    
    .diskretno-dugme { display: flex; justify-content: center; width: 100%; margin-top: 60px !important; }
    .diskretno-dugme > div > button { font-size: 13px !important; color: #888 !important; background-color: transparent !important; border: 1px solid #444 !important; padding: 5px 15px !important; opacity: 0.7; }
    </style>
    """, unsafe_allow_html=True)

# --- GOOGLE SHEETS FUNKCIJE ---
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
def oboji_dnevnik(row):
    danas = datetime.now().strftime("%d.%m.%Y")
    styles = [''] * len(row)
    if danas in str(row['Vreme']):
        for i, col in enumerate(row.index):
            if col == 'Br.': styles[i] = 'color: #007bff; font-weight: bold;'
            elif row['Akcija'] == 'DOLAZAK': styles[i] = 'background-color: #c3e6cb; color: #155724'
            elif row['Akcija'] == 'ODLAZAK': styles[i] = 'background-color: #f5c6cb; color: #721c24'
    return styles

def obracunaj_sate_i_dane(df):
    if df.empty: return pd.DataFrame(), pd.DataFrame()
    df['V_DT'] = pd.to_datetime(df['Vreme'], format="%d.%m.%Y %H:%M:%S", errors='coerce')
    df = df.dropna(subset=['V_DT']).sort_values(['Radnik', 'V_DT'])
    sati = []
    for r in df['Radnik'].unique():
        rd = df[df['Radnik'] == r]
        dv = None
        for _, row in rd.iterrows():
            if row['Akcija'] == "DOLAZAK": dv = row['V_DT']
            elif row['Akcija'] == "ODLAZAK" and dv:
                diff = (row['V_DT'] - dv).total_seconds()
                if diff > 0: sati.append([r, dv.strftime("%m-%Y"), diff])
                dv = None
    df_s = pd.DataFrame(sati, columns=["Radnik", "Mesec", "Sekunde"])
    df_d = df.groupby(['Radnik', df['V_DT'].dt.strftime("%m-%Y")])['Vreme'].apply(lambda x: x.str.slice(0,10).nunique()).reset_index(name='Radni Dani')
    df_d.columns = ['Radnik', 'Mesec', 'Radni Dani']
    return df_s, df_d

# --- GLAVNI PROGRAM ---
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
        
        st.markdown(f"<div class='admin-naslov'>📊 Admin Kontrola | R{br_r} G{br_g}</div>", unsafe_allow_html=True)
        tabs = st.tabs(["📅 Danas", "👥 Radnici", "🕒 Dnevnik", "💰 Dnevnice", "🏗️ Gradilišta", "💸 Troškovi"])
        
        with tabs[0]: # DANAS
            st.metric("Aktivno", br_r)
            st.subheader("Pregled aktivnosti za danas")
            if br_r > 0: st.dataframe(tr_p[['Radnik', 'Gradiliste', 'Vreme']], use_container_width=True)
            else: st.info("Nema prijavljenih.")
            danas_str = datetime.now().strftime("%d.%m.%Y")
            df_danas = df_l[df_l['Vreme'].str.contains(danas_str)].copy() if not df_l.empty else pd.DataFrame()
            if not df_danas.empty:
                st.dataframe(df_danas.iloc[::-1].reset_index().rename(columns={'index':'Br.'}).style.apply(oboji_dnevnik, axis=1), use_container_width=True, hide_index=True)

        with tabs[1]: # RADNICI
            if not st.session_state.get('uredjivanje_cene', False):
                st.subheader("Lista radnika")
                if not df_k.empty:
                    p_k = df_k.copy()
                    if 'Email' in p_k.columns: p_k = p_k.drop(columns=['Email'])
                    st.dataframe(p_k, use_container_width=True)
                    
                    danas_dt, mesec_dt = datetime.now().strftime("%d.%m.%Y"), datetime.now().strftime("%m-%Y")
                    r_danas = df_l[(df_l['Akcija'] == 'DOLAZAK') & (df_l['Vreme'].str.contains(danas_dt))]['Radnik'].unique() if not df_l.empty else []
                    
                    t_danas, t_mesec = 0, 0
                    if 'Cena' in df_k.columns:
                        cene_dict = pd.Series(df_k.Cena.values, index=df_k.Ime).to_dict()
                        for r in r_danas: t_danas += float(cene_dict.get(r, 0))
                        _, df_stat_dani = obracunaj_sate_i_dane(df_l)
                        if not df_stat_dani.empty:
                            te_m = df_stat_dani[df_stat_dani['Mesec'] == mesec_dt]
                            for _, row in te_m.iterrows():
                                t_mesec += row['Radni Dani'] * float(cene_dict.get(row['Radnik'], 0))

                    st.markdown(f"""
                        <div class='centriran-tekst'>
                            <p style='margin-bottom:5px; font-size:16px;'>Troškovi za danas:</p>
                            <span class='trosak-box'>{t_danas:,.0f} RSD</span>
                        </div>
                        <div class='centriran-tekst'>
                            <p style='margin-bottom:5px; font-size:16px;'>Troškovi u tekućem mesecu:</p>
                            <span class='trosak-mesec-box'>{t_mesec:,.0f} RSD</span>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    st.markdown('<div class="diskretno-dugme">', unsafe_allow_html=True)
                    if st.button("📝 Uredi cenu dnevnice"): st.session_state.uredjivanje_cene = True; st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)
            else:
                if st.button("⬅️ Nazad"): st.session_state.uredjivanje_cene = False; st.rerun()
                r_sel = st.selectbox("Radnik:", df_k['Ime'].tolist())
                n_c = st.number_input("Nova cena:", step=100)
                if st.button("Sačuvaj"): 
                    client = povezi_google()
                    ws = client.open("Baza Gradiliste").worksheet("korisnici")
                    cell = ws.find(r_sel)
                    if cell: ws.update_cell(cell.row, 3, n_c)
                    st.cache_data.clear(); st.session_state.uredjivanje_cene = False; st.rerun()

        with tabs[2]: # DNEVNIK
            if not df_l.empty:
                df_p = df_l.iloc[::-1].reset_index().rename(columns={'index':'Br.'})
                st.dataframe(df_p.style.apply(oboji_dnevnik, axis=1), use_container_width=True, hide_index=True)
        
        with tabs[3]: # DNEVNICE
            if not df_l.empty:
                _, d_stat = obracunaj_sate_i_dane(df_l)
                if not d_stat.empty:
                    m_sel = st.selectbox("Mesec:", d_stat['Mesec'].unique())
                    st.table(d_stat[d_stat['Mesec'] == m_sel][['Radnik', 'Radni Dani']])

        with tabs[4]: # GRADILIŠTA
            n_g = st.text_input("Novo gradilište:")
            if st.button("Dodaj"): dodaj_u_tabelu("gradilista", [n_g]); st.cache_data.clear(); st.rerun()
            if not df_g.empty:
                if not df_l.empty:
                    dolasci = df_l[df_l['Akcija'] == 'DOLAZAK'].copy()
                    dolasci['Datum'] = dolasci['Vreme'].str.slice(0,10)
                    stat_g = dolasci.drop_duplicates(subset=['Radnik', 'Gradiliste', 'Datum']).groupby('Gradiliste').size().reset_index(name='Ukupno Prijave')
                    st.dataframe(pd.merge(df_g, stat_g, left_on='Naziv', right_on='Gradiliste', how='left').fillna(0)[['Naziv', 'Ukupno Prijave']], use_container_width=True)
                else: st.dataframe(df_g, use_container_width=True)

        with tabs[5]: # TROŠKOVI
            if not df_t.empty:
                st.dataframe(df_t.iloc[::-1], use_container_width=True)
                st.metric("Ukupno troškovi", f"{df_t['Iznos'].astype(float).sum():,.0f} RSD")
        st.stop()

    # --- RADNIČKO OKRUŽENJE ---
    st.title("👷 Digitalna Prijava")
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
                        cookies["radnik_email"] = e_in; cookies.save(); st.cache_data.clear(); st.rerun()
    else:
        if st.session_state.get('unos_troska', False):
            st.subheader("💰 Unos troška")
            if st.button("⬅️ Nazad"): st.session_state.unos_troska = False; st.rerun()
            kat = st.selectbox("Kategorija:", ["GORIVO", "HRANA", "MATERIJAL", "DRUGO"])
            izn = st.number_input("Iznos RSD:", min_value=0, step=50)
            grad_t = st.selectbox("Gradilište:", df_g['Naziv'].tolist() if not df_g.empty else ["Nema"])
            if st.button("✅ SAČUVAJ"):
                if izn > 0:
                    dodaj_u_tabelu("troskovi", [p_ime, grad_t, kat, izn, datetime.now().strftime("%d.%m.%Y %H:%M:%S")])
                    st.cache_data.clear(); st.session_state.unos_troska = False; st.rerun()
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
                    if st.button("✅ PRIJAVI SE NA POSAO"): dodaj_u_tabelu("log", [p_ime, "DOLAZAK", izbor, v_sad]); st.cache_data.clear(); st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="odjava-dugme">', unsafe_allow_html=True)
                if st.button("🛑 ODJAVI SE SA POSLA"): dodaj_u_tabelu("log", [p_ime, "ODLAZAK", izbor, v_sad]); st.cache_data.clear(); st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('<div class="trosak-dugme-plavo">', unsafe_allow_html=True)
            if st.button("💰 DODAJ TROŠAK"): st.session_state.unos_troska = True; st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        st.write("---")
        if st.button("Logout"): del cookies["radnik_email"]; cookies.save(); st.rerun()
