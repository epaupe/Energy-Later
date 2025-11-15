import pandas as pd

# Path to your cleaned file
file_path = r"C:\Users\pielm\Desktop\EnergyLater\Energy-Later\data\Swissgrid_PRL_SRL_TRL\control-area-balance-2024-cleaned.csv"

# ---- Load data ---- #
df = pd.read_csv(file_path, parse_dates=["Date Time"])

# ---- Determine activation direction ---- #
def direction(row):
    if row["aFRR_Pos"] > 0:
        return 1       # positive aFRR activation
    elif row["aFRR_Neg"] < 0:
        return -1      # negative aFRR activation
    else:
        return 0       # no activation

df["dir"] = df.apply(direction, axis=1)

# Remove neutral / zero values (they break streaks)
df_nonzero = df[df["dir"] != 0].copy()

# ---- Identify consecutive streaks ---- #
df_nonzero["streak_id"] = (df_nonzero["dir"] != df_nonzero["dir"].shift()).cumsum()

streaks = df_nonzero.groupby("streak_id").agg(
    direction=("dir", "first"),
    start=("Date Time", "first"),
    end=("Date Time", "last"),
    intervals=("dir", "size"),
    total_pos_MW=("aFRR_Pos", "sum"),
    total_neg_MW=("aFRR_Neg", "sum")
).reset_index(drop=True)

# Convert MW to MWh (each interval = 15 minutes = 0.25 h)
streaks["total_pos_MWh"] = streaks["total_pos_MW"] * 0.25
streaks["total_neg_MWh"] = streaks["total_neg_MW"] * 0.25

# ---- Identify the worst (longest) streak ---- #
worst_streak = streaks.sort_values("intervals", ascending=False).head(1)

print("\n===== Worst aFRR Dispatch Streak in 2024 =====\n")
print(worst_streak.to_string(index=False))
print("\nExplanation:")
print("- direction == 1 → aFRR+ (upward activation)")
print("- direction == -1 → aFRR- (downward activation)")
print("- intervals = number of consecutive 15-minute steps")
print("- total_pos / total_neg = total MW dispatched during the streak")
