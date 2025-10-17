import pandas as pd
import matplotlib.pyplot as plt

def plot_DA_week(df, year, week, datetime_col='timestamp', price_col='price_eur_mwh'):
    """
    Plot day-ahead market prices for a given week and year.

    Parameters
    ----------
    df : pd.DataFrame
        Merged DataFrame containing the DA prices.
    year : int
        Year to plot (e.g. 2024)
    week : int
        ISO week number (1–52/53)
    datetime_col : str
        Name of the datetime column
    price_col : str
        Name of the price column
    """
    # --- Parse datetime column ---
    df[datetime_col] = pd.to_datetime(df[datetime_col])

    # --- Extract ISO week and year ---
    df['iso_year'] = df[datetime_col].dt.isocalendar().year
    df['iso_week'] = df[datetime_col].dt.isocalendar().week

    # --- Filter the requested week ---
    df_week = df[(df['iso_year'] == year) & (df['iso_week'] == week)]

    if df_week.empty:
        print(f"No data found for year {year}, week {week}. Check your datetime column format.")
        return

    # --- Plot ---
    plt.figure(figsize=(10, 5))
    plt.plot(df_week[datetime_col], df_week[price_col], marker='.', linestyle='-')
    plt.title(f"Day-Ahead Market Prices – Week {week}, {year}")
    plt.xlabel("Date")
    plt.ylabel("Price [€/MWh]")
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.tight_layout()
    plt.show()