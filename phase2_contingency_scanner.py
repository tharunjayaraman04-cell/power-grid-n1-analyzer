import pandapower as pp
import pandapower.networks as pn
import pandas as pd

def run_contingency_analysis():
    print("==========================================================")
    print("   PHASE 2: AUTOMATED N-1 CONTINGENCY & RELIABILITY SCAN  ")
    print("==========================================================")
    
    # 1. Load the benchmark network
    net = pn.case14()
    num_lines = len(net.line)
    
    # Run baseline load flow (N-0 state: normal operation)
    pp.runpp(net, numba=False)
    baseline_losses = net.res_line.pl_mw.sum()
    
    print(f"\n[+] Baseline Grid State (N-0): All {num_lines} lines operational.")
    print(f"    - Total Demand: {net.res_load.p_mw.sum():.2f} MW")
    print(f"    - System Line Losses: {baseline_losses:.2f} MW\n")
    
    results = []
    
    # 2. Iteratively simulate tripping each line (N-1 scan loop)
    print("Scanning N-1 contingencies...")
    for line_idx in net.line.index:
        # Trip line 'line_idx'
        net.line.loc[line_idx, "in_service"] = False
        
        try:
            # Run AC Load Flow for the faulted network state
            pp.runpp(net, numba=False)
            
            # Check for line overloads (> 100% capacity)
            overloaded_lines = net.res_line[net.res_line.loading_percent > 100.0]
            max_loading = net.res_line.loading_percent.max()
            most_loaded_line = net.res_line.loading_percent.idxmax()
            
            # Check for bus voltage violations (below 0.95 p.u. or above 1.05 p.u.)
            low_v_buses = net.res_bus[net.res_bus.vm_pu < 0.95]
            
            status = "CRITICAL" if not overloaded_lines.empty or not low_v_buses.empty else "STABLE"
            
            results.append({
                "Tripped Line": f"Line {line_idx} (Bus {net.line.loc[line_idx, 'from_bus']} -> {net.line.loc[line_idx, 'to_bus']})",
                "Status": status,
                "Max Line Loading (%)": round(max_loading, 2),
                "Overloaded Line Count": len(overloaded_lines),
                "Voltage Violations": len(low_v_buses),
                "System Loss (MW)": round(net.res_line.pl_mw.sum(), 2)
            })
            
        except Exception:
            # If load flow diverges, tripping this line causes blackout/islanded bus
            results.append({
                "Tripped Line": f"Line {line_idx} (Bus {net.line.loc[line_idx, 'from_bus']} -> {net.line.loc[line_idx, 'to_bus']})",
                "Status": "BLACKOUT / DIVERGED",
                "Max Line Loading (%)": float('nan'),
                "Overloaded Line Count": 0,
                "Voltage Violations": 0,
                "System Loss (MW)": float('nan')
            })
            
        # Restore line to service for next iteration
        net.line.loc[line_idx, "in_service"] = True

    # 3. Format and present contingency report
    df_report = pd.DataFrame(results)
    
    print("\n----------------------------------------------------------")
    print("                N-1 CONTINGENCY REPORT SUMMARY            ")
    print("----------------------------------------------------------")
    print(df_report.to_string(index=False))
    
    # Highlight highest-risk single point of failure
    critical_cases = df_report[df_report["Status"] != "STABLE"]
    print("\n----------------------------------------------------------")
    if not critical_cases.empty:
        print(f"[!] ALERT: Found {len(critical_cases)} critical contingencies that stress or collapse the grid!")
    else:
        print("[+] SUCCESS: Grid is fully N-1 reliable. No single line failure causes an overload.")
    print("----------------------------------------------------------")

if __name__ == "__main__":
    run_contingency_analysis()