import pandas as pd
import matplotlib.pyplot as plt

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