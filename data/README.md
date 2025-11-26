# Data Folder

This folder contains the raw and processed input datasets used for the BESS dispatch optimization model.

## 1. energy-charts_day_ahead/
This directory contains:
- **Raw historical Swiss Day-Ahead electricity prices** (2015–2024)  
  Source: https://www.energy-charts.info/charts/price_spot_market/chart.htm?l=en&c=CH

- **Forecasted Day-Ahead prices for 2025–2050**  
  These synthetic forecasts were generated using a stochastic volatility approach:
  - The yearly mean price is kept constant.
  - Price volatility evolves year-to-year according to a specified volatility factor.
  - The forecast generation method is implemented in the script:  
    **`DA_volatility_forecasts.py`**

**Uncertainty note:**  
This forecasting method is a simplified stylized model and does not incorporate macroeconomic factors, structural shifts, fuel prices, or policy assumptions. Actual long-term price evolution may differ significantly.

---

## 2. Swissgrid_PRL_SRL_TRL/
This directory contains:
- **Historical PRL (FCR) prices** (2015–2024)  
- **Historical SRL (aFRR) capacity auction prices** (2015–2024)  
  Source: https://www.swissgrid.ch/en/home/customers/topics/ancillary-services/tenders.html

- **Forecasted ancillary services prices for 2025–2044**, computed using internally defined forecasting functions:
  - **`PRL_Forecast.py`** for FCR (PRL) price forecasts
  - **`SRL_Capacity.py`** for aFRR capacity price forecasts

**Uncertainty note:**  
These forecasts are based on simplified statistical or trend-based methods.  
They do not account for market design reforms, cross-border changes, increasing RES penetration, or grid expansion, all of which may influence future ancillary-service price levels.

---

## Summary
- Historical data are sourced from public platforms (Energy-Charts, Swissgrid).  
- Forecasted datasets are generated using parameterized volatility and trend models.  

