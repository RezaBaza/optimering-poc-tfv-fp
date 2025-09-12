# app.py - VERSION 3.4 MED SLUTGILTIG LOGISK STRUKTUR

import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model 
import math

# --- Sidans Konfiguration och Titel ---
st.set_page_config(layout="wide", page_title="Optimeringsmotor för Körprov")
st.title("PoC: Optimeringsmotor för Körprovsplanering")

st.markdown("""
Detta verktyg innehåller **två olika analysmetoder** för att planera körprovskapacitet:

1.  **Utjämning:** Fördela en befintlig total kapacitet så rättvist som möjligt för att jämna ut väntetiderna mellan orter.
2.  **Målvärdesanalys:** Beräkna exakt hur mycket kapacitet som krävs för att alla orter ska nå ett specifikt väntetidsmål.

Börja med att mata in nuvarande data för de orter som ska ingå i gruppen nedan.
""")

# --- FUNKTIONER (Definitioner först) ---

def solve_optimization(orter_data, total_kapacitet):
    # (Inga ändringar i denna funktion)
    for ort in orter_data:
        ort['K'] = ort['nuvarande_prov'] * ort['väntetid']
    total_K = sum(ort['K'] for ort in orter_data)
    w_bar = total_K / total_kapacitet if total_kapacitet > 0 else 0
    model = cp_model.CpModel()
    x_variabler = {}
    for ort in orter_data:
        x_variabler[ort['namn']] = model.NewIntVar(0, total_kapacitet, ort['namn'])
    model.Add(sum(x_variabler.values()) == total_kapacitet)
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
    if error_vars: model.Minimize(sum(error_vars))
    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        results = []
        for ort in orter_data:
            assigned_prov = solver.Value(x_variabler[ort['namn']])
            ny_väntetid = ort['K'] / assigned_prov if assigned_prov > 0 else 0
            results.append({'Ort': ort['namn'], 'Nuläge (Prov/v)': ort['nuvarande_prov'], 'Nuläge (Väntetid)': f"{ort['väntetid']:.1f} v", 'Föreslaget Prov/vecka': assigned_prov, 'Ny beräknad väntetid': f"{ny_väntetid:.1f} v"})
        return pd.DataFrame(results), w_bar
    else: return None, None

def calculate_target_wait(orter_data, target_wait):
    # (Inga ändringar i denna funktion)
    results = []
    needed_capacity = 0
    current_capacity = sum(ort['nuvarande_prov'] for ort in orter_data)
    for ort in orter_data:
        K = ort['nuvarande_prov'] * ort['väntetid']
        required_prov = math.ceil(K / target_wait) if target_wait > 0 else 0
        needed_capacity += required_prov
        results.append({'Ort': ort['namn'], 'Nuvarande Prov/vecka': ort['nuvarande_prov'], 'Nödvändig Prov/vecka': required_prov})
    totals = {'current': current_capacity, 'needed': needed_capacity, 'gap': needed_capacity - current_capacity}
    return pd.DataFrame(results), totals

# --- INDATA-SEKTION ---
if 'orter_data' not in st.session_state:
    st.session_state.orter_data = []

st.header("Steg 1: Mata in nuvarande data för gruppen")
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
        st.session_state.orter_data.append({'namn': ort_namn, 'nuvarande_prov': int(nuvarande_prov), 'väntetid': float(väntetid)})
        st.rerun()

if st.session_state.orter_data:
    st.subheader("Orter som ingår i beräkningen:")
    df_input = pd.DataFrame(st.session_state.orter_data)
    st.dataframe(df_input, use_container_width=True)
    if st.button("Rensa listan"):
        st.session_state.orter_data = []
        st.rerun()

    # --- FLIKAR FÖR DE TVÅ OLIKA VERKTYGEN ---
    st.header("Steg 2: Välj ett verktyg")
    tab1, tab2 = st.tabs(["📊 Verktyg 1: Utjämna Väntetider", "🎯 Verktyg 2: Målvärdesanalys"])

    # --- FLIK 1: UTJÄMNA VÄNTETIDER ---
    with tab1:
        st.subheader("Fördela en given kapacitet så rättvist som möjligt")
        
        with st.expander("Metodförklaring, fördelar och tekniska detaljer"):
            st.markdown("**Syfte:** Att fördela en fast, total kapacitet mellan orterna för att göra väntetiderna så lika som möjligt.")
            st.markdown("**Metod:** Vi använder en matematisk optimeringsmodell (Google OR-Tools CP-SAT Solver) för att hitta den fördelning som minimerar den totala skillnaden från en genomsnittlig väntetid.")
            st.latex(r'''\min \sum_{i=1}^{N} |K_i - \bar{W} \cdot x_i| \quad \text{under bivillkoret} \quad \sum_{i=1}^{N} x_i = C_{\text{total}}''')
            
            st.markdown("---")
            st.markdown("**Fördelar med denna metod:**")
            st.success("Hittar den matematiskt bevisat optimala och mest rättvisa fördelningen av den givna kapaciteten.")
            
            st.markdown("**Tekniska detaljer (Solver):**")
            st.info("Modellen använder **CP-SAT Solver** från Google OR-Tools. Den är vald för sin exceptionella förmåga att hantera problem med heltalsvariabler (som 'antal prov'), vilket garanterar en robust och pålitlig lösning.")

        # Indata för flik 1
        nuvarande_summa_tab1 = sum(ort['nuvarande_prov'] for ort in st.session_state.orter_data)
        total_kapacitet_tab1 = st.number_input(
            f"Ange gruppens totala kapacitet (nuvarande summa är {nuvarande_summa_tab1})",
            min_value=1, value=nuvarande_summa_tab1, key="utjamna_kapacitet_input")

        # Knapp och resultatvisning för flik 1
        if st.button("🚀 Optimera!", type="primary"):
            with st.spinner("Tänker... Optimeringsmotorn arbetar..."):
                results_df_tab1, w_bar = solve_optimization(st.session_state.orter_data, total_kapacitet_tab1)
            if results_df_tab1 is not None:
                st.success("Optimal fördelning hittad!")
                st.markdown(f"Målet var att nå en gemensam väntetid på cirka **{w_bar:.2f} veckor**.")
                st.dataframe(results_df_tab1, use_container_width=True)
            else:
                st.error("Kunde inte hitta en lösning. Kontrollera att den totala kapaciteten är tillräcklig.")

    # --- FLIK 2: NÅ EN MÅLVÄRDE-VÄNTETID ---
    with tab2:
        st.subheader("Beräkna vilken kapacitet som krävs för att nå ett mål")

        with st.expander("Metodförklaring och fördelar"):
            st.markdown("**Syfte:** Att beräkna exakt hur många prov varje ort måste erbjuda per vecka för att nå en specifik målvärde-väntetid.")
            st.markdown("**Metod:** Detta är en direkt beräkning, inte en optimering. Vi använder den grundläggande formeln för väntetid och löser ut den kapacitet som krävs.")
            st.latex(r''' \text{Nödvändig Kapacitet} (x_i) = \lceil \frac{\text{Kötryck} (K_i)}{\text{Målvärde Väntetid} (T)} \rceil ''')
            
            st.markdown("---")
            st.markdown("**Fördelar med denna metod:**")
            st.success("Ger ett konkret, datadrivet underlag för strategiska beslut genom att tydligt kvantifiera resursbehov och kapacitetsgap.")

        # Indata för flik 2
        target_wait_time = st.number_input("Ange målvärde för väntetid (veckor):", min_value=1.0, value=5.0, step=0.5, key="target_wait_input")
        
        # Knapp och resultatvisning för flik 2
        if st.button("Beräkna Behov"):
            results_df_tab2, totals = calculate_target_wait(st.session_state.orter_data, target_wait_time)
            st.success("Beräkning slutförd!")
            st.subheader("Resultat: Kapacitetsbehov per ort")
            st.dataframe(results_df_tab2, use_container_width=True)
            
            st.subheader("Sammanfattning: Totalt Kapacitetsgap")
            col_sum1, col_sum2, col_sum3 = st.columns(3)
            with col_sum1:
                st.metric(label="Nuvarande total kapacitet", value=f"{totals['current']:.0f}")
            with col_sum2:
                st.metric(label="Nödvändig total kapacitet", value=f"{totals['needed']:.0f}")
            with col_sum3:
                st.metric(label="Kapacitetsgap", value=f"{totals['gap']:.0f}", delta=f"{totals['gap']:.0f}")