import pandas as pd
import os

# === USER SETTINGS ===

output_dir = r"C:\Users\pielm\Desktop\EnergyLater\Swissgrid_PRL_SRL_TRL"

start_year = 2025
end_year = 2040
saturation_year = 2035

start_price = 15.26   # avg at 2025
final_price = 10.00   # avg after saturation

base_year = 2024
base_file = fr"{output_dir}\PRL_filled_{base_year}.csv"

# === Load base profile ===
print(f"Loading base year profile from {base_file}")
base_df = pd.read_csv(base_file)
base_df.columns = base_df.columns.str.strip()

if "Preis" not in base_df.columns:
    raise ValueError("Base file must contain a 'Preis' column")

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
    df["Preis"] = df["Preis"] * scale_factor
    df["Preis"] = df["Preis"].round(2)

    # Update Ausschreibung identifiers to reflect the new year
    df["Ausschreibung"] = df["Ausschreibung"].str.replace(
        f"_{str(base_year)[-2:]}_", f"_{str(year)[-2:]}_", regex=False
    )

    output_path = fr"{output_dir}\PRL_filled_{year}.csv"
    df.to_csv(output_path, index=False)
    print(f"✅ {year}: target avg={target_avg:.2f}, scale={scale_factor:.4f}, "
          f"rows={len(df)}")
