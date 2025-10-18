import pandas as pd
import matplotlib.pyplot as plt
import os

def load_da_market_data(folder_path, years):
    """
    Loads and processes day-ahead market price data from CSV files for given years.

    Args:
        folder_path (str): The directory where the CSV files are stored.
        years (list of int): A list of the years to load.

    Returns:
        pd.DataFrame: A merged, cleaned, and sorted DataFrame containing the 
                      day-ahead prices with 'timestamp' and 'price_eur_mwh' columns.
    """
    file_paths = [os.path.join(folder_path, f"energy-charts_DA_{year}.csv") for year in years]

    df_list = []
    for path in file_paths:
        try:
            df = pd.read_csv(path, sep=',', decimal='.', skiprows=[0])
            df.columns = ['timestamp', 'price_eur_mwh'] 
            df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
            df['price_eur_mwh'] = pd.to_numeric(df['price_eur_mwh'], errors='coerce')
            df_list.append(df)
        except FileNotFoundError:
            print(f"Warning: File not found for path {path}. Skipping.")

    if not df_list:
        print("No data loaded. Returning empty DataFrame.")
        return pd.DataFrame(columns=['timestamp', 'price_eur_mwh'])

    # Merge the DA market price dataframes
    merged_df = pd.concat(df_list, ignore_index=True)
    merged_df = merged_df.dropna(subset=['timestamp', 'price_eur_mwh'])
    merged_df = merged_df.sort_values('timestamp').reset_index(drop=True)
    
    return merged_df

def plot_DA_week(df, year, week):
    df = df.copy()
    df['iso_year'] = df['timestamp'].dt.isocalendar().year
    df['iso_week'] = df['timestamp'].dt.isocalendar().week

    week_df = df[(df['iso_year'] == year) & (df['iso_week'] == week)]

    if week_df.empty:
        print(f"No data found for year {year}, week {week}")
        return

    plt.figure(figsize=(10, 5))
    plt.plot(week_df['timestamp'], week_df['price_eur_mwh'], marker='.')
    plt.title(f"Day-Ahead Prices – Week {week}, {year}")
    plt.xlabel("Date")
    plt.ylabel("Price [€/MWh]")
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.tight_layout()
    plt.show()