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

# --- 5. STILIZACIJA (POPRAVLJEN CSS - VRAĆENA STRELICA) ---
st.markdown(f"""
    <style>
    /* SMANJENJE PROSTORA NA VRHU I OSTAVLJANJE PROSTORA ZA STRELICU */
    .main .block-container {{ 
        padding-top: 2rem !important; 
        padding-bottom: 1rem !important; 
    }}
    
    /* SAKRIVA SAMO DESNI MENI (TRI TAČKICE) I DEPLOY DUGME */
    [data-testid="stHeaderActionSet"] {{ visibility: hidden; }}
    footer {{ visibility: hidden; }}
    
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
def oboji_dnevnik(row):
    danas = datetime.now().strftime("%d.%m.%Y")
    styles = [''] * len(row)
    if 'Vreme' in row.index and danas in str(row['Vreme']):
        for i, col in enumerate(row.index):
            if col == 'Br.': styles[i] = 'color: #0087bf; font-weight: bold;'
            elif 'Akcija' in row.index:
                if row['Akcija'] == 'DOLAZAK': styles[i] = 'background-color: rgba(40, 167, 69, 0.2); color: #28a745'
                elif row['Akcija'] == 'ODLAZAK': styles[i] = 'background-color: rgba(220, 53, 69, 0.2); color: #dc3545'
    return styles

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
        line = base.mark_line(color='#0087bf', strokeWidth=3).encode(y=alt.Y('Radnici:Q', title=None, axis=alt.Axis(tickMinStep=1, grid=False))).properties(height=100)
        point = base.mark_point(filled=True, size=80, color='#28a745').transform_filter(alt.datum.Danas == True).encode(y='Radnici:Q')
        st.altair_chart((line + point).configure_view(strokeOpacity=0), use_container_width=True)
    except: pass

# --- 9. PROGRAM ---
df_l, df_k, df_g, df_t = ucitaj_podatke()

if df_k is not None:
    st.sidebar.title("🔐 Admin")
    lozinka = st.sidebar.text_input("Lozinka:", type="password")
    if lozinka == "admin" and st.sidebar.checkbox("Prikaži Dashboard"):
        # --- ADMIN OKRUŽENJE ---
        prikazi_grafik_nizak(df_l)
        br_r, br_g = 0, 0
        tr_p = pd.DataFrame()
        if not df_l.empty:
            tr = df_l.sort_values('Vreme').groupby('Radnik').last().reset_index()
            tr_p = tr[tr['Akcija'] == 'DOLAZAK']
            br_r, br_g = len(tr_p), tr_p['Gradiliste'].nunique()
        
        danas_dt = datetime.now().strftime("%d.%m.%Y")
        r_danas_imena = df_l[(df_l['Akcija'] == 'DOLAZAK') & (df_l['Vreme'].str.contains(danas_dt))]['Radnik'].unique() if not df_l.empty else []
        t_d = df_k[df_k['Ime'].isin(r_danas_imena)]['Cena'].astype(float).sum() if not df_k.empty and 'Cena' in df_k.columns else 0
        t_r = df_t[df_t['Vreme'].str.contains(danas_dt)]['Iznos'].astype(float).sum() if not df_t.empty else 0
        u_t_danas = t_d + t_r

        st.markdown(f"<div class='admin-naslov'>Admin Kontrola | R{br_r} G{br_g}</div>", unsafe_allow_html=True)
        vest = f"na gradilištu: {br_r} radnika &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; • &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; trošak: {u_t_danas:,.0f} RSD"
        st.markdown(f'<div class="ticker-wrap"><div class="ticker-text">{vest} &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; • &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; {vest}</div></div>', unsafe_allow_html=True)
        
        tabs = st.tabs(["📅 Danas", "👥 Radnici", "🕒 Dnevnik", "💰 Dnevnice", "🏗️ Gradilišta", "💸 Troškovi"])
        
        with tabs[0]: # DANAS
            st.metric("Aktivno", br_r)
            if br_r > 0: st.dataframe(tr_p[['Radnik', 'Gradiliste', 'Vreme']], use_container_width=True)
            else: st.info("Nema prijavljenih radnika.")
            if not df_l.empty:
                df_danas = df_l[df_l['Vreme'].str.contains(danas_dt)].copy()
                if not df_danas.empty:
                    df_p_danas = df_danas.iloc[::-1].reset_index().rename(columns={'index':'Br.'})
                    st.dataframe(df_p_danas.style.apply(oboji_dnevnik, axis=1), use_container_width=True, hide_index=True)

        with tabs[1]: # RADNICI
            if not st.session_state.get('uredjivanje_cene', False):
                if not df_k.empty:
                    p_k = df_k.copy()
                    if 'Email' in p_k.columns: p_k = p_k.drop(columns=['Email'])
                    st.dataframe(p_k, use_container_width=True)
                    te_m_ime = MESECI_SR[datetime.now().month] + " " + str(datetime.now().year)
                    t_mesec = 0
                    if not df_k.empty and 'Cena' in df_k.columns:
                        c_dict = pd.Series(df_k.Cena.values, index=df_k.Ime).to_dict()
                        _, df_stat_dani = obracunaj_sate_i_dane(df_l)
                        if not df_stat_dani.empty:
                            te_m = df_stat_dani[df_stat_dani['Mesec'] == te_m_ime]
                            for _, row in te_m.iterrows(): t_mesec += row['Radni Dani'] * float(c_dict.get(row['Radnik'], 0))
                    st.markdown(f"<div class='centriran-tekst'><p>Troškovi za danas:<br><span class='trosak-box'>{u_t_danas:,.0f} RSD</span></p></div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='centriran-tekst'><p>Troškovi za mesec:<br><span class='trosak-mesec-box'>{t_mesec:,.0f} RSD</span></p></div>", unsafe_allow_html=True)
                    st.markdown('<div class="diskretno-dugme">', unsafe_allow_html=True)
                    if st.button("📝 Uredi cenu dnevnice"): st.session_state.uredjivanje_cene = True; st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)
            else:
                if st.button("⬅️ Nazad"): st.session_state.uredjivanje_cene = False; st.rerun()
                r_sel = st.selectbox("Radnik:", df_k['Ime'].tolist()); n_c = st.number_input("Nova cena:", step=100)
                if st.button("Sačuvaj"): 
                    client = povezi_google(); ws = client.open("Baza Gradiliste").worksheet("korisnici")
                    cell = ws.find(r_sel); ws.update_cell(cell.row, 3, n_c)
                    st.cache_data.clear(); st.session_state.uredjivanje_cene = False; st.rerun()

        with tabs[2]: # DNEVNIK
            if not df_l.empty:
                df_p = df_l.iloc[::-1].reset_index().rename(columns={'index':'Br.'})
                st.dataframe(df_p.style.apply(oboji_dnevnik, axis=1), use_container_width=True, hide_index=True)

        with tabs[3]: # DNEVNICE
            if not df_l.empty:
                _, d_stat = obracunaj_sate_i_dane(df_l)
                if not d_stat.empty:
                    m_sel = st.selectbox("Izaberi mesec:", d_stat['Mesec'].unique())
                    st.table(d_stat[d_stat['Mesec'] == m_sel][['Radnik', 'Radni Dani']])

        with tabs[4]: # GRADILIŠTA
            n_g = st.text_input("Naziv novog gradilišta:")
            if st.button("Dodaj gradilište"): 
                if n_g: dodaj_u_tabelu("gradilista", [n_g]); st.cache_data.clear(); st.rerun()
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
                st.metric("Ukupno RSD", f"{df_t['Iznos'].astype(float).sum():,.0f}")
        st.stop()

    # --- RADNIČKO OKRUŽENJE ---
    col_logo, col_txt = st.columns([1, 5])
    with col_logo:
        if os.path.exists("logo.png"): st.image("logo.png", width=90)
    with col_txt:
        st.markdown("<div class='glavni-naslov'>Digitalna prijava</div>", unsafe_allow_html=True)
    
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
            with st.expander("📊 Moja evidencija rada"):
                if not df_l.empty:
                    _, df_dani_radnik = obracunaj_sate_i_dane(df_l)
                    m_radnika = df_dani_radnik[df_dani_radnik['Radnik'] == p_ime]
                    if not m_radnika.empty:
                        te_m_ime = MESECI_SR[datetime.now().month] + " " + str(datetime.now().year)
                        d_sad = m_radnika[m_radnika['Mesec'] == te_m_ime]
                        b_d_sad = d_sad['Radni Dani'].values[0] if not d_sad.empty else 0
                        st.info(f"📅 U mesecu **{te_m_ime}** imate: **{b_d_sad} radnih dana**")
                        iz_m = st.selectbox("Istorija:", m_radnika['Mesec'].unique(), index=len(m_radnika['Mesec'].unique())-1)
                        st.write(f"U mesecu **{iz_m}** imali ste: **{m_radnika[m_radnika['Mesec'] == iz_m]['Radni Dani'].values[0]} dana**.")
        st.write("---")
        if st.button("Logout"): del cookies["radnik_email"]; cookies.save(); st.rerun()
