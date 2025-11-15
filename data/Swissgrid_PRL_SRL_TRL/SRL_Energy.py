import pandas as pd
import os

# Paths
file_first = r"C:\Users\pielm\Desktop\EnergyLater\Energy-Later\data\Swissgrid_PRL_SRL_TRL\control-area-balance-2024-net.csv"
file_second = r"C:\Users\pielm\Desktop\EnergyLater\Energy-Later\data\Swissgrid_PRL_SRL_TRL\control-area-balance-2024.csv"

# ---- Load both CSVs ---- #
df1 = pd.read_csv(file_first, sep=';')
df2 = pd.read_csv(file_second, sep=';')

# Parse datetime
df1['Date Time'] = pd.to_datetime(df1['Date Time'], dayfirst=True)
df2['Date Time'] = pd.to_datetime(df2['Date Time'], dayfirst=True)

# Determine last timestamp in the first file
last_time_df1 = df1['Date Time'].max()

# ---- Remove overlapping part from df2 ---- #
df2 = df2[df2['Date Time'] > last_time_df1]

# ---- Keep only needed columns ---- #
cols = ['Date Time', 
        'Abgedeckte Bedarf der aFRR+', 
        'Abgedeckte Bedarf der aFRR-']

df1 = df1[cols]
df2 = df2[cols]

# ---- Combine aFRR+ and aFRR- into net value ---- #
def split_positive_negative(row):
    net = row['Abgedeckte Bedarf der aFRR+'] + row['Abgedeckte Bedarf der aFRR-']
    if net >= 0:
        return pd.Series([net, 0.0])
    else:
        return pd.Series([0.0, net])

df1[['aFRR_Pos', 'aFRR_Neg']] = df1.apply(split_positive_negative, axis=1)
df2[['aFRR_Pos', 'aFRR_Neg']] = df2.apply(split_positive_negative, axis=1)

# Keep only cleaned columns
df1 = df1[['Date Time', 'aFRR_Pos', 'aFRR_Neg']]
df2 = df2[['Date Time', 'aFRR_Pos', 'aFRR_Neg']]

# ---- Combine into final dataset ---- #
df_final = pd.concat([df1, df2], ignore_index=True)

# Sort to be safe
df_final = df_final.sort_values(by='Date Time')

# ---- Save result ---- #
output_path = os.path.join(
    os.path.dirname(file_first), 
    "control-area-balance-2024-cleaned.csv"
)

df_final.to_csv(output_path, index=False)

print("File created:")
print(" →", output_path)
