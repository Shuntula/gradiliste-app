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
if 'unos_troska' not in st.session_state:
    st.session_state.unos_troska = False

# --- STILIZACIJA (Pulsiranje, Dugmići i Centriranje) ---
st.markdown("""
    <style>
    @keyframes pulse-green {
        0% { box-shadow: 0 0 0 0 rgba(40, 167, 69, 0.7); transform: scale(0.98); }
        70% { box-shadow: 0 0 0 20px rgba(40, 167, 69, 0); transform: scale(1); }
        100% { box-shadow: 0 0 0 0 rgba(40, 167, 69, 0); transform: scale(0.98); }
    }
    @keyframes pulse-red {
        0% { box-shadow: 0 0 0 0 rgba(220, 53, 69, 0.7); transform: scale(0.98); }
        70% { box-shadow: 0 0 0 20px rgba(220, 53, 69, 0); transform: scale(1); }
        100% { box-shadow: 0 0 0 0 rgba(220, 53, 69, 0); transform: scale(0.98); }
    }
    .trepcuce-dugme > div > button {
        height: 100px !important; font-size: 24px !important; font-weight: bold !important;
        color: white !important; background-color: #28a745 !important;
        animation: pulse-green 2s infinite; border: none !important; border-radius: 15px !important; width: 100% !important;
    }
    .odjava-dugme > div > button {
        height: 100px !important; font-size: 24px !important; font-weight: bold !important;
        background-color: #dc3545 !important; color: white !important;
        animation: pulse-red 2s infinite; border: none !important; border-radius: 15px !important; width: 100% !important;
    }
    .trosak-dugme-plavo > div > button {
        height: 70px !important; font-size: 20px !important; font-weight: bold !important;
        color: white !important; background-color: #007bff !important;
        border: none !important; border-radius: 15px !important; width: 100% !important;
        margin-top: 10px !important;
    }
    .onemoguceno-dugme > div > button {
        height: 100px !important; background-color: #262730 !important;
        color: #555 !important; border: 1px solid #444 !important;
        border-radius: 15px !important; width: 100% !important;
        pointer-events: none !important; font-weight: bold !important;
    }
    .label-radnik { font-size: 16px; color: #BBB; }
    .ime-radnika { font-size: 28px; font-weight: bold; color: #FFF; }
    
    /* CENTRIRAN NASLOV ADMINA SA RAZMAKOM NA DOLE */
    .admin-naslov { 
        font-size: 22px; 
        font-weight: bold; 
        text-align: center; 
        width: 100%;
        margin-top: 10px;
        margin-bottom: 50px; /* Ovo gura kartice na dole */
        padding: 10px;
        border-bottom: 1px solid #333;
    }

    .trosak-box { font-size: 22px; font-weight: bold; color: #FF4B4B; padding: 5px 10px; border: 2px solid #FF4B4B; border-radius: 10px; display: inline-block; }
    .trosak-mesec-box { font-size: 22px; font-weight: bold; color: #FFA500; padding: 5px 10px; border: 2px solid #FFA500; border-radius: 10px; display: inline-block; }
    </style>
    """, unsafe_allow_html=True)

# --- POVEZIVANJE SA GOOGLE ---
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
    try: df_t = pd.DataFrame(sh.worksheet("troskovi").get_all_records())
    except: df_t = pd.DataFrame(columns=["Radnik", "Gradiliste", "Kategorija", "Iznos", "Vreme"])
    return df_l, df_k, df_g, df_t

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

# --- POMOĆNE FUNKCIJE ---
def oboji_dnevnik(row):
    danas = datetime.now().strftime("%d.%m.%Y")
    styles = [''] * len(row)
    if danas in str(row['Vreme']):
        for i, col_name in enumerate(row.index):
            if col_name == 'Br.': styles[i] = 'color: #007bff; font-weight: bold;'
            elif row['Akcija'] == 'DOLAZAK': styles[i] = 'background-color: #c3e6cb; color: #155724'
            elif row['Akcija'] == 'ODLAZAK': styles[i] = 'background-color: #f5c6cb; color: #721c24'
    return styles

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
    return pd.DataFrame(obracun_sati, columns=["Radnik", "Mesec", "Sekunde"]), df.groupby(['Radnik', 'Mesec'])['Datum'].nunique().reset_index(name='Radni Dani')

# --- KOLAČIĆI ---
cookies = EncryptedCookieManager(password="neka_veoma_tajna_sifra_123")
if not cookies.ready(): st.stop()

# Učitavanje podataka
try:
    df_l, df_k, df_g, df_t = ucitaj_sve_podatke()
except Exception as e:
    st.error(f"Greška pri učitavanju: {e}"); st.stop()

# --- ADMIN OKRUŽENJE ---
st.sidebar.title("🔐 Admin")
if st.sidebar.text_input("Lozinka:", type="password") == "admin":
    if st.sidebar.checkbox("Prikaži Admin Dashboard"):
        broj_r, broj_g_aktivno = 0, 0
        if not df_l.empty:
            trenutno = df_l.sort_values('Vreme').groupby('Radnik').last().reset_index()
            df_prisutni_admin = trenutno[trenutno['Akcija'] == 'DOLAZAK']
            broj_r, broj_g_aktivno = len(df_prisutni_admin), df_prisutni_admin['Gradiliste'].nunique()
        
        # CENTRIRAN NASLOV SA RAZMAKOM
        st.markdown(f"<div class='admin-naslov'>📊 Admin Kontrola | R{broj_r} G{broj_g_aktivno}</div>", unsafe_allow_html=True)
        
        tabs = st.tabs(["📅 Danas", "🕒 Dnevnik", "👥 Radnici", "💰 Dnevnice", "🏗️ Gradilišta", "💸 Troškovi"])
        
        with tabs[0]: # DANAS
            st.metric("Aktivnih radnika", broj_r)
            st.subheader("Pregled aktivnosti za danas")
            if not df_l.empty and broj_r > 0: st.dataframe(df_prisutni_admin[['Radnik', 'Gradiliste', 'Vreme']], use_container_width=True)
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

        with tabs[2]: # RADNICI
            if not st.session_state.uredjivanje_cene:
                st.subheader("Lista radnika")
                if not df_k.empty:
                    p_radnika = df_k.copy()
                    if 'Email' in p_radnika.columns: p_radnika = p_radnika.drop(columns=['Email'])
                    st.dataframe(p_radnika, use_container_width=True)
                    st.button("📝 Uredi cenu dnevnice", on_click=lambda: setattr(st.session_state, 'uredjivanje_cene', True))
            else:
                if st.button("⬅️ Nazad"): st.session_state.uredjivanje_cene = False; st.rerun()
                col_r, col_c = st.columns(2)
                iz_r = st.selectbox("Radnik:", df_k['Ime'].tolist())
                new_c = st.number_input("Nova Cena:", step=100)
                if st.button("✅ Sačuvaj"): azuriraj_cenu_radnika(iz_r, new_c); st.rerun()

        with tabs[3]: # DNEVNICE
            if not df_l.empty:
                _, df_dani_stat = obracunaj_sate_i_dane(df_l)
                if not df_dani_stat.empty:
                    m_izbor = st.selectbox("Izaberi mesec:", df_dani_stat['Mesec'].unique())
                    st.table(df_dani_stat[df_dani_stat['Mesec'] == m_izbor][['Radnik', 'Radni Dani']])

        with tabs[4]: # GRADILIŠTA
            novo = st.text_input("Novo gradilište:")
            if st.button("Dodaj"): 
                if novo: dodaj_u_tabelu("gradilista", [novo]); st.rerun()
            st.dataframe(df_g, use_container_width=True)

        with tabs[5]: # TROŠKOVI
            st.subheader("Svi troškovi")
            if not df_t.empty:
                st.dataframe(df_t.iloc[::-1], use_container_width=True)
                st.metric("Ukupno", f"{df_t['Iznos'].astype(float).sum():,.0f} RSD")
        st.stop()

# --- RADNIČKO OKRUŽENJE ---
st.title("👷 Digitalna Prijava")
e_cookie = cookies.get("radnik_email")
p_ime = None
if e_cookie and not df_k.empty:
    match = df_k[df_k['Email'] == e_cookie]
    if not match.empty: p_ime = match.iloc[0]['Ime']

if not p_ime:
    e_in = st.text_input("Email:").strip().lower()
    if e_in:
        match = df_k[df_k['Email'] == e_in] if not df_k.empty else pd.DataFrame()
        if not match.empty:
            if st.button(f"Prijavi me kao {match.iloc[0]['Ime']}"):
                cookies["radnik_email"] = e_in; cookies.save(); st.rerun()
        else:
            i_in = st.text_input("Ime i Prezime:")
            if st.button("Registruj me"):
                if i_in and e_in:
                    dodaj_u_tabelu("korisnici", [i_in, e_in, 0]); cookies["radnik_email"] = e_in; cookies.save(); st.rerun()
else:
    if st.session_state.unos_troska:
        st.subheader("💰 Unos troška")
        if st.button("⬅️ Otkaži"): st.session_state.unos_troska = False; st.rerun()
        kat = st.selectbox("Šta?", ["GORIVO", "HRANA", "MATERIJAL", "DRUGO"])
        izn = st.number_input("Iznos:", min_value=0, step=50)
        grad_t = st.selectbox("Gradilište?", df_g['Naziv'].tolist() if not df_g.empty else ["Nema"])
        if st.button("✅ SAČUVAJ", use_container_width=True):
            if izn > 0:
                dodaj_u_tabelu("troskovi", [p_ime, grad_t, kat, izn, datetime.now().strftime("%d.%m.%Y %H:%M:%S")])
                st.session_state.unos_troska = False; st.rerun()
    else:
        status, posl_g = "ODLAZAK", None
        if not df_l.empty:
            r_logs = df_l[df_l['Radnik'] == p_ime]
            if not r_logs.empty: status = r_logs.iloc[-1]['Akcija']; posl_g = r_logs.iloc[-1]['Gradiliste']

        st.markdown(f"<span class='label-radnik'>radnik:</span> <span class='ime-radnika'>{p_ime}</span>", unsafe_allow_html=True)
        l_g = ["-- klikni ovde i izaberi gradilište --"] + df_g['Naziv'].tolist()
        def_idx = l_g.index(posl_g) if posl_g in l_g else 0
        izbor = st.selectbox("🚩 gde se nalazite trenutno?", l_g, index=def_idx)
        st.write("---")
        if status == "ODLAZAK":
            if izbor == "-- klikni ovde i izaberi gradilište --":
                st.markdown('<div class="onemoguceno-dugme"><button>IZBOR GRADILIŠTA OBAVEZAN</button></div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="trepcuce-dugme">', unsafe_allow_html=True)
                if st.button("✅ PRIJAVI SE NA POSAO"):
                    dodaj_u_tabelu("log", [p_ime, "DOLAZAK", izbor, datetime.now().strftime("%d.%m.%Y %H:%M:%S")]); st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="odjava-dugme">', unsafe_allow_html=True)
            if st.button("🛑 ODJAVI SE SA POSLA"):
                dodaj_u_tabelu("log", [p_ime, "ODLAZAK", izbor, datetime.now().strftime("%d.%m.%Y %H:%M:%S")]); st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('<div class="trosak-dugme-plavo">', unsafe_allow_html=True)
        if st.button("💰 DODAJ TROŠAK"): st.session_state.unos_troska = True; st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    st.write("---")
    if st.button("Logout"): del cookies["radnik_email"]; cookies.save(); st.rerun()
