import pandapower as pp
import pandapower.networks as pn

def run_phase1_starter():
    print("--- PHASE 1: POWER GRID LOAD FLOW & ACOPF INITIALIZATION ---")
    
    # 1. Load standard IEEE 14-bus benchmark test network
    net = pn.case14()
    print(f"\n[+] Loaded IEEE 14-Bus Grid:")
    print(f"    - Buses: {len(net.bus)}")
    print(f"    - Transmission Lines: {len(net.line)}")
    print(f"    - Generators: {len(net.gen) + len(net.ext_grid)}")
    print(f"    - Connected Loads: {len(net.load)}")

    # 2. Run Standard AC Load Flow (Newton-Raphson numerical method)
    pp.runpp(net, numba=False)  # Suppresses numba warning
    
    print("\n--- BASELINE LOAD FLOW RESULTS ---")
    print(f"Total Grid Demand (P): {net.res_load.p_mw.sum():.2f} MW")
    print(f"Total Grid Demand (Q): {net.res_load.q_mvar.sum():.2f} MVar")
    print(f"Total Transmission Losses: {net.res_line.pl_mw.sum():.2f} MW")
    
    # Identify heavily loaded transmission lines (> 70% capacity)
    print("\nHeavily Loaded Transmission Lines (> 70% capacity):")
    heavy_lines = net.res_line[net.res_line.loading_percent > 70]
    if heavy_lines.empty:
        print("  None. All lines operating below 70% thermal capacity.")
    else:
        for idx, row in heavy_lines.iterrows():
            from_bus = net.line.loc[idx, 'from_bus']
            to_bus = net.line.loc[idx, 'to_bus']
            print(f"  - Line {idx} (Bus {from_bus} -> Bus {to_bus}): {row['loading_percent']:.2f}% capacity")

    # 3. Define Generator Costs & Constraints for Optimal Power Flow (ACOPF)
    # Set bus voltage bounds (0.95 to 1.05 p.u.)
    net.bus["min_vm_pu"] = 0.95
    net.bus["max_vm_pu"] = 1.05
    
    # Clear pre-existing cost tables to avoid duplicate entries
    net.poly_cost.drop(net.poly_cost.index, inplace=True)
    
    # Assign custom cost functions ($/MW) for each generator
    for idx in net.gen.index:
        pp.create_poly_cost(net, element=idx, et="gen", cp1_eur_per_mw=20 + idx * 5)
    
    for idx in net.ext_grid.index:
        pp.create_poly_cost(net, element=idx, et="ext_grid", cp1_eur_per_mw=15)

    # 4. Run AC Optimal Power Flow (ACOPF)
    try:
        pp.runopp(net, numba=False)
        print("\n--- OPTIMAL POWER FLOW (ACOPF) SUCCESSFUL ---")
        print(f"Optimized System Generation Cost: ${net.res_cost:.2f} / hour")
        print(f"Optimized Line Losses: {net.res_line.pl_mw.sum():.2f} MW")
        
        print("\nGenerator Dispatch Summary (MW):")
        for idx in net.gen.index:
            p_mw = net.res_gen.loc[idx, 'p_mw']
            max_p = net.gen.loc[idx, 'max_p_mw']
            print(f"  - Generator at Bus {net.gen.loc[idx, 'bus']}: {p_mw:.2f} MW (Max Capacity: {max_p:.2f} MW)")
            
    except Exception as e:
        print(f"\n[-] OPF Solver Notice: {e}")

if __name__ == "__main__":
    run_phase1_starter()