import streamlit as st
import pandapower as pp
import pandapower.networks as pn
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import networkx as nx
import copy

# -------------------------------------------------------------------
# Page Config & Pure Minimalist Dark Theme (Zero Emojis & Zero Background Patterns)
# -------------------------------------------------------------------
st.set_page_config(
    page_title="IEEE 14-Bus N-1 & ACOPF Analyzer",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inject custom CSS for pure minimalist high-contrast theme
st.markdown("""
    <style>
    /* PURE SOLID DARK BACKGROUND - NO PATTERNS, NO EMOJIS */
    .stApp { 
        background-color: #0D1117 !important; 
        color: #C9D1D9 !important; 
    }
    
    [data-testid="stSidebar"] {
        background-color: #161B22 !important;
        border-right: 1px solid #30363D !important;
    }

    /* TYPOGRAPHY AND HEADER STYLING */
    .stMarkdown div p {
        font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Courier, monospace;
        font-weight: 400 !important;
        letter-spacing: 0.05rem;
    }

    .system-banner {
        font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Courier, monospace;
        background-color: #161B22;
        border: 1px solid #30363D;
        color: #58A6FF;
        padding: 0.6rem 1rem;
        border-radius: 6px;
        font-size: 0.95rem;
        font-weight: 600;
        margin-bottom: 1.5rem;
    }

    /* HIGH-CONTRAST METRIC CARDS */
    div[data-testid="stMetricValue"] { 
        font-size: 1.8rem !important; 
        font-weight: 700; 
        color: #58A6FF !important; 
    }
    
    div[data-testid="stMetricLabel"] {
        font-size: 0.85rem !important;
        color: #8B949E !important;
    }

    /* REMOVE HEADER ANCHOR LINKS */
    a.header-anchor, a[href^="#"] {
        display: none !important;
    }

    /* CLEAN BUTTONS */
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

# Main Application Title & Caption (Absolute Zero Emojis)
st.title("Power Grid N-1 Contingency & ACOPF Optimization Suite")
st.caption("Real-time steady-state AC load flow, ACOPF cost optimization dispatch, and interactive N-1 reliability analyzer.")

# Exact Top Callout Banner
st.markdown('<div class="system-banner">SYSTEM: IEEE 14-BUS TEST CASE | SYSTEM BASE MVA: 100</div>', unsafe_allow_html=True)

# -------------------------------------------------------------------
# Sidebar Controls
# -------------------------------------------------------------------
st.sidebar.markdown("### Simulation Controls")
load_scaling = st.sidebar.slider("Grid Load Scaling Factor (%)", min_value=50, max_value=200, value=100, step=10) / 100.0
line_rating_mva = st.sidebar.slider("Line Rating Limit (MVA)", min_value=20, max_value=300, value=100, step=10)
max_voltage = st.sidebar.slider("Max Voltage Limit (p.u.)", 1.00, 1.15, 1.06, 0.01)
min_voltage = st.sidebar.slider("Min Voltage Limit (p.u.)", 0.85, 1.00, 0.94, 0.01)

# -------------------------------------------------------------------
# IEEE 14-Bus Grid Model Builder & Parameter Updates
# -------------------------------------------------------------------
@st.cache_resource
def get_base_network():
    net = pn.case14()
    
    # Categorize buses cleanly
    net.bus['category'] = 'PQ'
    if len(net.ext_grid) > 0:
        net.bus.loc[net.ext_grid.bus.values, 'category'] = 'SL'
    if len(net.gen) > 0:
        for b in net.gen.bus.values:
            if net.bus.loc[b, 'category'] != 'SL':
                net.bus.loc[b, 'category'] = 'PV'
                
    return net

base_net = get_base_network()

def get_updated_network(scale, mva_limit, v_min, v_max):
    net = copy.deepcopy(base_net)
    
    # 1. Scale load demand
    net.load["p_mw"] *= scale
    net.load["q_mvar"] *= scale
    
    # 2. Update operational voltage boundaries
    net.bus["min_vm_pu"] = v_min
    net.bus["max_vm_pu"] = v_max
    
    # 3. Calculate max current limits (kA) per line based on rated MVA
    for idx, line in net.line.iterrows():
        vn_kv = net.bus.loc[line["from_bus"], "vn_kv"]
        max_i_ka = mva_limit / (np.sqrt(3) * vn_kv)
        net.line.loc[idx, "max_i_ka"] = max_i_ka
        
    for idx in net.trafo.index:
        net.trafo.loc[idx, "sn_mva"] = mva_limit
        
    return net

net = get_updated_network(load_scaling, line_rating_mva, min_voltage, max_voltage)

# -------------------------------------------------------------------
# Tab Navigation Layout
# -------------------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["Grid Dashboard", "ACOPF Optimization", "Interactive Outage Inspector"])

# -------------------------------------------------------------------
# TAB 1: Grid Dashboard & Automated N-1 Contingency Scanner
# -------------------------------------------------------------------
with tab1:
    # Run Baseline AC Load Flow
    try:
        pp.runpp(net, numba=False, max_iteration=50)
        baseline_success = True
    except Exception:
        baseline_success = False

    st.subheader("System Performance Metrics")
    if baseline_success:
        total_p = net.res_load.p_mw.sum()
        total_q = net.res_load.q_mvar.sum()
        losses_mw = net.res_line.pl_mw.sum() + net.res_trafo.pl_mw.sum()
        
        in_service_lines = net.line[net.line.in_service == True].index
        in_service_trafos = net.trafo[net.trafo.in_service == True].index
        
        overloaded_lines = len(net.res_line.loc[in_service_lines][net.res_line.loc[in_service_lines].loading_percent > 100.0])
        overloaded_trafos = len(net.res_trafo.loc[in_service_trafos][net.res_trafo.loc[in_service_trafos].loading_percent > 100.0])
        total_overloads = overloaded_lines + overloaded_trafos
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Active Demand (P)", f"{total_p:.1f} MW")
        m2.metric("Reactive Demand (Q)", f"{total_q:.1f} MVar")
        m3.metric("Transmission Losses", f"{losses_mw:.2f} MW")
        m4.metric("N-0 Overloaded Branches", f"{total_overloads}", delta_color="inverse")
    else:
        st.error("Baseline Load Flow Diverged! Load demand exceeds network capacity under current limits.")

    st.divider()

    st.subheader("Automated N-1 Contingency Scan")
    st.write("Simulating single transmission branch outages across all network lines...")
    
    # Run automated N-1 scan
    n1_results = []
    
    for line_idx in net.line.index:
        test_net = copy.deepcopy(net)
        test_net.line.loc[line_idx, "in_service"] = False
        from_b = test_net.line.loc[line_idx, "from_bus"] + 1
        to_b = test_net.line.loc[line_idx, "to_bus"] + 1
        
        try:
            pp.runpp(test_net, numba=False, max_iteration=50)
            
            # Active branches
            act_lines = test_net.line[test_net.line.in_service == True].index
            act_trafos = test_net.trafo[test_net.trafo.in_service == True].index
            
            max_line_load = test_net.res_line.loc[act_lines].loading_percent.max() if len(act_lines) > 0 else 0.0
            max_trafo_load = test_net.res_trafo.loc[act_trafos].loading_percent.max() if len(act_trafos) > 0 else 0.0
            max_branch_load = max(max_line_load, max_trafo_load)
            
            overloads = len(test_net.res_line.loc[act_lines][test_net.res_line.loc[act_lines].loading_percent > 100.0]) + \
                        len(test_net.res_trafo.loc[act_trafos][test_net.res_trafo.loc[act_trafos].loading_percent > 100.0])
            
            v_violations = len(test_net.res_bus[(test_net.res_bus.vm_pu < min_voltage) | (test_net.res_bus.vm_pu > max_voltage)])
            
            status = "CRITICAL" if (overloads > 0 or v_violations > 0) else "STABLE"
            losses = test_net.res_line.pl_mw.sum() + test_net.res_trafo.pl_mw.sum()
            
            n1_results.append({
                "Tripped Outage": f"Line {line_idx} (Bus {from_b} -> Bus {to_b})",
                "Status": status,
                "Max Branch Loading (%)": f"{max_branch_load:.1f}",
                "Overloaded Branches": overloads,
                "Voltage Violations": v_violations,
                "Losses (MW)": f"{losses:.2f}"
            })
        except Exception:
            n1_results.append({
                "Tripped Outage": f"Line {line_idx} (Bus {from_b} -> Bus {to_b})",
                "Status": "BLACKOUT",
                "Max Branch Loading (%)": "-",
                "Overloaded Branches": "-",
                "Voltage Violations": "-",
                "Losses (MW)": "-"
            })

    df_n1 = pd.DataFrame(n1_results)

    def style_status(val):
        if val == "CRITICAL":
            return 'background-color: #3D1414; color: #FF7B7B; font-weight: bold;'
        elif val == "BLACKOUT":
            return 'background-color: #5A1E1E; color: #FFFFFF; font-weight: bold;'
        return 'background-color: #122B1E; color: #58D68D;'

    st.dataframe(df_n1.style.map(style_status, subset=['Status']), width="stretch", height=400)

# -------------------------------------------------------------------
# TAB 2: ACOPF Optimization
# -------------------------------------------------------------------
with tab2:
    st.subheader("AC Optimal Power Flow (ACOPF) Fuel Cost Minimization")
    st.write("ACOPF redispatches generator active power outputs to minimize operational fuel cost while satisfying line thermal ratings and bus voltage limits.")
    
    try:
        acopf_net = copy.deepcopy(net)
        
        # Clear old costs
        for cost_type in ['gen', 'ext_grid']:
            if cost_type in acopf_net and len(acopf_net[cost_type]) > 0:
                acopf_net[cost_type].drop(acopf_net[cost_type].index, inplace=True)
                
        # Set quadratic costs
        for g in acopf_net.gen.index:
            pp.create_poly_cost(acopf_net, g, 'gen', cp1_eur_per_mw=20.0, cp2_eur_per_mw2=0.1)
        if len(acopf_net.ext_grid) > 0:
            pp.create_poly_cost(acopf_net, 0, 'ext_grid', cp1_eur_per_mw=10.0, cp2_eur_per_mw2=0.05)
            
        acopf_net.line["max_loading_percent"] = 100.0
        acopf_net.trafo["max_loading_percent"] = 100.0
        
        pp.runopp(acopf_net, numba=False)
        
        st.success("ACOPF Optimization Converged Successfully!")
        
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Optimal Generator Active Power Dispatch (MW):**")
            gen_data = []
            for i in acopf_net.gen.index:
                b_num = acopf_net.gen.loc[i, 'bus'] + 1
                p_out = acopf_net.res_gen.loc[i, 'p_mw']
                gen_data.append({"Generator": f"Gen Bus {b_num}", "Dispatch (MW)": f"{p_out:.2f}"})
            if len(acopf_net.ext_grid) > 0:
                gen_data.append({"Generator": "External Grid (Slack)", "Dispatch (MW)": f"{acopf_net.res_ext_grid.p_mw.iloc[0]:.2f}"})
                
            st.dataframe(pd.DataFrame(gen_data), width="stretch")
            
        with c2:
            st.markdown("**Post-Optimization Summary:**")
            st.metric("Total Operational Cost", f"${acopf_net.res_cost:.2f} / hr")
            max_opt_load = max(acopf_net.res_line.loading_percent.max(), acopf_net.res_trafo.loading_percent.max())
            st.metric("Max Optimized Branch Loading", f"{max_opt_load:.1f}%")
            
    except Exception as e:
        st.error(f"ACOPF Diverged: Network is heavily congested under current load scale ({e}).")

# -------------------------------------------------------------------
# TAB 3: Interactive Single-Line Diagram (SLD) Outage Inspector
# -------------------------------------------------------------------
with tab3:
    st.subheader("Interactive Line Outage & Structured Single-Line Diagram")
    
    line_options = [-1] + list(net.line.index)
    selected_line = st.selectbox(
        "Select Transmission Line to Trip (Simulate N-1 Outage):",
        options=line_options,
        format_func=lambda x: "All Lines In Service (Normal System State)" if x == -1 else f"Trip Line {x} (Bus {net.line.loc[x, 'from_bus']+1} -> Bus {net.line.loc[x, 'to_bus']+1})"
    )
    
    inspector_net = copy.deepcopy(net)
    if selected_line != -1:
        inspector_net.line.loc[selected_line, "in_service"] = False
        
    try:
        pp.runpp(inspector_net, numba=False, max_iteration=50)
        sld_solved = True
    except Exception:
        sld_solved = False

    # Standard Geographical/Logical Layout Coordinates for IEEE 14-Bus Test System
    # Explicitly positioned so ALL 14 buses and connections are clean and readable
    pos = {
        0: (0.0, 2.0),   # Bus 1 (Slack)
        1: (1.0, 2.0),   # Bus 2 (PV)
        2: (2.5, 2.0),   # Bus 3 (PV)
        3: (1.0, 1.2),   # Bus 4 (PQ)
        4: (0.0, 1.2),   # Bus 5 (PQ)
        5: (0.0, 0.4),   # Bus 6 (PV)
        6: (1.8, 1.2),   # Bus 7 (PQ - LV side of trafo)
        7: (2.5, 1.2),   # Bus 8 (PV - HV side of trafo)
        8: (2.5, 0.4),   # Bus 9 (PQ)
        9: (2.5, -0.4),  # Bus 10 (PQ)
        10: (1.8, -0.4), # Bus 11 (PQ)
        11: (0.0, -0.4), # Bus 12 (PQ)
        12: (0.8, -0.4), # Bus 13 (PQ)
        13: (1.0, 0.4)   # Bus 14 (PQ)
    }

    fig = go.Figure()

    # 1. DRAW LINES (EDGES)
    for idx, line in inspector_net.line.iterrows():
        fb = line["from_bus"]
        tb = line["to_bus"]
        x0, y0 = pos[fb]
        x1, y1 = pos[tb]
        
        is_active = line["in_service"]
        
        if is_active and sld_solved:
            load_pct = inspector_net.res_line.loc[idx, "loading_percent"]
            p_flow = inspector_net.res_line.loc[idx, "p_from_mw"]
            
            if load_pct >= 100.0:
                l_color, l_width = "#F85149", 3.5 # Red (Overloaded)
            elif load_pct >= 70.0:
                l_color, l_width = "#D29922", 2.5 # Orange (Heavy)
            else:
                l_color, l_width = "#3FB950", 2.0 # Green (Normal)
                
            hover = f"Line {idx} (Bus {fb+1} -> Bus {tb+1})<br>Loading: {load_pct:.1f}%<br>Power Flow: {p_flow:.2f} MW"
        elif not is_active:
            l_color, l_width = "#FF4B4B", 2.0
            hover = f"Line {idx} (Bus {fb+1} -> Bus {tb+1})<br>STATUS: TRIPPED / OUT OF SERVICE"
        else:
            l_color, l_width = "#8B949E", 1.5
            hover = f"Line {idx} (Bus {fb+1} -> Bus {tb+1})<br>STATUS: DIVERGED"

        # Draw line trace
        fig.add_trace(go.Scatter(
            x=[x0, x1], y=[y0, y1],
            mode='lines',
            line=dict(width=l_width, color=l_color, dash='solid' if is_active else 'dot'),
            hoverinfo='text',
            text=hover
        ))

    # 2. DRAW TRANSFORMERS (TRANSFORMER BRANCHES INCLUDING BUS 7-8 AND 4-7, 4-9)
    for idx, trafo in inspector_net.trafo.iterrows():
        hv_b = trafo["hv_bus"]
        lv_b = trafo["lv_bus"]
        x0, y0 = pos[hv_b]
        x1, y1 = pos[lv_b]
        
        if sld_solved:
            t_load = inspector_net.res_trafo.loc[idx, "loading_percent"]
            if t_load >= 100.0:
                t_color = "#F85149"
            elif t_load >= 70.0:
                t_color = "#D29922"
            else:
                t_color = "#3FB950"
            t_hover = f"Trafo {idx} (Bus {hv_b+1} -> Bus {lv_b+1})<br>Loading: {t_load:.1f}%"
        else:
            t_color = "#8B949E"
            t_hover = f"Trafo {idx} (Bus {hv_b+1} -> Bus {lv_b+1})"

        fig.add_trace(go.Scatter(
            x=[x0, x1], y=[y0, y1],
            mode='lines',
            line=dict(width=2.5, color=t_color, dash='dash'),
            hoverinfo='text',
            text=t_hover
        ))

    # 3. DRAW BUSES (NODES)
    bus_type_colors = {
        'SL': '#FFD700', # Slack (Yellow)
        'PV': '#F85149', # Generator (Red)
        'PQ': '#58A6FF'  # Load (Blue)
    }

    node_x = [pos[b][0] for b in inspector_net.bus.index]
    node_y = [pos[b][1] for b in inspector_net.bus.index]
    
    node_labels = []
    node_colors = []
    
    for b in inspector_net.bus.index:
        cat = inspector_net.bus.loc[b, 'category']
        node_colors.append(bus_type_colors.get(cat, '#58A6FF'))
        
        if sld_solved:
            vm = inspector_net.res_bus.loc[b, 'vm_pu']
            node_labels.append(f"Bus {b+1} ({cat})<br>{vm:.3f} p.u.")
        else:
            node_labels.append(f"Bus {b+1} ({cat})")

    fig.add_trace(go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text',
        hoverinfo='text',
        text=[f"Bus {b+1}" for b in inspector_net.bus.index],
        textposition="top center",
        hovertext=node_labels,
        marker=dict(size=22, color=node_colors, line=dict(width=2, color='#FFFFFF'))
    ))

    # Pure minimalist canvas layout
    fig.update_layout(
        showlegend=False,
        hovermode='closest',
        margin=dict(b=10, l=10, r=10, t=10),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        height=550
    )

    st.plotly_chart(fig, use_container_width=True)
