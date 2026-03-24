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

# --- UNAPREĐENA FUNKCIJA ZA BOJENJE ---
def oboji_dnevnik(row):
    danas = datetime.now().strftime("%d.%m.%Y")
    styles = [''] * len(row)
    
    if danas in str(row['Vreme']):
        for i, col_name in enumerate(row.index):
            if col_name == 'Br.':
                # Bojimo redni broj u PLAVO
                styles[i] = 'color: #007bff; font-weight: bold;'
            elif row['Akcija'] == 'DOLAZAK':
                styles[i] = 'background-color: #c3e6cb; color: #155724'
            elif row['Akcija'] == 'ODLAZAK':
                styles[i] = 'background-color: #f5c6cb; color: #721c24'
    return styles

# --- POMOĆNE FUNKCIJE ---
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
        tabs = st.tabs(["📅 Danas", "🕒 Dnevnik", "👥 Radnici", "⏱️ Sati", "🏗️ Gradilišta"])
        
        with tabs[0]: # DANAS
            st.metric("Aktivnih radnika", broj_r)
            st.subheader("Pregled aktivnosti za danas")
            if not df_prisutni_admin.empty:
                st.write("Trenutno prijavljeni radnici:")
                st.dataframe(df_prisutni_admin[['Radnik', 'Gradiliste', 'Vreme']], use_container_width=True)
            else: st.info("Nema prijavljenih.")
            st.divider()
            danas_str = datetime.now().strftime("%d.%m.%Y")
            df_danas = df_l[df_l['Vreme'].str.contains(danas_str)].copy()
            if not df_danas.empty:
                # Dodajemo kolonu sa rednim brojem
                df_prikaz_danas = df_danas.iloc[::-1].reset_index().rename(columns={'index': 'Br.'})
                st.dataframe(df_prikaz_danas.style.apply(oboji_dnevnik, axis=1), use_container_width=True, hide_index=True)

        with tabs[1]: # DNEVNIK
            if not df_l.empty:
                # Resetujemo indeks da bi on postao kolona koju možemo bojiti
                df_l_prikaz = df_l.iloc[::-1].reset_index().rename(columns={'index': 'Br.'})
                st.dataframe(df_l_prikaz.style.apply(oboji_dnevnik, axis=1), use_container_width=True, hide_index=True)
            else: st.info("Dnevnik je prazan.")
        
        with tabs[2]: # RADNICI
            if not st.session_state.uredjivanje_cene:
                st.subheader("Lista radnika i dnevnice")
                if not df_k.empty:
                    prikaz_radnika = df_k.copy()
                    if 'Email' in prikaz_radnika.columns: prikaz_radnika = prikaz_radnika.drop(columns=['Email'])
                    if 'Cena' in prikaz_radnika.columns: prikaz_radnika = prikaz_radnika.rename(columns={'Cena': 'cena [dan]'})
                    st.dataframe(prikaz_radnika, use_container_width=True)
                    
                    danas_str = datetime.now().strftime("%d.%m.%Y")
                    mesec_str = datetime.now().strftime("%m-%Y")
                    radnici_danas = df_l[(df_l['Akcija'] == 'DOLAZAK') & (df_l['Vreme'].str.contains(danas_str))]['Radnik'].unique()
                    trosak_danas = 0
                    trosak_mesec = 0
                    if 'Cena' in df_k.columns and not df_l.empty:
                        cene_dict = pd.Series(df_k.Cena.values, index=df_k.Ime).to_dict()
                        for r in radnici_danas: trosak_danas += float(cene_dict.get(r, 0))
                        _, df_stat_dani = obracunaj_sate_i_dane(df_l)
                        if not df_stat_dani.empty:
                            te_mesec = df_stat_dani[df_stat_dani['Mesec'] == mesec_str]
                            for _, row in te_mesec.iterrows():
                                c_radna = float(cene_dict.get(row['Radnik'], 0))
                                trosak_mesec += row['Radni Dani'] * c_radna

                    st.markdown(f"<p style='font-size:18px;'>Troškovi za danas: <span class='trosak-box'>{trosak_danas:,.0f} RSD</span></p>", unsafe_allow_html=True)
                    st.markdown(f"<p style='font-size:18px;'>Troškovi u tekućem mesecu: <span class='trosak-mesec-box'>{trosak_mesec:,.0f} RSD</span></p>", unsafe_allow_html=True)
                    if st.button("📝 Uredi cenu dnevnice"): st.session_state.uredjivanje_cene = True; st.rerun()
            else:
                st.subheader("⚙️ Podešavanje dnevnice")
                if st.button("⬅️ Nazad"): st.session_state.uredjivanje_cene = False; st.rerun()
                st.divider()
                col_r, col_c = st.columns(2)
                with col_r: izabrani_r = st.selectbox("Izaberi radnika:", df_k['Ime'].tolist())
                with col_c:
                    t_c = 0
                    if 'Cena' in df_k.columns:
                        try: t_c = int(df_k[df_k['Ime'] == izabrani_r]['Cena'].values[0])
                        except: t_c = 0
                    n_c = st.number_input("Nova cena:", value=t_c, step=100)
                if st.button("✅ Sačuvaj"): azuriraj_cenu_radnika(izabrani_r, n_c); st.success("Sačuvano!"); st.rerun()

        with tabs[4]: # GRADILIŠTA
            novo = st.text_input("Novo gradilište:")
            if st.button("Dodaj"): 
                if novo: dodaj_u_tabelu("gradilista", [novo]); st.rerun()
            if not df_g.empty:
                temp_l = df_l.copy() if not df_l.empty else pd.DataFrame(columns=['Vreme', 'Akcija', 'Radnik', 'Gradiliste'])
                if not temp_l.empty:
                    temp_l['Datum'] = temp_l['Vreme'].str.slice(0, 10)
                    dolasci = temp_l[temp_l['Akcija'] == 'DOLAZAK'].drop_duplicates(subset=['Radnik', 'Gradiliste', 'Datum'])
                    stat_g = dolasci.groupby('Gradiliste').size().reset_index(name='Ukupno Prijave')
                    p_g = pd.merge(df_g, stat_g, left_on='Naziv', right_on='Gradiliste', how='left')
                    p_g['Ukupno Prijave'] = p_g['Ukupno Prijave'].fillna(0).astype(int)
                    st.dataframe(p_g[['Naziv', 'Ukupno Prijave']], use_container_width=True)
            
        with tabs[3]: # SATI
            if not df_l.empty:
                df_sati, df_dani = obracunaj_sate_i_dane(df_l)
                if not df_sati.empty:
                    m = st.selectbox("Izaberi mesec:", df_sati['Mesec'].unique())
                    f_sati = df_sati[df_sati['Mesec'] == m].groupby('Radnik')['Sekunde'].sum().reset_index()
                    f_sati['Ukupno Vreme'] = f_sati['Sekunde'].apply(format_u_hms)
                    f_dani = df_dani[df_dani['Mesec'] == m]
                    kon_obr = pd.merge(f_sati, f_dani, on='Radnik')
                    st.table(kon_obr[['Radnik', 'Ukupno Vreme', 'Radni Dani']])
        st.stop()

# --- RADNIČKO OKRUŽENJE ---
st.title("👷 Digitalna Prijava")
e_cookie = cookies.get("radnik_email")
p_ime = None
if e_cookie and not df_k.empty:
    match = df_k[df_k['Email'] == e_cookie]
    if not match.empty: p_ime = match.iloc[0]['Ime']

if not p_ime:
    st.subheader("Prijava")
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
                    dodaj_u_tabelu("korisnici", [i_in, e_in, 0])
                    cookies["radnik_email"] = e_in; cookies.save(); st.rerun()
else:
    status = "ODLAZAK"
    posl_g = None
    if not df_l.empty:
        r_logs = df_l[df_l['Radnik'] == p_ime]
        if not r_logs.empty:
            posl_red = r_logs.iloc[-1]
            status = posl_red['Akcija']; posl_g = posl_red['Gradiliste']

    st.markdown(f"<span class='label-radnik'>radnik:</span> <span class='ime-radnika'>{p_ime}</span>", unsafe_allow_html=True)
    if not df_g.empty:
        l_g = ["-- klikni ovde i izaberi gradilište --"] + df_g['Naziv'].tolist()
        def_idx = 0
        if posl_g in l_g: def_idx = l_g.index(posl_g)
        izbor = st.selectbox("🚩 gde se nalazite trenutno?", l_g, index=def_idx)
        if izbor == "-- klikni ovde i izaberi gradilište --": st.info("izaberite lokaciju.")
        st.write("---")
        v_sad = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        c1, c2 = st.columns(2)
        with c1:
            if izbor == "-- klikni ovde i izaberi gradilište --":
                st.markdown('<div class="onemoguceno-dugme"><button>IZBOR OBAVEZAN</button></div>', unsafe_allow_html=True)
            elif status == "ODLAZAK":
                st.markdown('<div class="trepcuce-dugme">', unsafe_allow_html=True)
                if st.button("✅ PRIJAVI SE NA POSAO"):
                    dodaj_u_tabelu("log", [p_ime, "DOLAZAK", izbor, v_sad])
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="blago-trepcuce-zeleno">', unsafe_allow_html=True)
                st.button("✅ PRIJAVLJENI STE", key="dis_pri")
