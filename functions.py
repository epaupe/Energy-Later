import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import os
from datetime import datetime, timedelta
from pathlib import Path


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


def generate_fcr_price_forecasts(saturation_start_year):
    """
    Create synthetic FCR (PRL) price forecasts by scaling a base-year profile.

    Parameters
    ----------
    saturation_start_year : int
        Year when prices reach their minimum average (linear decline before,
        flat afterwards).

    Notes
    -----
    Reads `PRL_filled_2024.csv` from `data/Swissgrid_PRL_SRL_TRL`, scales
    the profile to target yearly means between 2025–2040, removes leap day
    entries for non-leap years, and writes `PRL_filled_<year>.csv` files to the
    same folder.
    """
    output_dir = Path("data") / "Swissgrid_PRL_SRL_TRL"
    output_dir.mkdir(parents=True, exist_ok=True)

    start_year = 2025
    end_year = 2040
    saturation_year = saturation_start_year

    start_price = 15.26   # avg at 2025
    final_price = 9.00   # avg after saturation

    base_year = 2024
    base_file = output_dir / f"PRL_filled_{base_year}.csv"

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

        # Remove leap day blocks for non-leap years
        if not ((year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)):
            df = df[~df["Ausschreibung"].str.contains(r"_02_29_")]

        output_path = output_dir / f"PRL_filled_{year}.csv"
        df.to_csv(output_path, index=False)

        print(f"{year}: target avg={target_avg:.2f}, scale={scale_factor:.4f}, rows={len(df)}")

def build_acceptance_rate(start_year, end_year, saturation_year):
    """
    Create a dict of yearly FCR acceptance rates.

    Parameters
    ----------
    start_year : int
        First year to include.
    end_year : int
        Last year to include.
    saturation_year : int
        Year at which acceptance stays 100% and then begins to decline.

    Returns
    -------
    dict[int, float]
        Mapping year → acceptance probability (1.0 until saturation_year,
        linear decline to 0.4 by end_year).
    """
    rates = {}
    if saturation_year >= end_year:
        # Saturation occurs after horizon → stick with full acceptance.
        for year in range(start_year, end_year + 1):
            rates[year] = 1.0
        return rates

    # Otherwise linearly taper from saturation_year down to end_year (40%).
    decline_span = end_year - saturation_year
    min_acceptance = 0.4
    for year in range(start_year, end_year + 1):
        if year <= saturation_year:
            rates[year] = 1.0
        else:
            frac = (year - saturation_year) / decline_span
            rates[year] = max(min_acceptance, 1.0 - (1.0 - min_acceptance) * frac)
    return rates
