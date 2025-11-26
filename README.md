# Optimal BESS Dispatch Model

This repository implements a multi-market dispatch and bidding strategy model for a 40 MWh / 10 MW Battery Energy Storage System (BESS).  
The BESS participates simultaneously in the **Day-Ahead (DA)** energy market, **Frequency Containment Reserve (FCR)**, and **automatic Frequency Restoration Reserve (aFRR)**.  
A **72-hour look-ahead / 24-hour apply** receding-horizon approach (MPC) is used to simulate annual operations and compute revenues.

This framework makes it possible to evaluate BESS revenues under different:
- market entry years,
- price forecast assumptions,
- volatility scenarios for future DA prices,
- ancillary-service participation conditions.

---

## Repository Structure

project/
│
├── Optimal_Dispatch_Model.ipynb       # Main notebook (runs full simulation)
│
├── src/
│   ├── config.py                      # Centralized configuration (paths, constants)
│   ├── data_loading.ipynb             # Notebook for loading & visualizing price inputs
│   ├── functions.py                   # Data loading & plotting utilities
│   └── dispatch_model.py              # Core DA–FCR–aFRR dispatch logic
│
├── data/                              # Raw and forecasted price data
│   ├── energy-charts_day_ahead/
│   └── Swissgrid_PRL_SRL_TRL/
│
├── results/                           # Yearly revenue .xlsx outputs
│
└── previous_versions/                 # Archived older model versions

---

## How the Model Works

The main notebook orchestrates the workflow:
1. Load DA, FCR, and aFRR data (historical or forecasted).
2. Define all BESS, market, and optimization parameters.
3. Run the receding-horizon simulation for each year of interest.
4. Export yearly revenue tables and produce diagnostic plots.

The optimization itself is fully implemented in `src/dispatch_model.py`.

---

## Core Functions (dispatch_model.py)

### **1. `solve_da_fcr_afrr()`**
Solves a **single 72-hour optimization window** using Gurobi.  
It co-optimizes:
- Hourly DA charge/discharge,
- 4-hour FCR reserve bids (with stochastic acceptance),
- 24-hour aFRR up/down capacity bids,
- aFRR activation energy (using empirical utilization factors).

The function enforces:
- SOC balance with efficiency and self-discharge,
- Headroom constraints for FCR and aFRR energy,
- Power limits including reserve commitments,
- Daily cycling constraints.

It returns the optimal schedule for all variables over the 72-hour horizon.

---

### **2. `run_receding_horizon_single_year()`**
Wraps the above optimizer inside a **rolling 24-hour loop** to simulate an entire year.

Each step:
- Extracts DA, FCR, and aFRR prices for the next 72 hours,
- Calls `solve_da_fcr_afrr()` to optimize,
- Applies only the first 24 hours of the solution,
- Computes realized DA, FCR, and aFRR revenues,
- Updates SOC and advances the simulation window.

Returns:
- Yearly total revenues,
- DA/FCR/aFRR revenue breakdown,
- Hourly dispatch dataframe,
- Daily profit dataframe.

---