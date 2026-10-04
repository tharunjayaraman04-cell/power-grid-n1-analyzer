# Power Grid N-1 Contingency & Optimal Power Flow (ACOPF) Analyzer

An interactive power systems analysis suite built in Python using Pandapower, Streamlit, and Plotly. This tool models transmission grid steady-state behavior, executes AC Optimal Power Flow (ACOPF) cost optimization, and performs automated N-1 contingency scans to evaluate grid security under dynamic load stress.

---

## Key Features

* AC Load Flow Analysis: Solves non-linear power flow equations on benchmark IEEE networks using Newton-Raphson numerical solvers.
* AC Optimal Power Flow (ACOPF): Optimizes generator active power dispatch to minimize hourly generation fuel cost while enforcing voltage bounds (0.95 to 1.05 p.u.) and transmission line thermal limits.
* Automated N-1 Contingency Scanner: Iteratively simulates single transmission line trip events (N-1), identifying critical points of failure, thermal line overloads (above 100%), and bus voltage security violations.
* Interactive Streamlit Dashboard: Real-time parameter controls for grid load scaling, voltage bounds adjustments, and dynamic network topology heatmaps.

---

## Tech Stack & Dependencies

* Language: Python 3.10+
* Power Systems Engine: pandapower
* Data & Numerical Processing: numpy, pandas, scipy
* Frontend & Visualization: streamlit, plotly, networkx

---

## Quick Start & Installation

1. Clone the repository:
   git clone https://github.com/your-username/power-grid-n1-analyzer.git
   cd power-grid-n1-analyzer

2. Install dependencies:
   pip install -r requirements.txt

3. Launch the Web Dashboard:
   streamlit run app.py
   (Access the web app at http://localhost:8501 in your browser)

---

## System Architecture & Methodology

[ IEEE 14-Bus Test Case ] ---> [ Load Scaling Engine ] ---> [ Newton-Raphson AC Load Flow ]
                                                                     |
                                                                     +---> [ ACOPF Generator Dispatch ]
                                                                     +---> [ Iterative N-1 Contingency Loop ]
                                                                                     |
                                                                                     v
                                                                     [ Streamlit Interactive Dashboard ]

---

## Project Structure

power-grid-n1-analyzer/
├── app.py                      # Interactive Streamlit Web Application
├── phase1_grid_starter.py      # Baseline Load Flow & ACOPF Script
├── phase2_contingency_scanner.py # Command-line N-1 Contingency Scanner
├── requirements.txt            # Project Dependencies
└── README.md                   # Project Documentation

---

## License
Distributed under the MIT License. See LICENSE for details.