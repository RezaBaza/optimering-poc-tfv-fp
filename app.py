# app.py - SLUTGILTIG VERSION

import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model 

# --- Sidans Konfiguration och Titel ---
st.set_page_config(layout="wide", page_title="Optimeringsmotor för Körprov")

st.title("PoC: Optimeringsmotor för Körprovsplanering")
st.markdown("""
Detta verktyg hjälper till att fördela provkapacitet för att jämna ut väntetiderna mellan olika orter.
Börja med att mata in nuvarande data för de orter som ska ingå i gruppen.
""")

# === NY DEL: FÖRKLARING AV MODELLEN ===

with st.expander("Klicka här för att läsa om modellen och dess för- och nackdelar"):
    st.subheader("Hur fungerar optimeringen?")
    st.markdown("""
    Tänk dig att du har en kanna med vatten (**total kapacitet**) som ska fördelas mellan flera törstiga plantor (**orter**). Vissa är väldigt torra (**lång väntetid**) och andra är nästan nöjda.

    Modellen använder en matematisk metod som kallas **Linjär Optimering** för att hitta det absolut bästa sättet att fördela vattnet så att alla plantor blir **så lika nöjda som möjligt** (får en så jämn väntetid som möjligt). Den gör detta genom att följa tre principer:

    1.  **Mål:** Minimera den totala "ojämlikheten" i väntetid mellan orterna.
    2.  **Beslut:** Bestämma det exakta antalet prov (`x`) som varje ort ska tilldelas.
    3.  **Regler:** Aldrig överskrida den totala kapaciteten för gruppen.

    Resultatet är inte en "bra gissning", utan den matematiskt bevisat bästa lösningen givet indatan.
    """)

    st.subheader("Fördelar vs. Nackdelar & Begränsningar")
    col1, col2 = st.columns(2)

    with col1:
        st.success("Fördelar 👍")
        st.markdown("""
        *   **Optimal & Rättvis:** Hittar den matematiskt bästa och mest rättvisa fördelningen.
        *   **Datadriven:** Besluten baseras på verklig data, inte magkänsla.
        *   **Snabb & Skalbar:** Kan lösa problemet lika enkelt för 3 orter som för 300.
        *   **Transparent:** Reglerna är tydliga och resultatet är spårbart.
        """)

    with col2:
        st.warning("Nackdelar & Begränsningar ⚠️")
        st.markdown("""
        *   **"Skräp in, skräp ut":** Resultatet är helt beroende av att indatan (väntetider, kapacitet) är korrekt.
        *   **Förenklad världsbild:** Modellen känner inte till lokala förutsättningar (sjukdom, semester, vägarbeten) om vi inte matar in dem som nya regler.
        *   **Fokuserar på ett enda mål:** Just nu är målet *endast* att jämna ut väntetider. Den tar inte hänsyn till t.ex. resekostnader för personal eller andra affärsmål.
        """)


# --- DEL 2: INDATA-SEKTION ---
if 'orter_data' not in st.session_state:
    st.session_state.orter_data = []

st.header("Steg 1: Lägg till orter i gruppen")

col1, col2, col3 = st.columns(3)

with col1:
    ort_namn = st.text_input("Namn på ort")
with col2:
    nuvarande_prov = st.number_input("Nuvarande prov/vecka", min_value=0, step=1)
with col3:
    väntetid = st.number_input("Nuvarande väntetid (veckor)", min_value=0.0, step=0.5, format="%.1f")

if st.button("Lägg till ort"):
    if not ort_namn:
        st.warning("Vänligen ange ett namn på orten.")
    else:
        st.session_state.orter_data.append({
            'namn': ort_namn,
            'nuvarande_prov': int(nuvarande_prov),
            'väntetid': float(väntetid)
        })
        st.rerun() # Ladda om för att rensa fälten

# --- DEL 3: VISA INMATAD DATA ---
if st.session_state.orter_data:
    st.subheader("Orter som ingår i optimeringen:")
    df_input = pd.DataFrame(st.session_state.orter_data)
    st.dataframe(df_input, use_container_width=True)

    if st.button("Rensa listan"):
        st.session_state.orter_data = []
        st.rerun()

# --- NY DEL: OPTIMERINGS-SEKTION ---

def solve_optimization(orter_data, total_kapacitet):
    """
    Kärnan i appen. Tar in listan med orter och total kapacitet,
    kör optimeringen och returnerar en resultattabell.
    """
    for ort in orter_data:
        ort['K'] = ort['nuvarande_prov'] * ort['väntetid']
    total_K = sum(ort['K'] for ort in orter_data)
    w_bar = total_K / total_kapacitet if total_kapacitet > 0 else 0

    model = cp_model.CpModel()
    x_variabler = {}
    for ort in orter_data:
        x_variabler[ort['namn']] = model.NewIntVar(0, total_kapacitet, ort['namn'])
    
    # Bivillkor: Tvinga modellen att använda all tillgänglig kapacitet
    model.Add(sum(x_variabler.values()) == total_kapacitet)

    # Robust målfunktion (v3.0 från Colab)
    PRECISION_FAKTOR = 100
    w_bar_int = int(w_bar * PRECISION_FAKTOR)
    error_vars = []
    for ort in orter_data:
        x = x_variabler[ort['namn']]
        K_int = int(ort['K'] * PRECISION_FAKTOR)
        max_error = int(total_K * PRECISION_FAKTOR)
        error = model.NewIntVar(-max_error, max_error, f"error_{ort['namn']}")
        model.Add(error == K_int - w_bar_int * x)
        abs_error = model.NewIntVar(0, max_error, f"abs_error_{ort['namn']}")
        model.AddAbsEquality(abs_error, error)
        error_vars.append(abs_error)

    if error_vars:
        model.Minimize(sum(error_vars))

    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        results = []
        for ort in orter_data:
            assigned_prov = solver.Value(x_variabler[ort['namn']])
            ny_väntetid = ort['K'] / assigned_prov if assigned_prov > 0 else 0
            results.append({
                'Ort': ort['namn'],
                'Nuläge (Prov/v)': ort['nuvarande_prov'],
                'Nuläge (Väntetid)': f"{ort['väntetid']:.1f} v",
                'Föreslaget Prov/vecka': assigned_prov,
                'Ny beräknad väntetid': f"{ny_väntetid:.1f} v"
            })
        return pd.DataFrame(results), w_bar
    else:
        return None, None

# Visa bara optimeringsknappen om vi har minst en ort i listan
if st.session_state.orter_data:
    st.header("Steg 2: Ange total kapacitet och optimera")

    # Beräkna och föreslå total kapacitet baserat på inmatad data
    nuvarande_summa = sum(ort['nuvarande_prov'] for ort in st.session_state.orter_data)
    
    total_kapacitet = st.number_input(
        f"Ange gruppens totala kapacitet (nuvarande summa är {nuvarande_summa})",
        min_value=1,
        value=nuvarande_summa
    )

    # Den stora optimeringsknappen
    if st.button("🚀 Optimera!", type="primary"):
        # Visa en "spinner" medan beräkningen pågår
        with st.spinner("Tänker... Optimeringsmotorn arbetar..."):
            results_df, w_bar = solve_optimization(st.session_state.orter_data, total_kapacitet)
        
        if results_df is not None:
            st.success("Optimal fördelning hittad!")
            st.subheader("Resultat")
            st.markdown(f"Målet var att nå en gemensam väntetid på cirka **{w_bar:.2f} veckor**.")
            st.dataframe(results_df, use_container_width=True)
            st.markdown(f"**Kontroll:** Totalt tilldelad kapacitet är **{results_df['Föreslaget Prov/vecka'].sum()}** av **{total_kapacitet}**.")
        else:
            st.error("Kunde inte hitta en lösning. Kontrollera att den totala kapaciteten är tillräcklig.")