import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from streamlit_cookies_manager import EncryptedCookieManager

# --- KONFIGURACIJA STRANICE ---
st.set_page_config(page_title="Gradilište Log", page_icon="👷", layout="wide")

# --- INICIJALIZACIJA STANJA ---
if 'uredjivanje_cene' not in st.session_state:
    st.session_state.uredjivanje_cene = False

# --- STILIZACIJA (Dugmići i Animacije) ---
st.markdown("""
    <style>
    @keyframes blinking {
        0% { background-color: #28a745; box-shadow: 0 0 5px #28a745; }
        50% { background-color: #58d68d; box-shadow: 0 0 20px #58d68d; }
        100% { background-color: #28a745; box-shadow: 0 0 5px #28a745; }
    }
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
    .admin-naslov { font-size: 20px; font-weight: bold; margin-bottom: 15px; }
    .trosak-box { font-size: 24px; font-weight: bold; color: #FF4B4B; padding: 5px 10px; border: 2px solid #FF4B4B; border-radius: 10px; display: inline-block; }
    .trosak-mesec-box { font-size: 24px; font-weight: bold; color: #FFA500; padding: 5px 10px; border: 2px solid #FFA500; border-radius: 10px; display: inline-block; }
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

def azuriraj_cenu_radnika(ime, nova_cena):
    client = povezi_google()
    sh = client.open("Baza Gradiliste")
    ws = sh.worksheet("korisnici")
    cell = ws.find(ime)
    if cell:
        ws.update_cell(cell.row, 3, nova_cena)
        st.cache_data.clear()

# --- FUNKCIJA ZA BOJENJE DNEVNIKA ---
def oboji_dnevnik(row):
    danas = datetime.now().strftime("%d.%m.%Y")
    styles = [''] * len(row)
    if danas in str(row['Vreme']):
        for i, col_name in enumerate(row.index):
            if col_name == 'Br.':
                styles[i] = 'color: #007bff; font-weight: bold;'
            elif row['Akcija'] == 'DOLAZAK':
                styles[i] = 'background-color: #c3e6cb; color: #155724'
            elif row['Akcija'] == 'ODLAZAK':
                styles[i] = 'background-color: #f5c6cb; color: #721c24'
    return styles

# --- POMOĆNE FUNKCIJE ZA OBRAČUN ---
def format_u_hms(ukupno_sekundi):
    sati, ostalo = divmod(int(ukupno_sekundi), 3600)
    minuti, sekunde = divmod(ostalo, 60)
    return f"{sati:02d}:{minuti:02d}:{sekunde:02d}"

def obracunaj_sate_i_dane(df):
    if df.empty or 'Vreme' not in df.columns: return pd.DataFrame(), pd.DataFrame()
    df['Vreme_DT'] = pd.to_datetime(df['Vreme'], format="%d.%m.%Y %H:%M:%S", errors='coerce')
    df = df.dropna(subset=['Vreme_DT']).sort_values(['Radnik', 'Vreme_DT'])
    df['Mesec'] = df['Vreme_DT'].dt.strftime("%m-%Y")
    df['Datum'] = df['Vreme_DT'].dt.strftime("%d.%m.%Y")
    
    obracun_sati = []
    for radnik in df['Radnik'].unique():
        radnik_data = df[df['Radnik'] == radnik]
        dolazak_vreme = None
        for _, row in radnik_data.iterrows():
            if row['Akcija'] == "DOLAZAK": dolazak_vreme = row['Vreme_DT']
            elif row['Akcija'] == "ODLAZAK" and dolazak_vreme is not None:
                razlika = (row['Vreme_DT'] - dolazak_vreme).total_seconds()
                if razlika > 0: obracun_sati.append([radnik, row['Mesec'], razlika])
                dolazak_vreme = None
    
    df_sati = pd.DataFrame(obracun_sati, columns=["Radnik", "Mesec", "Sekunde"])
    df_dani = df.groupby(['Radnik', 'Mesec'])['Datum'].nunique().reset_index(name='Radni Dani')
    return df_sati, df_dani

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
        
        st.markdown(f"<div class='admin-naslov'>📊 Admin Kontrola | R{broj_r} G{broj_g_aktivno}</div>", unsafe_allow_html=True)
        
        # PREIMENOVANA KARTICA "Sati" U "Dnevnice"
        tabs = st.tabs(["📅 Danas", "🕒 Dnevnik", "👥 Radnici", "💰 Dnevnice", "🏗️ Gradilišta"])
        
        with tabs[0]: # DANAS
            st.metric("Aktivnih radnika", broj_r)
            st.subheader("Pregled aktivnosti za danas")
            if not df_prisutni_admin.empty:
                st.dataframe(df_prisutni_admin[['Radnik', 'Gradiliste', 'Vreme']], use_container_width=True)
            else: st.info("Nema prijavljenih.")
            st.divider()
            danas_str = datetime.now().strftime("%d.%m.%Y")
            df_danas = df_l[df_l['Vreme'].str.contains(danas_str)].copy()
            if not df_danas.empty:
                df_p_danas = df_danas.iloc[::-1].reset_index().rename(columns={'index': 'Br.'})
                st.dataframe(df_p_danas.style.apply(oboji_dnevnik, axis=1), use_container_width=True, hide_index=True)

        with tabs[1]: # DNEVNIK
            if not df_l.empty:
                df_l_prikaz = df_l.iloc[::-1].reset_index().rename(columns={'index': 'Br.'})
                st.dataframe(df_l_prikaz.style.apply(oboji_dnevnik, axis=1), use_container_width=True, hide_index=True)
            else: st.info("Dnevnik je prazan.")
        
        with tabs[2]: # RADNICI
            if not st.session_state.uredjivanje_cene:
                st.subheader("Lista radnika i dnevnice")
                if not df_k.empty:
                    p_radnika = df_k.copy()
                    if 'Email' in p_radnika.columns: p_radnika = p_radnika.drop(columns=['Email'])
                    if 'Cena' in p_radnika.columns: p_radnika = p_radnika.rename(columns={'Cena': 'cena [dan]'})
                    st.dataframe(p_radnika, use_container_width=True)
                    
                    # Troškovi
                    danas_str = datetime.now().strftime("%d.%m.%Y")
                    mesec_str = datetime.now().strftime("%m-%Y")
                    r_danas = df_l[(df_l['Akcija'] == 'DOLAZAK') & (df_l['Vreme'].str.contains(danas_str))]['Radnik'].unique()
                    t_danas, t_mesec = 0, 0
                    if 'Cena' in df_k.columns and not df_l.empty:
                        c_dict = pd.Series(df_k.Cena.values, index=df_k.Ime).to_dict()
                        for r in r_danas: t_danas += float(c_dict.get(r, 0))
                        _, d_stat = obracunaj_sate_i_dane(df_l)
                        if not d_stat.empty:
                            te_mesec = d_stat[d_stat['Mesec'] == mesec_str]
                            for _, row in te_mesec.iterrows():
                                t_mesec += row['Radni Dani'] * float(c_dict.get(row['Radnik'], 0))

                    st.markdown(f"<p style='font-size:18px;'>Troškovi za danas: <span class='trosak-box'>{t_danas:,.0f} RSD</span></p>", unsafe_allow_html=True)
                    st.markdown(f"<p style='font-size:18px;'>Troškovi u tekućem mesecu: <span class='trosak-mesec-box'>{t_mesec:,.0f} RSD</span></p>", unsafe_allow_html=True)
                    if st.button("📝 Uredi cenu dnevnice"): st.session_state.uredjivanje_cene = True; st.rerun()
            else:
                st.subheader("⚙️ Podešavanje dnevnice")
                if st.button("⬅️ Nazad"): st.session_state.uredjivanje_cene = False; st.rerun()
                col_r, col_c = st.columns(2)
                with col_r: iz_r = st.selectbox("Radnik:", df_k['Ime'].tolist())
                with col_c:
                    cur_c = int(df_k[df_k['Ime'] == iz_r]['Cena'].values[0]) if 'Cena' in df_k.columns else 0
                    new_c = st.number_input("Cena:", value=cur_c, step=100)
                if st.button("✅ Sačuvaj"): azuriraj_cenu_radnika(iz_r, new_c); st.rerun()

        with tabs[3]: # TAB DNEVNICE (Prikaz samo Radnika i Dana)
            if not df_l.empty:
                _, df_dani_stat = obracunaj_sate_i_dane(df_l)
                if not df_dani_stat.empty:
                    svi_meseci = df_dani_stat['Mesec'].unique()
                    m_izbor = st.selectbox("Izaberi mesec za pregled radnih dana:", svi_meseci)
                    prikaz_dnevnica =
