# Power Grid N-1 Contingency & ACOPF Optimization Suite

An interactive, web-based power system analysis suite built to simulate steady-state AC load flow, perform automated N-1 grid reliability scans, and optimize generator dispatch costs using AC Optimal Power Flow (ACOPF) on the IEEE 14-bus test system.

Live Interactive Web Application: https://power-grid-n1-analyzer.streamlit.app

---

## Key Features

* Steady-State AC Load Flow Analysis: Executes Newton-Raphson load flow to compute active power (P), reactive power (Q), transmission losses, voltage magnitudes (V_i), and system power factor.
* Voltage-Adjusted Thermal Loading Engine: Converts line MVA thermal limits into bus-voltage-adjusted current capacities (I_max in kA), ensuring accurate percentage loading calculations without numerical divergence.
* AC Optimal Power Flow (ACOPF): Redispatches active generator power (P_g) using polynomial cost curves to minimize total operational costs while enforcing branch thermal ratings and bus voltage limits.
* Automated N-1 Contingency Scanner: Iteratively isolates individual transmission lines across the network to identify critical points of failure, line overloads, and low-voltage security violations.
* Interactive Network Topology Map: Renders network graphs using NetworkX and Plotly, featuring dynamic line color-coding (Green for normal, Orange for heavy load, Red for critical overload) and hover telemetry.
* Single Outage Inspector: Allows users to simulate specific line trips via a dropdown selector to observe immediate post-contingency voltage drops and power flow redistributions.

---

## Tech Stack & Dependencies

* Core Language: Python 3.x
* Power Systems Engine: pandapower (built on scipy non-linear solvers)
* Frontend & Dashboard: streamlit
* Data Visualization & Graphs: plotly, networkx
* Data Processing: pandas, numpy

---

## Quick Start & Installation

### 1. Clone the repository
```bash
git clone [https://github.com/tharunjayaraman04-cell/power-grid-n1-analyzer.git](https://github.com/tharunjayaraman04-cell/power-grid-n1-analyzer.git)
cd power-grid-n1-analyzer
---

## License
Distributed under the MIT License. See LICENSE for details.
