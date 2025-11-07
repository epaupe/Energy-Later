import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import os
from datetime import datetime, timedelta


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
            # Detect whether the file has 1 or 2 header lines by peeking at the second line.
            try:
                with open(path, "r", encoding="utf-8") as f:
                    _first = f.readline()
                    _second = f.readline()
            except UnicodeDecodeError:
                # Fallback in case a file has a different encoding
                with open(path, "r", encoding="latin-1") as f:
                    _first = f.readline()
                    _second = f.readline()

            # If the second line starts with a digit (timestamp), it's a 1-line header; otherwise 2-line header
            s = (_second or "").lstrip()
            skip = 1 if (s and s[0].isdigit()) else 2

            df = pd.read_csv(
                path,
                sep=",",
                header=None,
                names=["timestamp", "price_eur_mwh"],
                usecols=[0, 1],
                skiprows=skip,
                engine="python",
                encoding="utf-8",
            )
            # Parse timestamps; some newer files (e.g., 2025+) omit timestamps on many rows.
            # If timestamps are missing (NaT), reconstruct an hourly sequence aligned to rows.
            ts = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
            if ts.isna().any():
                first_valid = ts.first_valid_index()
                if first_valid is not None:
                    start_ts = ts.iloc[first_valid]
                    # Align so that row index == hour offset from start
                    aligned_start = start_ts - pd.Timedelta(hours=first_valid)
                    full_ts = pd.date_range(start=aligned_start, periods=len(df), freq="h", tz="UTC")
                    ts = pd.Series(full_ts)
                else:
                    # Fallback: derive year from filename and assume Jan 1st start
                    try:
                        year_part = os.path.basename(path).split("_")[-1].split(".")[0]
                        year_int = int(year_part)
                    except Exception:
                        year_int = 2000
                    full_ts = pd.date_range(start=pd.Timestamp(year=year_int, month=1, day=1, tz="UTC"),
                                             periods=len(df), freq="h")
                    ts = pd.Series(full_ts)
            df["timestamp"] = ts
            df["price_eur_mwh"] = pd.to_numeric(df["price_eur_mwh"], errors="coerce")
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


def load_fcr_prices(folder_path, years):
    """
    Load and merge FCR (PRL) auction price data for given years.
    Parses Ausschreibung codes (e.g. PRL_24_01_01_1) into real timestamps.

    Parameters
    ----------
    folder_path : str
        Path to folder containing PRL_filled_YYYY.csv
    years : list of int
        Years to load (e.g. [2023, 2024])

    Returns
    -------
    pd.DataFrame
        Merged and time-indexed DataFrame with columns ['timestamp', 'Preis']
    """

    df_list = []
    for year in years:
        file_path = os.path.join(folder_path, f"PRL_filled_{year}.csv")
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            continue

        df = pd.read_csv(file_path, sep=",", decimal=".")
        df.columns = df.columns.str.strip()  # clean potential whitespace

        # Parse Ausschreibung like PRL_24_01_01_1 → datetime
        def parse_ausschreibung(ausschreibung):
            parts = ausschreibung.split("_")
            # e.g. ['PRL', '24', '01', '01', '1']
            yy, mm, dd, block = int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4])
            year_full = 2000 + yy  # '24' -> 2024
            start_hour = (block - 1) * 4
            return datetime(year_full, mm, dd, start_hour)

        df["timestamp"] = df["Ausschreibung"].apply(parse_ausschreibung)
        df = df[["timestamp", "Preis"]].sort_values("timestamp")

        df_list.append(df)

    if not df_list:
        raise ValueError("No valid PRL files loaded.")

    merged = pd.concat(df_list, ignore_index=True)
    merged = merged.sort_values("timestamp").reset_index(drop=True)

    print(f"Loaded and merged {len(df_list)} FCR files ({len(merged)} total rows).")
    return merged

def plot_fcr_prices(merged_FCR, year=None, week=None, weekly=False):
    """
    Plot FCR (PRL) auction prices.
    
    Parameters
    ----------
    merged_FCR : pd.DataFrame
        Must contain columns ['timestamp', 'Preis'].
    year : int, optional
        Year to filter (e.g. 2024). If None, plots all available years.
    week : int, optional
        Week number (1–52/53) to zoom in. If provided, only that week is plotted.
    weekly : bool, optional
        If True, plot weekly averages instead of 4h resolution.
    """

    df = merged_FCR.copy()

    # Filter by year
    if year is not None:
        df = df[df["timestamp"].dt.year == year]

    # Filter by week number
    if week is not None:
        df["week"] = df["timestamp"].dt.isocalendar().week
        df = df[df["week"] == week]

    if df.empty:
        print("⚠️ No data available for the selected year/week.")
        return

    # Plot weekly average if requested
    if weekly:
        df["week"] = df["timestamp"].dt.isocalendar().week
        df_weekly = df.groupby("week", as_index=False)["Preis"].mean()
        plt.plot(df_weekly["week"], df_weekly["Preis"], marker="o", linewidth=1.8)
        plt.xlabel("Week of Year")
        plt.ylabel("Average FCR Price [€/MWh]")
        plt.title(f"Weekly Average FCR Auction Prices ({year})")
    else:
        plt.figure(figsize=(10, 4))
        plt.plot(df["timestamp"], df["Preis"], marker=".", linewidth=1)
        plt.xlabel("Date / Time")
        plt.ylabel("FCR Price [€/MWh]")

        # Title
        title = "FCR (PRL) Auction Prices"
        if year: title += f" – {year}"
        if week: title += f" – Week {week}"
        plt.title(title)

        # Format x-axis
        if week is None:
            plt.gca().xaxis.set_major_formatter(mdates.DateFormatter("%b"))
            plt.gca().xaxis.set_major_locator(mdates.MonthLocator())
        else:
            plt.gca().xaxis.set_major_formatter(mdates.DateFormatter("%d-%b"))
            plt.gcf().autofmt_xdate()

    plt.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.show()
