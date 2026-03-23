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

# --- POVEZIVANJE SA GOOGLE SHEETS ---
def povezi_tabelu():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client.open("Baza Gradiliste")
    except Exception as e:
        st.error(f"Greška pri povezivanju: {e}")
        return None

def ucitaj_podatke(sheet_name):
    sh = povezi_tabelu()
    if sh:
        try:
            return pd.DataFrame(sh.worksheet(sheet_name).get_all_records())
        except:
            return pd.DataFrame()
    return pd.DataFrame()

def dodaj_u_tabelu(sheet_name, red):
    sh = povezi_tabelu()
    if sh:
        sh.worksheet(sheet_name).append_row(red)

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

# --- FUNKCIJA ZA LOGIKU OBRAČUNA ---
def obracunaj_sate(df):
    if df.empty or 'Vreme' not in df.columns:
        return pd.DataFrame()
    
    # Konverzija vremena u Python objekte
    df['Vreme_DT'] = pd.to_datetime(df['Vreme'], format="%d.%m.%Y %H:%M:%S", errors='coerce')
    df = df.dropna(subset=['Vreme_DT'])
    df = df.sort_values(['Radnik', 'Vreme_DT'])
    
    obracun = []
    for radnik in df['Radnik'].unique():
        radnik_data = df[df['Radnik'] == radnik]
        dolazak_vreme = None
        
        for _, row in radnik_data.iterrows():
            if row['Akcija'] == "DOLAZAK":
                dolazak_vreme = row['Vreme_DT']
            elif row['Akcija'] == "ODLAZAK" and dolazak_vreme is not None:
                razlika_sekundi = (row['Vreme_DT'] - dolazak_vreme).total_seconds()
                # Ako je razlika negativna (greška u unosu), preskoči
                if razlika_sekundi > 0:
                    mesec = dolazak_vreme.strftime("%m-%Y")
                    obracun.append([radnik, mesec, razlika_sekundi])
                dolazak_vreme = None
                
    return pd.DataFrame(obracun, columns=["Radnik", "Mesec", "Sekunde"])

# --- KOLAČIĆI ---
cookies = EncryptedCookieManager(password="neka_veoma_tajna_sifra_123")
if not cookies.ready(): st.stop()

# --- ADMIN LOGIKA ---
st.sidebar.title("🔐 Admin")
admin_lozinka = st.sidebar.text_input("Lozinka:", type="password")
prikazi_dashboard = False

if admin_lozinka == "admin":
    st.sidebar.success("✅ Admin pristup")
    prikazi_dashboard = st.sidebar.checkbox("Prikaži Admin Dashboard")

# --- PRIKAZ: ILI ADMIN ILI RADNIK ---
if prikazi_dashboard:
    # ------------------ ADMIN OKRUŽENJE ------------------
    st.header("📊 Admin Kontrola")
    t1, t2, t3, t4 = st.tabs(["🕒 Dnevnik", "👥 Radnici", "⏱️ Sati", "🏗️ Gradilišta"])
    
    df_l = ucitaj_podatke("log")
    
    with t1:
        if not df_l.empty:
            st.dataframe(df_l.iloc[::-1], use_container_width=True)
        else:
            st.info("Dnevnik je prazan.")
            
    with t4:
        st.subheader("Gradilišta")
        novo = st.text_input("Novo gradilište:")
        if st.button("Dodaj gradilište"):
            if novo:
                dodaj_u_tabelu("gradilista", [novo])
                st.rerun()
        st.dataframe(ucitaj_podatke("gradilista"), use_container_width=True)
        
    with t2:
        st.dataframe(ucitaj_podatke("korisnici"), use_container_width=True)
        
    with t3:
        st.subheader("Obračun radnog vremena")
        if not df_l.empty:
            res = obracunaj_sate(df_l)
            if not res.empty:
                # Filter po mesecu
                svi_meseci = res['Mesec'].unique()
                izabrani_mesec = st.selectbox("Izaberi mesec za obračun:", svi_meseci)
                
                # Grupisanje i sumiranje sekundi za izabrani mesec
                mesecni_df = res[res['Mesec'] == izabrani_mesec]
                finalni = mesecni_df.groupby('Radnik')['Sekunde'].sum().reset_index()
                
                # Pretvaranje sekundi u format SS:MM:ss
                finalni['Ukupno Vreme'] = finalni['Sekunde'].apply(format_u_hms)
                
                # Prikaz tabele
                st.table(finalni[['Radnik', 'Ukupno Vreme']])
                
                # Opcija za preuzimanje
                csv = finalni[['Radnik', 'Ukupno Vreme']].to_csv(index=False).encode('utf-8')
                st.download_button("📥 Preuzmi ovaj obračun", csv, f"obracun_{izabrani_mesec}.csv", "text/csv")
            else:
                st.warning("Nema dovoljno podataka (parova Prijava-Odjava) za obračun.")
        else:
            st.info("Dnevnik je prazan, nema podataka za obračun.")

else:
    # ------------------ RADNIČKO OKRUŽENJE ------------------
    st.title("👷 Digitalna Prijava")
    
    email_cookie = cookies.get("radnik_email")
    df_korisnici = ucitaj_podatke("korisnici")
    prijavljeno_ime = None

    if email_cookie and not df_korisnici.empty:
        match = df_korisnici[df_korisnici['Email'] == email_cookie]
        if not match.empty: 
            prijavljeno_ime = match.iloc[0]['Ime']

    if not prijavljeno_ime:
        st.subheader("Registracija / Prijava")
        email_in = st.text_input("Email:").strip().lower()
        if email_in:
            postoji = False
            if not df_korisnici.empty and 'Email' in df_korisnici.columns:
                match = df_korisnici[df_korisnici['Email'] == email_in]
                if not match.empty:
                    postoji = True
                    if st.button(f"Prijavi me kao {match.iloc[0]['Ime']}"):
                        cookies["radnik_email"] = email_in
                        cookies.save(); st.rerun()
            if not postoji:
                ime_in = st.text_input("Ime i Prezime:")
                if st.button("Registruj me"):
                    if ime_in and email_in:
                        dodaj_u_tabelu("korisnici", [ime_in, email_in])
                        cookies["radnik_email"] = email_in
                        cookies.save(); st.rerun()
    else:
        status = dobij_poslednji_status(prijavljeno_ime)
        st.write(f"### Radnik: **{prijavljeno_ime}**")
        
        df_g = ucitaj_podatke("gradilista")
        if not df_g.empty:
            gradilista = df_g['Naziv'].tolist()
            izbor = st.selectbox("Izaberi gradilište:", gradilista)
            
            st.write("---")
            vreme_sad = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
            col1, col2 = st.columns(2)
            
            with col1:
                if status == "ODLAZAK":
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
