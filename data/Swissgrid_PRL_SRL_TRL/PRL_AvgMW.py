import pandas as pd
import os

base_path = r"C:\Users\pielm\Desktop\EnergyLater\Swissgrid_PRL_SRL_TRL"

results = {}

for year in [2023, 2024]:
    file_path = os.path.join(base_path, f"{year}-PRL-SRL-TRL-Ergebnis.csv")
    df = pd.read_csv(file_path, sep=";", low_memory=False)

    # Filter only Primary control and CH rows
    df = df[df["Beschreibung"].str.contains("Primary control", case=False, na=False)]
    df = df[df["Land"].str.strip().str.upper() == "CH"]

    # Convert MW column (Zugesprochenes Volumen) to numeric
    df["Zugesprochenes Volumen"] = pd.to_numeric(df["Zugesprochenes Volumen"], errors="coerce")

    # ✅ Group by both day (Ausschreibung) and block (Beschreibung)
    total_mw_per_block = (
        df.groupby(["Ausschreibung", "Beschreibung"])["Zugesprochenes Volumen"]
        .sum()
        .reset_index()
    )
    total_mw_per_block.columns = ["Ausschreibung", "Beschreibung", "Total_MW"]

    # Save results
    output_path = os.path.join(base_path, f"CH_PRL_totalMW_per_block_{year}.csv")
    total_mw_per_block.to_csv(output_path, index=False)

    # Store for comparison
    results[year] = total_mw_per_block

    # Print summary
    year_total_avg = total_mw_per_block["Total_MW"].mean()
    print(f"{year}: saved {len(total_mw_per_block)} blocks | average total MW per block = {year_total_avg:.2f}")

# After processing both years
combined_df = pd.concat([results[2023], results[2024]], ignore_index=True)
combined_avg = combined_df["Total_MW"].mean()
print(f"\nCombined average total MW per block (2023 + 2024): {combined_avg:.2f}")