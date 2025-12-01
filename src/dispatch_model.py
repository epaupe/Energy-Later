import numpy as np
import pandas as pd
import gurobipy as gp
from gurobipy import GRB, quicksum

def solve_da_fcr_afrr(
    da_block,
    fcr_prices_block,
    initial_soc,
    AFRR_Pos_Cap_price,
    AFRR_Neg_Cap_price,
    *,
    granularity_DA=1,
    granularity_FCR=4,
    granularity_AFRR =24,
    battery_capacity=40.0,
    soc_min=1.0,
    charge_rate_bounds=(0.0, 10.0),
    discharge_rate_bounds=(0, 10.0),
    efficiency=0.92,
    self_discharge_rate=3e-5,
    minimum_bid_FCR=1.0,
    wcs_factor_FCR=(0.36, 0.27, 0.18, 0.90),
    wcs_factor_AFRR=1.8,
    time_limit_seconds=300,
    gurobi_output=False,
    terminal_soc_target=None,
    activation_counter=0,
    year=2024,
    utilization_factor_AFRR=0.05,
    acceptance_rate_fcr=None,
    acceptance_rate_afrr=None,
    minimum_bid_AFRR=5,
    AFRR_Pos_Act_price = 375, 
    AFRR_Neg_Act_price = -35 
):
    """
    Solve the joint 72h DA + FCR + aFRR optimization problem.

    The model optimizes battery dispatch for:
        • Day-Ahead (hourly)
        • FCR (4-hour blocks with worst-case energy content)
        • aFRR capacity & activation (daily blocks)

    Notes
    -----
    - FCR acceptance is stochastic: each block uses a uniform random draw.
    - aFRR activation in the SOC balance is scaled by an empirical utilization factor.
    - Battery dynamics include self-discharge and round-trip efficiency.
    - SOC headroom ensures available energy for reserves.
    """

    # ----------------------------------------------------------------------
    # 1. Process time horizon and price inputs
    # ----------------------------------------------------------------------
    da_block = da_block.sort_values("timestamp").reset_index(drop=True)
    clearing_price_DA = da_block["price_eur_mwh"].to_numpy(dtype=float)

    n_hours = len(clearing_price_DA)
    DA_horizon = range(int(n_hours / granularity_DA)) #number of 1h blocks
    FCR_horizon = range(int(n_hours / granularity_FCR))  # number of 4h blocks
    AFRR_horizon = range(int(n_hours / granularity_AFRR)) # number of 24h blocks 


    clearing_price_FCR = fcr_prices_block["Preis"].to_numpy(dtype=float)
    assert len(clearing_price_FCR) == len(FCR_horizon), (
        f"FCR price length {len(clearing_price_FCR)} "
        f"≠ number of 4h blocks {len(FCR_horizon)}"
    )

    # ----------------------------------------------------------------------
    # 2. Gurobi model creation
    # ----------------------------------------------------------------------
    MMO = gp.Model("DA_FCR_receding_horizon")
    MMO.Params.OutputFlag = 1 if gurobi_output else 0
    MMO.Params.TimeLimit = time_limit_seconds

    charge_lb, charge_ub = charge_rate_bounds
    discharge_lb, discharge_ub = discharge_rate_bounds

    # ----------------------------------------------------------------------
    # 3. Decision variables 
    # ----------------------------------------------------------------------
    Charge = MMO.addVars(n_hours, vtype=GRB.CONTINUOUS, lb=charge_lb, ub=charge_ub, name="Charge")
    Discharge = MMO.addVars(n_hours, vtype=GRB.CONTINUOUS, lb=discharge_lb, ub=discharge_ub, name="Discharge")
    Charging_Indicator = MMO.addVars(n_hours, vtype=GRB.BINARY, name="Charging_Indicator")
    SOC = MMO.addVars(n_hours + 1, vtype=GRB.CONTINUOUS, lb=soc_min, ub=battery_capacity, name="SOC")

    FCR_Participation = MMO.addVars(FCR_horizon, vtype=GRB.BINARY, name="FCR_Participation")
    FCR_Volume = MMO.addVars(FCR_horizon, vtype=GRB.CONTINUOUS, lb=0.0, ub=charge_ub, name="FCR_Volume")

    AFRR_Participation_Pos = MMO.addVars(AFRR_horizon, vtype=GRB.BINARY, name="AFRR_Participation_Pos")
    AFRR_Volume_Pos = MMO.addVars(AFRR_horizon, vtype=GRB.INTEGER, lb=0.0, ub=discharge_ub, name="AFRR_Volume_Pos")

    AFRR_Participation_Neg = MMO.addVars(AFRR_horizon, vtype=GRB.BINARY, name="AFRR_Participation_Neg")
    AFRR_Volume_Neg = MMO.addVars(AFRR_horizon, vtype=GRB.INTEGER, lb=0.0, ub=charge_ub, name="AFRR_Volume_Neg")

    # ----------------------------------------------------------------------
    # 4. Battery SOC balance with aFRR activation
    # ----------------------------------------------------------------------
    MMO.addConstr(SOC[0] == initial_soc)
    for h in AFRR_horizon:
        for i in range(granularity_AFRR):
            t = granularity_AFRR * h  + i
            MMO.addConstr(SOC[t + 1] == (1 - self_discharge_rate) * SOC[t] 
                          + granularity_DA * (efficiency * Charge[t] - (1 / efficiency) * Discharge[t]) 
                          + granularity_DA * utilization_factor_AFRR * ((efficiency * AFRR_Volume_Neg[h] - (1 / efficiency) * AFRR_Volume_Pos[h]))
            )
    #NB: The FCR energy content is modelled via headroom constraints below, not in the SOC balance directly
    #NB 2: the aFRR are scaled by an empirical utilization factor to account for the fact that not all bid volume is activated, this means that if we bid 1 MW of aFRR capacity, only 0.05 MW on average will be activated, so the impact on SOC is reduced accordingly.

    if terminal_soc_target is not None: # enforce terminal SOC for last time step!
        MMO.addConstr(SOC[n_hours] == terminal_soc_target)

    # ----------------------------------------------------------------------
    # 5. Prevent simultaneous charging and discharging
    # ----------------------------------------------------------------------
    for t in range(n_hours):
        MMO.addGenConstrIndicator(Charging_Indicator[t], True, Discharge[t] == 0)
        MMO.addGenConstrIndicator(Charging_Indicator[t], False, Charge[t] == 0)


    # ----------------------------------------------------------------------
    # 6. FCR participation constraints with stochastic acceptance
    # ----------------------------------------------------------------------
    for t in FCR_horizon:
        # Random number for activation
        rng = np.random.default_rng(seed=activation_counter)
        random_value_fcr = rng.random()
        activation_counter += 1

        # Minimum bid if participating
        if random_value_fcr <= acceptance_rate_fcr[year]: 
            MMO.addConstr(FCR_Participation[t] * minimum_bid_FCR <= FCR_Volume[t])
            MMO.addConstr(FCR_Volume[t] <= charge_ub * FCR_Participation[t])

        else:  # no participation
            MMO.addConstr(FCR_Volume[t] == 0)

    # ----------------------------------------------------------------------
    # 7. aFRR participation constraints (upward and downward)
    # ----------------------------------------------------------------------

    for t in AFRR_horizon:
        # Random number for activation
        rng = np.random.default_rng(seed=activation_counter + 42)
        random_value_afrr = rng.random()
        activation_counter += 1

        if random_value_afrr <= acceptance_rate_afrr[year]: 
            # Minimum bid if participating for positive (upward) regulation
            MMO.addConstr(AFRR_Participation_Pos[t] * minimum_bid_AFRR <= AFRR_Volume_Pos[t])
            MMO.addConstr(AFRR_Volume_Pos[t] <= charge_ub * AFRR_Participation_Pos[t])

            # Minimum bid if participating for negative (downward) regulation
            MMO.addConstr(AFRR_Participation_Neg[t] * minimum_bid_AFRR <= AFRR_Volume_Neg[t])
            MMO.addConstr(AFRR_Volume_Neg[t] <= charge_ub * AFRR_Participation_Neg[t])

        else:  # no participation
            MMO.addConstr(AFRR_Volume_Pos[t] == 0)
            MMO.addConstr(AFRR_Volume_Neg[t] == 0)

    # ----------------------------------------------------------------------
    # 8. SOC headroom + power headroom constraints
    # ----------------------------------------------------------------------
    for k in range(n_hours):

        # FCR mapping
        f = k // granularity_FCR          # FCR block index (0..17)
        j = k % granularity_FCR           # hour inside the block (0..3)

        # AFRR mapping
        a = k // granularity_AFRR         # AFRR block index (0..2)

        # SOC headroom
        MMO.addConstr(SOC[k] >= soc_min + FCR_Volume[f] * wcs_factor_FCR[j] + AFRR_Volume_Pos[a] * wcs_factor_AFRR)
        MMO.addConstr(SOC[k] <= battery_capacity - FCR_Volume[f] * wcs_factor_FCR[j] - AFRR_Volume_Neg[a] * wcs_factor_AFRR)

        # Power limits
        MMO.addConstr(Discharge[k] + FCR_Volume[f] + AFRR_Volume_Pos[a] <= discharge_ub)
        MMO.addConstr(Charge[k] + FCR_Volume[f] + AFRR_Volume_Neg[a] <= charge_ub)


    # ----------------------------------------------------------------------
    # 9. Daily cycling constraint (limit to 1 full cycle per day)
    # ----------------------------------------------------------------------
    max_daily_cycles = 1
    avg_agg_FCR_discharge = 0.136  # MWh/MW of FCR Volume capacity per 4 hours
    n_days = n_hours // 24  # number of complete 24h days in the horizon
    for d in range(n_days):
        MMO.addConstr(
            quicksum(Discharge[24//granularity_DA * d + t] for t in range(24//granularity_DA))
            + quicksum(avg_agg_FCR_discharge * FCR_Volume[24//granularity_FCR * d + t] for t in range(24//granularity_FCR))
            + AFRR_Volume_Pos[d] * utilization_factor_AFRR * granularity_AFRR
            <= max_daily_cycles * battery_capacity
        ) 

    # ----------------------------------------------------------------------
    # 10. Objective function: DA + FCR + aFRR (cap + activation)
    # ----------------------------------------------------------------------
    DA_term = quicksum(clearing_price_DA[t] * (Discharge[t] - Charge[t]) * granularity_DA for t in range(n_hours))
    FCR_term = quicksum(FCR_Volume[t] * clearing_price_FCR[t] * granularity_FCR for t in FCR_horizon)
    
    AFRR_Pos_Cap_term =  quicksum(AFRR_Volume_Pos[t] * AFRR_Pos_Cap_price[t] * granularity_AFRR for t in AFRR_horizon)
    AFRR_Neg_Cap_term =  quicksum(AFRR_Volume_Neg[t] * AFRR_Neg_Cap_price[t]* granularity_AFRR for t in AFRR_horizon)

    AFRR_Pos_Act_term =  quicksum(utilization_factor_AFRR * AFRR_Volume_Pos[t] * AFRR_Pos_Act_price * granularity_AFRR for t in AFRR_horizon)
    AFRR_Neg_Act_term =  quicksum(utilization_factor_AFRR * AFRR_Volume_Neg[t] * AFRR_Neg_Act_price * granularity_AFRR  for t in AFRR_horizon)


    MMO.setObjective(DA_term + FCR_term + AFRR_Pos_Cap_term + AFRR_Neg_Cap_term + AFRR_Pos_Act_term - AFRR_Neg_Act_term, GRB.MAXIMIZE)
    MMO.optimize()

    # ----------------------------------------------------------------------
    # 11. Extract optimal schedule
    # ----------------------------------------------------------------------
    schedule = {
        "charge": np.array([Charge[t].X for t in range(n_hours)]),
        "discharge": np.array([Discharge[t].X for t in range(n_hours)]),
        "soc": np.array([SOC[t].X for t in range(n_hours + 1)]),
        "fcr_volume": np.array([FCR_Volume[t].X for t in FCR_horizon]),
        "afrr_volume_pos": np.array([AFRR_Volume_Pos[t].X for t in AFRR_horizon]),
        "afrr_volume_neg": np.array([AFRR_Volume_Neg[t].X for t in AFRR_horizon]),
        "afrr_participation_pos": np.array([AFRR_Participation_Pos[t].X for t in AFRR_horizon]),
        "afrr_participation_neg": np.array([AFRR_Participation_Neg[t].X for t in AFRR_horizon]),
    }

    return {
        "objective_value": MMO.ObjVal,
        "schedule": schedule,
        "terminal_soc": schedule["soc"][-1],
    }


def run_receding_horizon_single_year(
    year,
    DA_all,
    FCR_all,
    AFRR_cap_all,
    acceptance_rate_fcr,
    acceptance_rate_afrr,
    *,
    initial_SOC=20,
    granularity_DA=1,
    granularity_FCR=4,
    granularity_AFRR=24,
    SOC_min=1,
    charge_rate_min=0,
    charge_rate_max=10,
    discharge_rate_min=0,
    discharge_rate_max=10,
    efficiency=0.92,
    self_discharge_rate=3e-5,
    minimum_bid_FCR=1,
    wcs_factor_FCR=[0.36, 0.27, 0.18, 0.09],
    wcs_factor_AFRR=1.8,
    time_limit_seconds=300,
    activation_counter=0,
    utilization_factor_AFRR=0.05,
    AFRR_Pos_Act_price=375,
    AFRR_Neg_Act_price=-35,
    minimum_bid_AFRR=5
):
    """
    Run the receding-horizon simulation for a full year using:
        - 72-hour look-ahead optimization windows
        - 24-hour apply intervals
        - DA + FCR + aFRR co-optimization

    Returns:
        Dictionary containing yearly aggregated profits and detailed hourly/daily dataframes.
    """

    # ----------------------------------------------------------------------
    # 1. Extract market data for the given year
    # ----------------------------------------------------------------------
    DA_prices_merged = DA_all[DA_all["timestamp"].dt.year == year].copy()
    merged_FCR = FCR_all[FCR_all["timestamp"].dt.year == year].copy()

    if year not in AFRR_cap_all:
        print(f"[{year}] No aFRR capacity data available.")
        return {
            "year": year,
            "da_profit": 0.0,
            "fcr_revenue": 0.0,
            "afrr_total": 0.0,
            "total_profit": 0.0,
            "profit_df": pd.DataFrame(),
            "dispatch_df": pd.DataFrame(),
        }

    AFRR_Pos_Cap_price = AFRR_cap_all[year]["pos"].copy()
    AFRR_Neg_Cap_price = AFRR_cap_all[year]["neg"].copy()

    if DA_prices_merged.empty:
        print(f"[{year}] No DA data available.")
        return {
            "year": year,
            "da_profit": 0.0,
            "fcr_revenue": 0.0,
            "afrr_total": 0.0,
            "total_profit": 0.0,
            "profit_df": pd.DataFrame(),
            "dispatch_df": pd.DataFrame(),
        }

    # ----------------------------------------------------------------------
    # 2. Receding-horizon simulation setup
    # ----------------------------------------------------------------------
    look_ahead_hours = 72
    apply_hours = 24
    state_soc = initial_SOC

    timestamps = DA_prices_merged["timestamp"]
    start_time = timestamps.min()
    end_time = timestamps.max()

    hourly_rows = []
    daily_rows = []

    current_time = start_time

    # ----------------------------------------------------------------------
    # 3. Rolling window over the full year
    # ----------------------------------------------------------------------
    while current_time + pd.Timedelta(hours=apply_hours) <= end_time:

        horizon_end = current_time + pd.Timedelta(hours=look_ahead_hours)

        # ------------------ DA data for this window ----------------------
        da_block = DA_prices_merged[
            (DA_prices_merged["timestamp"] >= current_time)
            & (DA_prices_merged["timestamp"] < horizon_end)
        ].copy()

        if da_block.empty:
            print(f"Skipping {current_time.date()} — no DA data available.")
            current_time += pd.Timedelta(hours=apply_hours)
            continue

        # ------------------ FCR prices for this window -------------------
        fcr_prices_block = merged_FCR[
            (merged_FCR["timestamp"] >= current_time)
            & (merged_FCR["timestamp"] < horizon_end)
        ].copy()

        # ------------------ aFRR prices (daily block) --------------------
        afrr_pos_prices_block = AFRR_Pos_Cap_price[
            (AFRR_Pos_Cap_price["timestamp"] >= current_time.normalize())
            & (AFRR_Pos_Cap_price["timestamp"] < horizon_end.normalize())
        ]["price"].to_numpy()

        afrr_neg_prices_block = AFRR_Neg_Cap_price[
            (AFRR_Neg_Cap_price["timestamp"] >= current_time.normalize())
            & (AFRR_Neg_Cap_price["timestamp"] < horizon_end.normalize())
        ]["price"].to_numpy()

        # Ensure exactly 3 daily blocks for the 72h horizon
        target_len = look_ahead_hours // granularity_AFRR

        if len(afrr_pos_prices_block) < target_len:
            last = afrr_pos_prices_block[-1]
            afrr_pos_prices_block = np.concatenate(
                [afrr_pos_prices_block, np.full(target_len - len(afrr_pos_prices_block), last)]
            )

        if len(afrr_neg_prices_block) < target_len:
            last = afrr_neg_prices_block[-1]
            afrr_neg_prices_block = np.concatenate(
                [afrr_neg_prices_block, np.full(target_len - len(afrr_neg_prices_block), last)]
            )

        # ------------------ Terminal SOC for last window -----------------
        target_soc = initial_SOC if horizon_end >= end_time else None

        # ------------------------------------------------------------------
        # 4. Solve the 72-hour co-optimization problem
        # ------------------------------------------------------------------
        result = solve_da_fcr_afrr(
            da_block,
            fcr_prices_block,
            state_soc,
            AFRR_Pos_Cap_price=afrr_pos_prices_block,
            AFRR_Neg_Cap_price=afrr_neg_prices_block,
            granularity_DA=granularity_DA,
            granularity_FCR=granularity_FCR,
            battery_capacity=40,
            soc_min=SOC_min,
            charge_rate_bounds=(charge_rate_min, charge_rate_max),
            discharge_rate_bounds=(discharge_rate_min, discharge_rate_max),
            efficiency=efficiency,
            self_discharge_rate=self_discharge_rate,
            minimum_bid_FCR=minimum_bid_FCR,
            wcs_factor_FCR=wcs_factor_FCR,
            wcs_factor_AFRR=wcs_factor_AFRR,
            time_limit_seconds=time_limit_seconds,
            gurobi_output=False,
            terminal_soc_target=target_soc,
            activation_counter=activation_counter,
            year=current_time.year,
            utilization_factor_AFRR=utilization_factor_AFRR,
            acceptance_rate_fcr=acceptance_rate_fcr,
            acceptance_rate_afrr=acceptance_rate_afrr,
            minimum_bid_AFRR=minimum_bid_AFRR,
            AFRR_Pos_Act_price=AFRR_Pos_Act_price,
            AFRR_Neg_Act_price=AFRR_Neg_Act_price
        )

        # Each 24h apply period consumes 6 FCR activation draws
        activation_counter += 6

        # ------------------------------------------------------------------
        # 5. Extract 24-hour schedule and store hourly results
        # ------------------------------------------------------------------
        schedule = result["schedule"]
        soc_profile = schedule["soc"]
        charge = schedule["charge"]
        discharge = schedule["discharge"]
        fcr_volume = schedule["fcr_volume"]
        afrr_volume_pos = schedule["afrr_volume_pos"]
        afrr_volume_neg = schedule["afrr_volume_neg"]
        afrr_part_pos = schedule["afrr_participation_pos"]
        afrr_part_neg = schedule["afrr_participation_neg"]

        n_apply = apply_hours // granularity_DA
        block_apply = da_block.iloc[:n_apply].copy()

        for t in range(n_apply):
            ts = block_apply["timestamp"].iloc[t]
            hourly_rows.append({
                "timestamp": ts,
                "charge_mw": charge[t],
                "discharge_mw": discharge[t],
                "soc_mwh": soc_profile[t + 1],
                "fcr_reserve_mw": fcr_volume[t // granularity_FCR],
                "price_eur_mwh": block_apply["price_eur_mwh"].iloc[t],
                "afrr_volume_pos_mw": afrr_volume_pos[t // granularity_AFRR],
                "afrr_volume_neg_mw": afrr_volume_neg[t // granularity_AFRR],
                "afrr_participation_pos": afrr_part_pos[t // granularity_AFRR],
                "afrr_participation_neg": afrr_part_neg[t // granularity_AFRR],
            })

        # ------------------------------------------------------------------
        # 6. Compute realized 24-hour revenues
        # ------------------------------------------------------------------

        # Day-Ahead revenue
        net_export = discharge[:n_apply] - charge[:n_apply]
        da_profit = float(np.dot(block_apply["price_eur_mwh"].to_numpy(), net_export))

        # FCR revenue (first 6×4h blocks)
        n_fcr_apply = apply_hours // granularity_FCR
        fcr_prices_apply = fcr_prices_block.head(n_fcr_apply)
        fcr_revenue = float(np.dot(fcr_volume[:n_fcr_apply], fcr_prices_apply["Preis"].to_numpy()) * granularity_FCR) \
                      if not fcr_prices_apply.empty else 0.0

        # aFRR revenue
        n_afrr_apply = apply_hours // granularity_AFRR
        afrr_vol_pos_apply = afrr_volume_pos[:n_afrr_apply]
        afrr_vol_neg_apply = afrr_volume_neg[:n_afrr_apply]

        afrr_cap_pos_revenue = float(
            np.dot(afrr_vol_pos_apply, afrr_pos_prices_block[:n_afrr_apply]) * granularity_AFRR
        )
        afrr_cap_neg_revenue = float(
            np.dot(afrr_vol_neg_apply, afrr_neg_prices_block[:n_afrr_apply]) * granularity_AFRR
        )

        afrr_act_pos_revenue = float(
            np.sum(afrr_vol_pos_apply) * granularity_AFRR * utilization_factor_AFRR * AFRR_Pos_Act_price
        )
        afrr_act_neg_revenue = float(
            np.sum(afrr_vol_neg_apply) * granularity_AFRR * utilization_factor_AFRR * AFRR_Neg_Act_price
        )

        afrr_total_revenue = (
            afrr_cap_pos_revenue +
            afrr_cap_neg_revenue +
            afrr_act_pos_revenue +
            afrr_act_neg_revenue
        )

        total_profit = da_profit + fcr_revenue + afrr_total_revenue

        # ------------------------------------------------------------------
        # 7. Store daily results
        # ------------------------------------------------------------------
        daily_rows.append({
            "run_time": current_time,
            "profit_model": result["objective_value"],
            "profit_realized": total_profit,
            "da_profit": da_profit,
            "fcr_revenue": fcr_revenue,
            "afrr_cap_pos": afrr_cap_pos_revenue,
            "afrr_cap_neg": afrr_cap_neg_revenue,
            "afrr_act_pos": afrr_act_pos_revenue,
            "afrr_act_neg": afrr_act_neg_revenue,
            "afrr_total": afrr_total_revenue,
            "terminal_soc": soc_profile[n_apply],
        })

        # ------------------------------------------------------------------
        # 8. Advance horizon forward by 24 hours % update SOC
        # ------------------------------------------------------------------
        state_soc = float(soc_profile[n_apply])
        current_time += pd.Timedelta(hours=apply_hours)

    # ----------------------------------------------------------------------
    # 9. Aggregate yearly results
    # ----------------------------------------------------------------------
    profit_df = pd.DataFrame(daily_rows)
    dispatch_df = pd.DataFrame(hourly_rows)

    da_profit_total = float(profit_df["da_profit"].sum()) if not profit_df.empty else 0.0
    fcr_revenue_total = float(profit_df["fcr_revenue"].sum()) if not profit_df.empty else 0.0
    afrr_revenue_total = float(profit_df["afrr_total"].sum()) if not profit_df.empty else 0.0
    total_profit = float(profit_df["profit_realized"].sum()) if not profit_df.empty else 0.0

    print(f"[{year}] Simulated {len(profit_df)} receding-horizon steps.")
    print(f"[{year}] Total DA + FCR + aFRR profit: {total_profit:,.2f} €")

    return {
        "year": year,
        "da_profit": da_profit_total,
        "fcr_revenue": fcr_revenue_total,
        "afrr_total": afrr_revenue_total,
        "total_profit": total_profit,
        "profit_df": profit_df,
        "dispatch_df": dispatch_df,
    }
