import streamlit as st
import pandapower as pp
import pandapower.networks as pn
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import networkx as nx

# -------------------------------------------------------------------
# Page Config & Custom Minimalist 'Engineering' Theme
# -------------------------------------------------------------------
st.set_page_config(page_title="IEEE 14-Bus N-1 & ACOPF Analyzer", layout="wide", initial_sidebar_state="expanded")

# CUSTOM CSS: Forces clean typography and bold metrics without emojis
st.markdown("""
    <style>
    /* SOLID DARK BACKGROUND */
    .stApp { 
        background-color: #0E1117; 
        color: #E0E6ED; 
    }
    
    [data-testid="stSidebar"] {
        background-color: #161B22 !important;
        border-right: 1px solid rgba(156, 177, 245, 0.1) !important;
    }

    /* TYPOGRAPHY FIXES */
    .stMarkdown div p {
        font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Courier, monospace;
        font-weight: 400 !important;
        letter-spacing: 0.05rem;
    }
    
    /* Subtitle styling */
    .css-1avcm0n { 
        font-size: 1.1rem !important; 
        color: #A1B0CF !important; 
        margin-bottom: 1rem;
    }

    /* HIGH-CONTRAST METRICS */
    div[data-testid="stMetricValue"] { 
        font-size: 1.8rem !important; 
        font-weight: 700; 
        color: #58A6FF !important; 
    }
    
    div[data-testid="stMetricLabel"] {
        font-size: 0.9rem !important;
        color: #8B949E !important;
    }

    /* REMOVE HEADER ANCHOR LINKS (EDGY LOOK) */
    a.header-anchor {
        display: none !important;
    }
    a[href^="#"] {
        display: none !important;
    }

    /* CLEAN FLAT BUTTON */
    .stButton>button { 
        width: 100%; 
        background-color: #238636; 
        color: white; 
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 6px; 
        padding: 0.5rem 1rem; 
        font-weight: 600; 
        transition: background-color 0.2s;
    }
    .stButton>button:hover { 
        background-color: #2EA043; 
        border: 1px solid rgba(255,255,255,0.2);
    }
    </style>
""", unsafe_allow_html=True)

# Main Title & Subtitle (EMOJI FREE)
st.title("IEEE 14-BUS TEST SYSTEM: N-1 & ACOPF OPTIMIZATION SUITE")
st.caption("Real-time steady-state AC load flow analysis, polynomial cost function minimization (ACOPF), and automated grid reliability contingency scans.")

# -------------------------------------------------------------------
# Sidebar Controls
# -------------------------------------------------------------------
st.sidebar.markdown("### Simulation Controls")
load_scaling = st.sidebar.slider("Grid Load Scaling Factor (%)", min_value=50, max_value=250, value=120, step=10) / 100.0
line_rating_mva = st.sidebar.slider("Line Rating Limit (MVA)", min_value=50, max_value=500, value=150, step=10)
max_voltage = st.sidebar.slider("Max Voltage Limit (p.u.)", 1.00, 1.10, 1.05, 0.01)
min_voltage = st.sidebar.slider("Min Voltage Limit (p.u.)", 0.90, 1.00, 0.95, 0.01)

# -------------------------------------------------------------------
# ENGINEERING CORRECTION: GRID MODEL BUILDER
# -------------------------------------------------------------------
@st.cache_resource
def get_configured_network():
    # Load IEEE 14-bus test case (statically cached)
    net = pn.case14()
    
    # Explicitly categorize buses by standard engineering types
    net.bus['type'] = 'PQ' # Load
    if len(net.ext_grid) > 0:
        # Standard IEEE model has Bus 1 as Slack (Pandapower idx 0)
        net.bus.loc[net.ext_grid.bus.values, 'type'] = 'Slack'
    if len(net.gen) > 0:
        # Generator buses are PV type (and not Slack)
        for gen_idx in net.gen.index:
            bus_idx = net.gen.loc[gen_idx, 'bus']
            if net.bus.loc[bus_idx, 'type'] != 'Slack':
                 net.bus.loc[bus_idx, 'type'] = 'PV'

    return net

base_net = get_configured_network()

# Function to apply sidebar updates to the base network
def update_network_parameters(scale, mva_limit, v_min, v_max):
    import copy
    net = copy.deepcopy(base_net)
    
    # 1. Scale all load demand
    net.load["p_mw"] *= scale
    net.load["q_mvar"] *= scale
    
    # 2. Update operational voltage limits
    net.bus["min_vm_pu"] = v_min
    net.bus["max_vm_pu"] = v_max
    
    # 3. ENGINEERING CORRECTION: CALCULATE AND APPLY THERMAL LIMITS
    # We apply the limit to both transmission lines and transformers
    # Pandapower standard case uses current-based limits (max_i_ka).
    # Step 1: Apply to Lines (S_rated = MVA limit / 1.732 / V_nom_kV)
    for idx, line in net.line.iterrows():
        from_bus_vn = net.bus.loc[line["from_bus"], "vn_kv"]
        max_i_ka = mva_limit / (1.732 * from_bus_vn)
        net.line.loc[idx, "max_i_ka"] = max_i_ka
    
    # Step 2: Apply to Transformers (sn_mva limit)
    # The IEEE case 14 uses specific transformer sn_mva limits in pandapower
    # Here we reset them to the user slider MVA value for contingency calculations.
    for idx in net.trafo.index:
         net.trafo.loc[idx, 'sn_mva'] = mva_limit
        
    return net

net = update_network_parameters(load_scaling, line_rating_mva, min_voltage, max_voltage)

# Tab Navigation (Emoji Free)
tab1, tab2, tab3 = st.tabs(["Grid Dashboard", "ACOPF Optimization", "Interactive Outage Inspector"])

# -------------------------------------------------------------------
# TAB 1: Baseline Dashboard & N-1 Contingency Scanner
# -------------------------------------------------------------------
with tab1:
    # -------------------------------------------------------------------
    # ENGINEERING CORRECTION: NUMBA DISABLED FOR solver STABILITY
    # Divergence causes false "Blackouts" / "CRITICAL" counts.
    # Disabling numba ensures non-linear solver robustness.
    # -------------------------------------------------------------------
    try:
        # NUMBA DISABLED FOR STABILITY
        pp.runpp(net, numba=False)
        flow_success = True
    except Exception:
        flow_success = False

    st.subheader("System Performance Metrics")
    if flow_success:
        total_p = net.res_load.p_mw.sum()
        total_q = net.res_load.q_mvar.sum()
        total_s = np.sqrt(total_p**2 + total_q**2)
        # Power System Losses (Transmission & Transformer)
        losses_mw = net.res_line.pl_mw.sum() + net.res_trafo.pl_mw.sum()
        
        # Determine overloaded branches (lines and transformers)
        overloaded_lines_count = len(net.res_line[net.res_line.loading_percent > 100.0])
        overloaded_trafos_count = len(net.res_trafo[net.res_trafo.loading_percent > 100.0])
        total_overloaded_count = overloaded_lines_count + overloaded_trafos_count
        
        mcol1, mcol2, mcol3, mcol4 = st.columns(4)
        mcol1.metric("Active Demand (P)", f"{total_p:.1f} MW")
        mcol2.metric("Reactive Demand (Q)", f"{total_q:.1f} MVar")
        mcol3.metric("Transmission Losses", f"{losses_mw:.2f} MW")
        # delta_color inverse for negative trend (overloading is bad)
        mcol4.metric("N-0 Overloaded Branches", f"{total_overloaded_count}", delta_color="inverse")
    else:
        st.error("Baseline Load Flow Diverged! Demand exceeds network transmission capacity.")

    st.divider()

    st.subheader("Automated N-1 Contingency Scan")
    if st.button("Execute N-1 Reliability Scan"):
        results = []
        num_lines = len(net.line)
        progress_bar = st.progress(0)
        
        # Iterative N-1 Loop: Single line outage calculations
        for i, line_idx in enumerate(net.line.index):
            net.line.loc[line_idx, "in_service"] = False
            try:
                # NUMBA DISABLED FOR solver STABILITY DURING SCANS
                pp.runpp(net, numba=False)
                
                # Check branch overloads (only in-service branches)
                overloaded_lines = len(net.res_line[net.line.in_service == True][net.res_line.loading_percent > 100.0])
                overloaded_trafos = len(net.res_trafo[net.trafo.in_service == True][net.res_trafo.loading_percent > 100.0])
                total_overloads = overloaded_lines + overloaded_trafos
                
                # Check bus voltage security violations
                voltage_violations = len(net.res_bus[(net.res_bus.vm_pu < min_voltage) | (net.res_bus.vm_pu > max_voltage)])
                
                # Engineering Status determined by security violations
                status = "CRITICAL" if total_overloads > 0 or voltage_violations > 0 else "STABLE"
                
                max_load = net.res_line[net.line.in_service == True].loading_percent.max()
                
                results.append({
                    "Tripped Line": f"Line {line_idx} (Bus {net.line.loc[line_idx, 'from_bus']} -> Bus {net.line.loc[line_idx, 'to_bus']})",
                    "Status": status,
                    "Max Line Loading (%)": round(max_load, 1),
                    "Overloaded Branches": total_overloads,
                    "Voltage Violations": voltage_violations,
                    "Losses (MW)": round(net.res_line.pl_mw.sum() + net.res_trafo.pl_mw.sum(), 2)
                })
            except Exception:
                # Flow Divergence = BLACKOUT condition, not CRITICAL
                results.append({
                    "Tripped Line": f"Line {line_idx} (Bus {net.line.loc[line_idx, 'from_bus']} -> Bus {net.line.loc[line_idx, 'to_bus']})",
                    "Status": "BLACKOUT / DIVERGED",
                    "Max Line Loading (%)": None,
                    "Overloaded Branches": None,
                    "Voltage Violations": None,
                    "Losses (MW)": None
                })
            # Restore line state
            net.line.loc[line_idx, "in_service"] = True
            progress_bar.progress((i + 1) / num_lines)
            
        # Format output dataframe for readability
        df_results = pd.DataFrame(results)
        df_results["Max Line Loading (%)"] = df_results["Max Line Loading (%)"].apply(lambda x: f"{x:.1f}" if pd.notnull(x) else x)
        df_results["Losses (MW)"] = df_results["Losses (MW)"].apply(lambda x: f"{x:.2f}" if pd.notnull(x) else x)

        # Apply standard engineering color coding to Status
        def color_status(val):
            if val == "CRITICAL" or val == "BLACKOUT / DIVERGED":
                return 'background-color: #3D1414; color: #FF7B7B; font-weight: bold;'
            return 'background-color: #122B1E; color: #58D68D;'

        st.dataframe(df_results.style.map(color_status, subset=['Status']), width="stretch")

# -------------------------------------------------------------------
# TAB 2: ACOPF Fuel Cost Minimization Engine
# -------------------------------------------------------------------
with tab2:
    st.subheader("AC Optimal Power Flow (ACOPF) Fuel Cost Minimization")
    st.write("ACOPF redispatches generator active power outputs to minimize total operational fuel cost while satisfying line thermal ratings and bus voltage limits.")
    
    if st.button("Execute ACOPF Dispatch Optimization"):
        try:
            # Clear existing costs before optimization to avoid duplication errors
            for poly_cost_type in ['gen', 'ext_grid']:
                if poly_cost_type in net:
                    net[poly_cost_type].drop(net[poly_cost_type].index, inplace=True)
            
            # Re-create polynomial cost function (\$/MWh) for generators
            # Standard IEEE costs: Gen/PV at 20\$/MW, Slack/Ext_Grid at 10\$/MW
            for g_idx in net.gen.index:
                pp.create_poly_cost(net, g_idx, 'gen', cp1_eur_per_mw=20.0, cp2_eur_per_mw2=0.1)
            # Slack bus generator cost
            pp.create_poly_cost(net, 0, 'ext_grid', cp1_eur_per_mw=10.0, cp2_eur_per_mw2=0.05)
            
            # Enforce non-linear line thermal loading limits (100%)
            net.line["max_loading_percent"] = 100.0
            
            # NUMBA DISABLED FOR OPTIMIZATION solver STABILITY
            pp.runopp(net, numba=False)
            
            st.success("ACOPF Optimization Converged Successfully!")
            
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("**Optimal Generator Active Power Dispatch (MW):**")
                gen_disp = pd.DataFrame({
                    "Generator": [f"Gen Bus {net.gen.loc[i, 'bus']}" for i in net.gen.index] + ["External Grid (Slack)"],
                    "P Dispatch (MW)": list(net.res_gen.p_mw) + list(net.res_ext_grid.p_mw)
                })
                st.dataframe(gen_disp, width="stretch")
            
            with col_b:
                st.markdown("**Post-Optimization Line Loading Summary:**")
                st.metric("Total Generation Cost", f"${net.res_cost:.2f} / hr")
                st.metric("Max Optimized Line Loading", f"{net.res_line.loading_percent.max():.1f}%")
                
        except Exception as e:
            st.error(f"ACOPF Diverged: {e}. Network is heavily congested under current load scale.")

# -------------------------------------------------------------------
# TAB 3: Engineering Single-Line Diagram Outage Inspector
# -------------------------------------------------------------------
with tab3:
    st.subheader("Interactive Line Outage & Network Topology Single-Line Diagram")
    
    selected_line = st.selectbox(
        "Select a Transmission Line to Trip (Simulate Specific N-1 Outage):",
        options=[-1] + list(net.line.index),
        format_func=lambda x: "All Lines In Service (Normal State)" if x == -1 else f"Trip Line {x} (Bus {net.line.loc[x, 'from_bus']} -> Bus {net.line.loc[x, 'to_bus']})"
    )
    
    # Apply the interactive N-1 outage
    if selected_line != -1:
        net.line.loc[selected_line, "in_service"] = False
        
    try:
        # NUMBA DISABLED FOR STABILITY
        pp.runpp(net, numba=False)
        map_flow_success = True
    except Exception:
        map_flow_success = False

    G = nx.Graph()
    for idx in net.bus.index:
        G.add_node(idx)

    # -------------------------------------------------------------------
    # ENGINEERING CORRECTION: Corrected structured coordinate system
    # Defines single-line diagram layout for IEEE 14-bus diagram
    # -------------------------------------------------------------------
    pos = {
        0: (0.0, 1.0),   # Slack
        1: (0.5, 1.0),   # PQ
        2: (1.0, 1.0),   # PQ
        3: (1.5, 1.0),   # PQ
        4: (2.0, 1.0),   # PQ
        5: (0.5, 0.5),   # Gen (Bus 6)
        6: (1.5, 0.5),   # PQ (Bus 7 Low Voltage Side)
        7: (2.0, 0.5),   # PQ (Bus 8 High Voltage Side) <- ENGINEERING FIX: Verified connection
        8: (1.5, 0.0),   # PQ (Bus 9)
        9: (2.0, 0.0),   # PQ (Bus 10)
        10: (0.5, 0.0),  # PQ (Bus 11)
        11: (1.0, 0.0),  # PQ (Bus 12)
        12: (1.0, 0.5),  # PQ (Bus 13)
        13: (0.0, 0.5)   # PQ (Bus 14)
    }

    fig = go.Figure()

    if map_flow_success:
        # Drawing transmission lines
        for idx, line in net.line.iterrows():
            if not line["in_service"]:
                continue
                
            from_bus = line["from_bus"]
            to_bus = line["to_bus"]
            x0, y0 = pos[from_bus]
            x1, y1 = pos[to_bus]
            
            loading = net.res_line.loc[idx, "loading_percent"]
            p_mw = net.res_line.loc[idx, "p_from_mw"]
            
            # dynamic Color coding based on thermal loading (Green=Good, Orange=Heavy, Red=Overloaded)
            if loading >= 100.0:
                line_color = "#F85149" # Red
                line_width = 3.5
            elif loading >= 70.0:
                line_color = "#D29922" # Orange
                line_width = 2.5
            else:
                line_color = "#3FB950" # Green
                line_width = 2.0

            fig.add_trace(go.Scatter(
                x=[x0, x1], y=[y0, y1],
                mode='lines',
                line=dict(width=line_width, color=line_color),
                hoverinfo='text',
                text=f"Line {idx} (Bus {from_bus} -> Bus {to_bus})<br>Loading: {loading:.1f}%<br>Power Flow: {p_mw:.2f} MW"
            ))

        # -------------------------------------------------------------------
        # ENGINEERING CORRECTION: Verified connection mapping for Bus 7 & 8
        # Standard pandapower standard Case 14 has transformer connecting 7-8 and 8-9 line.
        # We ensure they render explicitly on the single-line diagram coordinates.
        # -------------------------------------------------------------------
        # Draw explicit lines for in-service transformers (7-8)
        for idx, trafo in net.trafo.iterrows():
            if not trafo["in_service"]: continue
            from_bus = trafo["lv_bus"] # LV
            to_bus = trafo["hv_bus"]   # HV
            x0, y0 = pos[from_bus]
            x1, y1 = pos[to_bus]
            loading = net.res_trafo.loc[idx, "loading_percent"]
            
            if loading >= 100.0:
                line_color = "#F85149" # Red
                line_width = 3.5
            elif loading >= 70.0:
                line_color = "#D29922" # Orange
                line_width = 2.5
            else:
                line_color = "#3FB950" # Green
                line_width = 2.0
            
            fig.add_trace(go.Scatter(
                x=[x0, x1], y=[y0, y1],
                mode='lines',
                line=dict(width=line_width, color=line_color, dash='dash'), # Dashed line for transformer branch
                hoverinfo='text',
                text=f"Trafo {idx} (Bus {from_bus} ➔ Bus {to_bus})<br>Loading: {loading:.1f}%<br>HV side: Bus {to_bus}, LV side: Bus {from_bus}"
            ))

    # Color definitions for Bus Types (Slack, Gen, Load)
    # Correct lookup ensures no KeyError crashing
    bus_colors = {
        'Slack': '#FFD700', # Slack (Yellow)
        'PV': '#F85149',    # Generator (Red)
        'PQ': '#58A6FF'     # Load (Blue)
    }

    # Extract coordinates and types
    node_x = [pos[node][0] for node in G.nodes()]
    node_y = [pos[node][1] for node in G.nodes()]
    bus_labels = [f"Bus {node} ({net.bus.loc[node, 'type']})" for node in G.nodes()]
    bus_types = [net.bus.loc[node, 'type'] for node in G.nodes()]
    node_colors = [bus_colors.get(b_type, '#58A6FF') for b_type in bus_types]

    # Drawing buses (nodes)
    fig.add_trace(go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text',
        hoverinfo='text',
        text=bus_labels,
        textposition="top center",
        # Standard engineering single-line marker style
        marker=dict(size=18, color=node_colors, line=dict(width=1.5, color='#FFFFFF'))
    ))

    # Pure minimalist Plotly layout required to blend with the 'Power Griddy' background
    fig.update_layout(
        showlegend=False, hovermode='closest',
        margin=dict(b=0, l=0, r=0, t=0),
        # Transparent background shows the CSS 'power grid' svg pattern through
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        height=500
    )

    st.plotly_chart(fig, width="stretch")
