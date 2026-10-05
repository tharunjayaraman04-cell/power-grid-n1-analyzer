import streamlit as st
import pandapower as pp
import pandapower.networks as pn
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import networkx as nx

# -------------------------------------------------------------------
# Page Config & Pure Minimalist Theme
# -------------------------------------------------------------------
st.set_page_config(page_title="Power Grid N-1 & ACOPF Analyzer", layout="wide", initial_sidebar_state="expanded")

# Custom CSS for dark minimalist theme and typography
st.markdown("""
    <style>
    /* SOLID DARK BACKGROUND */
    .stApp { 
        background-color: #0D1117; 
        color: #C9D1D9; 
    }
    
    [data-testid="stSidebar"] {
        background-color: #161B22 !important;
        border-right: 1px solid #30363D !important;
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
        color: #E6EDF3 !important; 
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

    /* REMOVE HEADER ANCHOR LINKS */
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
        color: #FFFFFF; 
        border: 1px solid #2EA043;
        border-radius: 6px; 
        padding: 0.5rem 1rem; 
        font-weight: 600; 
    }
    .stButton>button:hover { 
        background-color: #2EA043; 
    }
    </style>
""", unsafe_allow_html=True)

# Main Title & Subtitle
st.title("Power Grid N-1 Contingency & ACOPF Optimization Suite")
st.caption("Real-time steady-state AC load flow, ACOPF cost optimization dispatch, and interactive N-1 reliability analyzer.")

# Engineering Data Callout
st.write("**SYSTEM: IEEE 14-BUS TEST CASE | SYSTEM BASE MVA: 100**")

# -------------------------------------------------------------------
# Sidebar Controls
# -------------------------------------------------------------------
st.sidebar.markdown("### Simulation Controls")
load_scaling = st.sidebar.slider("Grid Load Scaling Factor (%)", min_value=50, max_value=250, value=120, step=10) / 100.0
line_rating_mva = st.sidebar.slider("Line Rating Limit (MVA)", min_value=50, max_value=500, value=150, step=10)
max_voltage = st.sidebar.slider("Max Voltage Limit (p.u.)", 1.00, 1.10, 1.05, 0.01)
min_voltage = st.sidebar.slider("Min Voltage Limit (p.u.)", 0.90, 1.00, 0.95, 0.01)

# -------------------------------------------------------------------
# Grid Model Builder
# -------------------------------------------------------------------
@st.cache_resource
def get_configured_network():
    net = pn.case14()
    # Explicitly map engineering bus categories (Slack, PV, PQ)
    net.bus['category'] = 'PQ'
    if len(net.ext_grid) > 0:
        net.bus.loc[net.ext_grid.bus.values, 'category'] = 'SL'
    if len(net.gen) > 0:
        net.bus.loc[net.gen.bus.values, 'category'] = 'PV'
    return net

base_net = get_configured_network()

def update_network_parameters(scale, mva_limit, v_min, v_max):
    import copy
    net = copy.deepcopy(base_net)
    
    # Scale demand
    net.load["p_mw"] *= scale
    net.load["q_mvar"] *= scale
    
    # Operational voltage boundaries
    net.bus["min_vm_pu"] = v_min
    net.bus["max_vm_pu"] = v_max
    
    # Convert MVA rating limit to max current capacity (kA) per bus voltage level
    for idx, line in net.line.iterrows():
        from_bus_vn = net.bus.loc[line["from_bus"], "vn_kv"]
        max_i_ka = mva_limit / (1.732 * from_bus_vn)
        net.line.loc[idx, "max_i_ka"] = max_i_ka
        
    return net

net = update_network_parameters(load_scaling, line_rating_mva, min_voltage, max_voltage)

# Tab Navigation
tab1, tab2, tab3 = st.tabs(["Grid Dashboard", "ACOPF Optimization", "Interactive Outage Inspector"])

# -------------------------------------------------------------------
# TAB 1: Grid Dashboard & Automatic N-1 Scan
# -------------------------------------------------------------------
with tab1:
    try:
        pp.runpp(net, numba=False)
        flow_success = True
    except Exception:
        flow_success = False

    st.subheader("System Performance Metrics")
    if flow_success:
        total_p = net.res_load.p_mw.sum()
        total_q = net.res_load.q_mvar.sum()
        total_s = np.sqrt(total_p**2 + total_q**2)
        losses_mw = net.res_line.pl_mw.sum()
        in_service_lines = net.line[net.line.in_service == True].index
        overloaded_lines_count = len(net.res_line.loc[in_service_lines][net.res_line.loc[in_service_lines].loading_percent > 100.0])
        
        mcol1, mcol2, mcol3, mcol4 = st.columns(4)
        mcol1.metric("Active Demand (P)", f"{total_p:.1f} MW")
        mcol2.metric("Reactive Demand (Q)", f"{total_q:.1f} MVar")
        mcol3.metric("Transmission Losses", f"{losses_mw:.2f} MW")
        mcol4.metric("N-0 Overloaded Lines", f"{overloaded_lines_count}", delta_color="inverse")
    else:
        st.error("Baseline Load Flow Diverged! Demand exceeds network transmission capacity.")

    st.divider()

    st.subheader("Automated N-1 Contingency Scan")
    
    # AUTO-RUN: Executes automatically on page load without requiring button press
    results = []
    num_lines = len(net.line)
    
    for i, line_idx in enumerate(net.line.index):
        net.line.loc[line_idx, "in_service"] = False
        try:
            pp.runpp(net, numba=False)
            active_lines = net.line[net.line.in_service == True].index
            max_load = net.res_line.loc[active_lines].loading_percent.max()
            overloads = len(net.res_line.loc[active_lines][net.res_line.loc[active_lines].loading_percent > 100.0])
            v_violations = len(net.res_bus[(net.res_bus.vm_pu < min_voltage) | (net.res_bus.vm_pu > max_voltage)])
            status = "CRITICAL" if overloads > 0 or v_violations > 0 else "STABLE"
            
            results.append({
                "Tripped Line": f"Line {line_idx} (Bus {net.line.loc[line_idx, 'from_bus']+1} -> Bus {net.line.loc[line_idx, 'to_bus']+1})",
                "Status": status,
                "Max Line Loading (%)": round(max_load, 1),
                "Overloaded Lines": overloads,
                "Voltage Violations": v_violations,
                "Losses (MW)": round(net.res_line.pl_mw.sum(), 2)
            })
        except Exception:
            results.append({
                "Tripped Line": f"Line {line_idx} (Bus {net.line.loc[line_idx, 'from_bus']+1} -> Bus {net.line.loc[line_idx, 'to_bus']+1})",
                "Status": "BLACKOUT / DIVERGED",
                "Max Line Loading (%)": None,
                "Overloaded Lines": None,
                "Voltage Violations": None,
                "Losses (MW)": None
            })
        net.line.loc[line_idx, "in_service"] = True
        
    df_results = pd.DataFrame(results)
    df_results["Max Line Loading (%)"] = df_results["Max Line Loading (%)"].apply(lambda x: f"{x:.1f}" if pd.notnull(x) else x)
    df_results["Losses (MW)"] = df_results["Losses (MW)"].apply(lambda x: f"{x:.2f}" if pd.notnull(x) else x)

    def color_status(val):
        if val == "CRITICAL" or val == "BLACKOUT / DIVERGED":
            return 'background-color: #3D1414; color: #FF7B7B; font-weight: bold;'
        return 'background-color: #122B1E; color: #58D68D;'

    st.dataframe(df_results.style.map(color_status, subset=['Status']), width="stretch")

# -------------------------------------------------------------------
# TAB 2: ACOPF Cost Minimization Engine
# -------------------------------------------------------------------
with tab2:
    st.subheader("AC Optimal Power Flow (ACOPF) Fuel Cost Minimization")
    st.write("ACOPF redispatches generator active power outputs to minimize operational fuel cost while satisfying line thermal ratings and bus voltage limits.")
    
    # AUTO-RUN: Executes automatically on page load without requiring button press
    try:
        for poly_cost_type in ['gen', 'ext_grid']:
            if poly_cost_type in net:
                net[poly_cost_type].drop(net[poly_cost_type].index, inplace=True)
        
        for g_idx in net.gen.index:
            pp.create_poly_cost(net, g_idx, 'gen', cp1_eur_per_mw=20.0, cp2_eur_per_mw2=0.1)
        pp.create_poly_cost(net, 0, 'ext_grid', cp1_eur_per_mw=10.0, cp2_eur_per_mw2=0.05)
        
        net.line["max_loading_percent"] = 100.0
        pp.runopp(net)
        
        st.success("ACOPF Optimization Converged Successfully!")
        
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**Optimal Generator Active Power Dispatch (MW):**")
            gen_disp = pd.DataFrame({
                "Generator": [f"Gen Bus {net.gen.loc[i, 'bus']+1}" for i in net.gen.index] + ["External Grid (Slack)"],
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
# TAB 3: Interactive Single-Line Diagram Outage Inspector
# -------------------------------------------------------------------
with tab3:
    st.subheader("Interactive Line Outage & Structured Single-Line Diagram")
    
    selected_line = st.selectbox(
        "Select a Transmission Line to Trip (Simulate Specific N-1 Outage):",
        options=[-1] + list(net.line.index),
        format_func=lambda x: "All Lines In Service (Normal State)" if x == -1 else f"Trip Line {x} (Bus {net.line.loc[x, 'from_bus']+1} -> Bus {net.line.loc[x, 'to_bus']+1})"
    )
    
    if selected_line != -1:
        net.line.loc[selected_line, "in_service"] = False
        
    try:
        pp.runpp(net, numba=False)
        map_flow_success = True
    except Exception:
        map_flow_success = False

    G = nx.Graph()
    for idx in net.bus.index:
        G.add_node(idx)

    # Coordinates for IEEE 14-bus single-line diagram layout
    pos = {
        0: (0.0, 1.0),   # Slack (Bus 1)
        1: (0.5, 1.0),   # Bus 2
        2: (1.0, 1.0),   # Bus 3
        3: (1.5, 1.0),   # Bus 4
        4: (2.0, 1.0),   # Bus 5
        5: (0.5, 0.5),   # Bus 6
        6: (1.5, 0.5),   # Bus 7
        7: (2.0, 0.5),   # Bus 8
        8: (1.5, 0.0),   # Bus 9
        9: (2.0, 0.0),   # Bus 10
        10: (0.5, 0.0),  # Bus 11
        11: (1.0, 0.0),  # Bus 12
        12: (1.0, 0.5),  # Bus 13
        13: (0.0, 0.5)   # Bus 14
    }

    fig = go.Figure()

    # FIX 1: ALWAYS RENDER TRANSMISSION LINE EDGES
    for idx, line in net.line.iterrows():
        if not line["in_service"]:
            continue
            
        from_bus = line["from_bus"]
        to_bus = line["to_bus"]
        x0, y0 = pos[from_bus]
        x1, y1 = pos[to_bus]
        
        if map_flow_success:
            loading = net.res_line.loc[idx, "loading_percent"]
            p_mw = net.res_line.loc[idx, "p_from_mw"]
            
            if loading >= 100.0:
                line_color = "#F85149"
                line_width = 3.5
            elif loading >= 70.0:
                line_color = "#D29922"
                line_width = 2.5
            else:
                line_color = "#3FB950"
                line_width = 2.0
            hover_text = f"Line {idx} (Bus {from_bus+1} -> Bus {to_bus+1})<br>Loading: {loading:.1f}%<br>Power Flow: {p_mw:.2f} MW"
        else:
            line_color = "#8B949E"
            line_width = 2.0
            hover_text = f"Line {idx} (Bus {from_bus+1} -> Bus {to_bus+1})<br>Status: Out of Service / Diverged"

        fig.add_trace(go.Scatter(
            x=[x0, x1], y=[y0, y1],
            mode='lines',
            line=dict(width=line_width, color=line_color),
            hoverinfo='text',
            text=hover_text
        ))

    # Bus Color mappings
    bus_colors = {
        'SL': '#FFD700', # Slack (Yellow)
        'PV': '#F85149', # Generator (Red)
        'PQ': '#58A6FF'  # Load (Blue)
    }

    node_x = [pos[node][0] for node in G.nodes()]
    node_y = [pos[node][1] for node in G.nodes()]
    
    bus_labels = [f"Bus {node+1} ({net.bus.loc[node, 'category']})" for node in G.nodes()]
    bus_categories = [net.bus.loc[node, 'category'] for node in G.nodes()]
    
    node_colors = [bus_colors.get(b_cat, '#58A6FF') for b_cat in bus_categories]

    fig.add_trace(go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text',
        hoverinfo='text',
        text=bus_labels,
        textposition="top center",
        marker=dict(size=18, color=node_colors, line=dict(width=1.5, color='#FFFFFF'))
    ))

    fig.update_layout(
        showlegend=False, hovermode='closest',
        margin=dict(b=0, l=0, r=0, t=0),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        height=500
    )

    st.plotly_chart(fig, width="stretch")
