import pandas as pd
import os
import re

# === USER SETTINGS ===
output_dir = r"C:\Users\pielm\Desktop\EnergyLater\Energy-Later\data\Swissgrid_PRL_SRL_TRL"

start_year = 2025
end_year = 2040
saturation_year = 2035

start_price = 15.26   # avg at 2025
final_price = 9.00   # avg after saturation

base_year = 2024
base_file = fr"{output_dir}\PRL_filled_{base_year}.csv"

# === Load base profile ===
print(f"Loading base year profile from {base_file}")
base_df = pd.read_csv(base_file)
base_df.columns = base_df.columns.str.strip()

if "Preis" not in base_df.columns:
    raise ValueError("Base file must contain a 'Preis' column")
if "Ausschreibung" not in base_df.columns:
    raise ValueError("Base file must contain an 'Ausschreibung' column")

base_mean = base_df["Preis"].mean()
print(f"Base year {base_year} mean price: {base_mean:.2f}")

# === Compute slope for linear degradation ===
years_to_saturation = saturation_year - start_year
slope = (final_price - start_price) / years_to_saturation
print(f"Linear decline {start_price:.2f} → {final_price:.2f} by {saturation_year} "
      f"({slope:.4f} per year)")

# === Generate scaled profiles for future years ===
for year in range(start_year, end_year + 1):
    # Target average for this year
    if year <= saturation_year:
        target_avg = start_price + (year - start_year) * slope
    else:
        target_avg = final_price

    scale_factor = target_avg / base_mean

    df = base_df.copy()
    df["Preis"] = (df["Preis"] * scale_factor).round(2)

    # Safely replace only the first year occurrence (_24_ -> _25_)
    base_yy = str(base_year)[-2:]
    new_yy = str(year)[-2:]

    df["Ausschreibung"] = df["Ausschreibung"].str.replace(
        f"_{base_yy}_", f"_{new_yy}_", n=1, regex=False
    )

    # 🧹 Remove leap day blocks for non-leap years
    if not ((year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)):
        df = df[~df["Ausschreibung"].str.contains(r"_02_29_")]

    output_path = fr"{output_dir}\PRL_filled_{year}.csv"
    df.to_csv(output_path, index=False)

    print(f"✅ {year}: target avg={target_avg:.2f}, scale={scale_factor:.4f}, rows={len(df)}")

