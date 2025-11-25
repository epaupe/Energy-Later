import pandas as pd
import calendar
import os

# === File paths ===
base_path = os.path.dirname(os.path.abspath(__file__))
input_file = os.path.join(base_path, "energy-charts_DA_2024.csv")

# Load 2024 data
df = pd.read_csv(input_file, skiprows=1)
df.columns = ["Date (GMT+1)", "Price (EUR/MWh)"]

# Convert date column to datetime
df["Date (GMT+1)"] = pd.to_datetime(df["Date (GMT+1)"], errors="coerce")

# Compute mean and std of 2024 prices
mean_price = df["Price (EUR/MWh)"].mean()
base_std = df["Price (EUR/MWh)"].std()

base_year = 2024

# Loop for years 2025–2040
for year in range(2025, 2051):
    df_forecast = df.copy()

    # 🔧 Ensure datetime dtype (fixes the AttributeError)
    df_forecast["Date (GMT+1)"] = pd.to_datetime(df_forecast["Date (GMT+1)"], errors="coerce")

    # Drop Feb 29 for non-leap years
    if not calendar.isleap(year):
        df_forecast = df_forecast[
            ~((df_forecast["Date (GMT+1)"].dt.month == 2) &
              (df_forecast["Date (GMT+1)"].dt.day == 29))
        ]

    # Replace year in timestamps (safe after dropping leap day)
    df_forecast["Date (GMT+1)"] = df_forecast["Date (GMT+1)"].apply(
        lambda d: d.replace(year=year)
    )

    # Volatility increase: +2% per year (customize as needed)
    vol_factor = 1.01 ** (year - base_year)

    # Apply volatility scaling (keep same mean)
    df_forecast["Price (EUR/MWh)"] = (
        mean_price + (df_forecast["Price (EUR/MWh)"] - mean_price) * vol_factor
    )

    # Define output path for each year
    output_file = os.path.join(base_path, f"energy-charts_DA_{year}.csv")

    # Save forecast file
    df_forecast.to_csv(output_file, index=False)

    # Report summary
    n_hours = len(df_forecast)
    print(f"✅ Saved {output_file} — {n_hours} hours, volatility factor {vol_factor:.3f}")
