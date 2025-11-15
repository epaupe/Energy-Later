import pandas as pd
import os

# ---- File Setup ---- #
file_path = r"C:\Users\pielm\Desktop\EnergyLater\Energy-Later\data\Swissgrid_PRL_SRL_TRL\2024-PRL-SRL-TRL-Ergebnis.csv"
base_dir = os.path.dirname(file_path)

# ---- Load Data ---- #
df = pd.read_csv(file_path, sep=';')

# ---- Filter SRL 2024 ---- #
df_srl = df[df["Ausschreibung"].astype(str).str.startswith("SRL_24")]

# Positive and negative SRL
df_srl_positive = df_srl[df_srl["Beschreibung"].str.contains(r"SRL\+", regex=True)]
df_srl_negative = df_srl[df_srl["Beschreibung"].str.contains(r"SRL\-", regex=True)]


# ---- Weekly Aggregation ---- #
def aggregate_weekly(df_in):
    df = df_in.copy()

    # Extract week part (SRL_24_KWxx) — works with or without _S1, _S2
    df["Week"] = df["Ausschreibung"].str.extract(r"(SRL_24_KW\d+)")

    # Aggregate: sum volume, mean price
    df_weekly = (
        df.groupby(["Week", "Beschreibung"])
          .agg(
              Total_Volume=("Zugesprochenes Volumen", "sum"),
              Mean_Price=("Preis", "mean")
          )
          .reset_index()
    )

    return df_weekly


# ---- Run Aggregation ---- #
weekly_positive = aggregate_weekly(df_srl_positive)
weekly_negative = aggregate_weekly(df_srl_negative)

# ---- Save Results ---- #
weekly_positive.to_csv(os.path.join(base_dir, "SRL_capacity_positive_weekly.csv"), index=False)
weekly_negative.to_csv(os.path.join(base_dir, "SRL_capacity_negative_weekly.csv"), index=False)

