import streamlit as st
import pandas as pd
import cloudscraper
from bs4 import BeautifulSoup
import concurrent.futures
import requests

# --- 1. KONFIGURATION ---
# Deine Firebase URL (mit angehängtem /steammachine.json für den Datenzugriff)
FIREBASE_URL = "https://geizhalslisten-81b9d-default-rtdb.europe-west1.firebasedatabase.app/steammachine.json"
EDIT_PIN = "1234"  # Deine PIN für den Bearbeitungsmodus

# --- 2. DATENBANK LOGIK ---
def load_data():
    try:
        res = requests.get(FIREBASE_URL)
        if res.status_code == 200 and res.json():
            return res.json()
    except:
        pass
    # Leere Startvorlage, falls die Datenbank noch ganz leer ist
    return {"Konfig_A": [], "Konfig_B": []}

def save_data(data):
    requests.put(FIREBASE_URL, json=data)

data = load_data()

# --- 3. STEAM DESIGN (CSS) ---
st.set_page_config(page_title="DIY Steam Machine", page_icon="🎮", layout="wide")
st.markdown("""
    <style>
    .stApp { background-color: #1b2838; color: #c7d5e0; }
    h1, h2, h3 { color: #66c0f4 !important; font-family: sans-serif; }
    div[data-testid="stVerticalBlock"] > div[style*="flex-direction: column;"] {
        background-color: #171a21; padding: 20px; border-radius: 6px; box-shadow: 0 4px 8px rgba(0,0,0,0.3);
    }
    div[data-testid="stMetricValue"] { color: #a3cc27 !important; font-size: 2.5rem !important; font-weight: bold; }
    .steam-table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 14px;}
    .steam-table th { background-color: #101214; color: #66c0f4; text-align: left; padding: 10px; border-bottom: 2px solid #2a475e; }
    .steam-table td { padding: 10px; border-bottom: 1px solid #2a475e; color: #8f98a0; }
    .steam-table a { color: #66c0f4; text-decoration: none; }
    </style>
""", unsafe_allow_html=True)

# --- 4. PREIS SCRAPER ---
@st.cache_data(ttl=1800)
def fetch_price(url):
    if not isinstance(url, str) or "geizhals" not in url: return 0.0
    try:
        scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
        html = scraper.get(url, timeout=8).text
        price_span = BeautifulSoup(html, 'html.parser').find('span', class_='gh_g_price')
        if price_span: return float(price_span.text.replace('€', '').replace('.', '').replace(',', '.').strip())
    except: pass
    return 0.0

def get_all_prices(urls):
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        return list(executor.map(fetch_price, urls))

# --- 5. BENUTZEROBERFLÄCHE ---
st.title("🎮 DIY Steam Machine")
st.markdown("Live-Preisverfolgung über Geizhals.")

with st.sidebar:
    st.header("⚙️ Verwaltung")
    pin_input = st.text_input("PIN eingeben für Bearbeitungsmodus", type="password")
    edit_mode = (pin_input == EDIT_PIN)
    if pin_input and not edit_mode:
        st.error("Falsche PIN")

if edit_mode:
    st.success("Bearbeitungsmodus aktiv. Die Daten werden in Firebase gespeichert.")
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Konfiguration A**")
        df_a = pd.DataFrame(data["Konfig_A"]) if data["Konfig_A"] else pd.DataFrame(columns=["Komponente", "Bezeichnung", "Link"])
        edited_a = st.data_editor(df_a, num_rows="dynamic", key="edit_a")
        
    with col2:
        st.write("**Konfiguration B**")
        df_b = pd.DataFrame(data["Konfig_B"]) if data["Konfig_B"] else pd.DataFrame(columns=["Komponente", "Bezeichnung", "Link"])
        edited_b = st.data_editor(df_b, num_rows="dynamic", key="edit_b")
        
    if st.button("💾 Speichern & Live schalten"):
        data["Konfig_A"] = edited_a.to_dict('records')
        data["Konfig_B"] = edited_b.to_dict('records')
        save_data(data)
        st.cache_data.clear()
        st.success("Gespeichert! Lösche die PIN links aus dem Feld, um die fertige Seite zu sehen.")

else:
    col1, col2 = st.columns(2)
    for col, conf_key, title in zip([col1, col2], ["Konfig_A", "Konfig_B"], ["Konfiguration A", "Konfiguration B"]):
        with col:
            st.header(title)
            df = pd.DataFrame(data[conf_key])
            if not df.empty and "Link" in df.columns:
                urls = df["Link"].tolist()
                with st.spinner("Lade Preise..."):
                    prices = get_all_prices(urls)
                
                df['Preis (€)'] = [f"{p:.2f} €" if p > 0 else "-" for p in prices]
                df['Link'] = df['Link'].apply(lambda x: f'<a href="{x}" target="_blank">Geizhals ↗</a>' if pd.notna(x) and x else "")
                
                st.markdown(df.to_html(index=False, escape=False, classes="steam-table"), unsafe_allow_html=True)
                st.metric(label="Gesamtpreis (Live)", value=f"{sum(prices):.2f} €")
            else:
                st.info("Noch keine Hardware hinterlegt. PIN eingeben, um zu starten.")
