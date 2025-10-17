import pandas as pd

for year in [2023, 2024]:
    df = pd.read_csv(
        fr"C:\Users\pielm\Desktop\EnergyLater\Swissgrid_PRL_SRL_TRL\{year}-PRL-SRL-TRL-Ergebnis.csv",
        sep=";",
        low_memory=False
    )
    filtered_df = df[df["Beschreibung"].str.contains("Primary control", case=False, na=False)]
    filtered_df = filtered_df[filtered_df["Land"].str.strip().str.upper() == "CH"]
    filtered_df = filtered_df[filtered_df["Preis"].diff() != 0]
    filtered_df = filtered_df[["Ausschreibung", "Preis"]]

    block_counts = {}
    new_ids = []
    for val in filtered_df["Ausschreibung"]:
        if val not in block_counts:
            block_counts[val] = 1
        else:
            block_counts[val] += 1
        new_ids.append(f"{val}_{block_counts[val]}")
    filtered_df["Ausschreibung"] = new_ids

    filtered_df.to_csv(
        fr"C:\Users\pielm\Desktop\EnergyLater\Swissgrid_PRL_SRL_TRL\PRL_{year}.csv",
        index=False
    )
    print(f"File with block IDs saved for {year}. Total rows: {len(filtered_df)}")

    expected = []
    days_in_year = 366 if pd.Timestamp(f"{year}-12-31").is_leap_year else 365
    for day in range(1, days_in_year + 1):
        date = pd.Timestamp(f"{year}-01-01") + pd.Timedelta(days=day - 1)
        for block in range(1, 7):
            expected.append(f"PRL_{str(year)[-2:]}_{date.month:02d}_{date.day:02d}_{block}")
    expected_df = pd.DataFrame({"Ausschreibung": expected})

    merged_df = expected_df.merge(filtered_df, on="Ausschreibung", how="left")

    merged_df["Preis"] = merged_df["Preis"].ffill()

    filled_missing = merged_df[merged_df["Preis"].isna()]
    print(f"Missing blocks before fill for {year}: {len(expected_df) - len(filtered_df)}")
    print(f"Still missing after fill for {year}: {len(filled_missing)}")

    merged_df.to_csv(
        fr"C:\Users\pielm\Desktop\EnergyLater\Swissgrid_PRL_SRL_TRL\PRL_filled_{year}.csv",
        index=False
    )
    print(f"Filled file saved for {year}. Total rows: {len(merged_df)}\n")
