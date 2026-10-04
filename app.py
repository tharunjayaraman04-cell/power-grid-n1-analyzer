import streamlit as st
import pandapower as pp
import pandapower.networks as pn
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import networkx as nx

# -------------------------------------------------------------------
# Page Config & Custom Design (NO EMOJIS)
# -------------------------------------------------------------------
st.set_page_config(page_title="Power Grid N-1 & ACOPF Analyzer", layout="wide", initial_sidebar_state="expanded")

# CUSTOM CSS: Minimalist Power Grid Background and Emoji-Free UI
st.markdown("""
    <style>
    /* SOLID MINIMALIST TECH BACKGROUND */
    .stApp { 
        background-color: #0E1117; 
        background-image: 
            linear-gradient(rgba(14, 17, 23, 0.95), rgba(14, 17, 23, 0.98)),
            url('data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI0MCIgaGVpZ2h0PSI0MCIgdmlld0JveD0iMCAwIDQwIDQwIj48ZyBmaWxsLXJ1bGU9ImV2ZW5vZGQiPjxnIGZpbGw9IiM5Q0IxRjUiIGZpbGwtb3BhY2l0eT0iMC4wNSI+PHBhdGggZD0iTTAgMGg0MHY0MEgwVjB6bTIwIDIwaDIwdjIwSDIWMjB6TTAgMjBoMjB2MjBIMFYyMHoyMCAwaDIwdjIwSDIwVjB6Ii8+PC9nPjwvZz48L3N2Zz4=');
        color: #E0E6ED; 
    }
    
    [data-testid="stSidebar"] {
        background-color: transparent !important;
        border-right: 1px solid rgba(156, 177, 245, 0.1) !important;
    }

    /* REMOVE HEADER ANCHOR LINKS (CLEAN LOOK) */
    a.header-anchor {
        display: none !important;
    }
    a[href^="#"] {
        display: none !important;
    }

    /* Typography & Metric Styling */
    div[data-testid="stMetricValue"] { 
        font-size: 1.6rem !important; 
        font-weight: 700; 
        color: #58A6FF; /* Accent blue for data */
    }
    
    /* Clean Green Button (Matches image 6) */
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

# Main Title & Description (EMOJI FREE)
st.title("POWER GRID N-1 CONTINGENCY & ACOPF OPTIMIZATION SUITE")
st.caption("Real-time steady-state AC load flow, ACOPF cost optimization dispatch, and interactive N-1 reliability analyzer.")

# -------------------------------------------------------------------
# Sidebar Simulation Controls (Clean Headers)
# -------------------------------------------------------------------
st.sidebar.markdown("### Simulation Controls")
load_scaling = st.sidebar.slider("Grid Load Scaling Factor (%)", min_value=50, max_value=250, value=120, step=10) / 100.0
line_rating_mva = st.sidebar.slider("Line Rating Limit (MVA)", min_value=50, max_value=500, value=150, step=10)
max_voltage = st.sidebar.slider("Max Voltage Limit (p.u.)", 1.00, 1.10, 1.05, 0.01)
min_voltage = st.sidebar.slider("Min Voltage Limit (p.u.)", 0.90, 1.00, 0.95, 0.01)

# -------------------------------------------------------------------
# Grid Model Builder Function
# -------------------------------------------------------------------
@st.cache_resource
def get_configured_network():
    return pn.case14()

base_net = get_configured_network()

def update_network_parameters(scale, mva_limit, v_min, v_max):
    import copy
    net = copy.deepcopy(base_net)
    net.load["p_mw"] *= scale
    net.load["q_mvar"] *= scale
    net.bus["min_vm_pu"] = v_min
    net.bus["max_vm_pu"] = v_max
    
    for idx, line in net.line.iterrows():
        from_bus_vn = net.bus.loc[line["from_bus"], "vn_kv"]
        max_i_ka = mva_limit / (1.732 * from_bus_vn)
        net.line.loc[idx, "max_i_ka"] = max_i_ka
        
    return net

net = update_network_parameters(load_scaling, line_rating_mva, min_voltage, max_voltage)

# Tab Navigation Layout (EMOJI FREE)
tab1, tab2, tab3 = st.tabs(["Grid Dashboard", "ACOPF Optimization", "Interactive Outage Inspector"])

# -------------------------------------------------------------------
# TAB 1: Grid Dashboard & N-1 Contingency Scanner
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
    if st.button("Run N-1 Reliability Scan"):
        results = []
        num_lines = len(net.line)
        progress_bar = st.progress(0)
        
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
                    "Tripped Line": f"Line {line_idx} (Bus {net.line.loc[line_idx, 'from_bus']} -> Bus {net.line.loc[line_idx, 'to_bus']})",
                    "Status": status,
                    "Max Line Loading (%)": round(max_load, 1),
                    "Overloaded Lines": overloads,
                    "Voltage Violations": v_violations,
                    "Losses (MW)": round(net.res_line.pl_mw.sum(), 2)
                })
            except Exception:
                results.append({
                    "Tripped Line": f"Line {line_idx} (Bus {net.line.loc[line_idx, 'from_bus']} -> Bus {net.line.loc[line_idx, 'to_bus']})",
                    "Status": "BLACKOUT / DIVERGED",
                    "Max Line Loading (%)": None,
                    "Overloaded Lines": None,
                    "Voltage Violations": None,
                    "Losses (MW)": None
                })
            net.line.loc[line_idx, "in_service"] = True
            progress_bar.progress((i + 1) / num_lines)
            
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
    
    if st.button("Execute ACOPF Dispatch Optimization"):
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
# TAB 3: Interactive Topology Map
# -------------------------------------------------------------------
with tab3:
    st.subheader("Interactive Line Outage & Network Topology Map")
    
    selected_line = st.selectbox(
        "Select a Transmission Line to Trip (Simulate Specific N-1 Outage):",
        options=[-1] + list(net.line.index),
        format_func=lambda x: "All Lines In Service (Normal State)" if x == -1 else f"Trip Line {x} (Bus {net.line.loc[x, 'from_bus']} -> Bus {net.line.loc[x, 'to_bus']})"
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

    pos = nx.spring_layout(G, seed=42)
    fig = go.Figure()

    if map_flow_success:
        for idx, line in net.line.iterrows():
            if not line["in_service"]:
                continue
                
            from_bus = line["from_bus"]
            to_bus = line["to_bus"]
            x0, y0 = pos[from_bus]
            x1, y1 = pos[to_bus]
            
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

            fig.add_trace(go.Scatter(
                x=[x0, x1], y=[y0, y1],
                mode='lines',
                line=dict(width=line_width, color=line_color),
                hoverinfo='text',
                text=f"Line {idx} (Bus {from_bus} -> Bus {to_bus})<br>Loading: {loading:.1f}%<br>Power Flow: {p_mw:.2f} MW"
            ))

    node_x = [pos[node][0] for node in G.nodes()]
    node_y = [pos[node][1] for node in G.nodes()]
    bus_labels = [f"Bus {node}" for node in G.nodes()]

    fig.add_trace(go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text',
        hoverinfo='text',
        text=bus_labels,
        textposition="top center",
        marker=dict(size=18, color='#58A6FF', line=dict(width=1.5, color='#FFFFFF'))
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
