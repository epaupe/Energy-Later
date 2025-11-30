import pandas as pd
import datetime as dt
import os

# Input file (relative path)
input_file = r"data/Swissgrid_PRL_SRL_TRL/regelleistung_srl4_2025-11-30.csv"

# Output folder
output_folder = r"data/Swissgrid_PRL_SRL_TRL"

# Ensure output folder exists
os.makedirs(output_folder, exist_ok=True)

# Output files
output_neg = os.path.join(output_folder, "SRL_capacity_negative_weekly_PICASSO.csv")
output_pos = os.path.join(output_folder, "SRL_capacity_positive_weekly_PICASSO.csv")

# Load CSV
df = pd.read_csv(input_file, sep=";", decimal=".")

# Convert date to datetime
df["Date"] = pd.to_datetime(df["Date"], format="%d.%m.%Y")

# Extract ISO week and year
df["ISO_Year"] = df["Date"].dt.isocalendar().year
df["ISO_Week"] = df["Date"].dt.isocalendar().week

# ✅ Filter: only keep ISO year 2024
df = df[df["ISO_Year"] == 2024].copy()

# Function to create the "Week" string (SRL_YY_KWXX)
def format_week(row):
    year_short = str(row["ISO_Year"])[2:]  # last two digits
    week_str = f"{int(row['ISO_Week']):02d}"
    return f"SRL_{year_short}_KW{week_str}"

df["Week"] = df.apply(format_week, axis=1)

# Convert €/MW/week → €/MWh (divide by 168 hours)
df["NEG_MeanPrice"] = df["NEG"] / 168.0
df["POS_MeanPrice"] = df["POS"] / 168.0

# Volume
TOTAL_VOLUME = 2000

# Create negative dataframe
df_neg = pd.DataFrame({
    "Week": df["Week"],
    "Beschreibung": "Secondary control Auction SRL-",
    "Total_Volume": TOTAL_VOLUME,
    "Mean_Price": df["NEG_MeanPrice"]
})

# Create positive dataframe
df_pos = pd.DataFrame({
    "Week": df["Week"],
    "Beschreibung": "Secondary control Auction SRL+",
    "Total_Volume": TOTAL_VOLUME,
    "Mean_Price": df["POS_MeanPrice"]
})

# Save to CSV inside the same folder as the source data
df_neg.to_csv(output_neg, index=False)
df_pos.to_csv(output_pos, index=False)

print(f"Created: {output_neg}")
print(f"Created: {output_pos}")
