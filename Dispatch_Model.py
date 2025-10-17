import numpy as np
import gurobipy as gp
from gurobipy import GRB
from gurobipy import quicksum
from scipy.ndimage import gaussian_filter1d
import matplotlib.pyplot as plt

#Battery Parameters
battery_capacity = 40 #[MWh]
SOC_min = 1 #[Mwh]
charge_rate_min = 0 #[MW]
discharge_rate_min = 0 #[MW]
charge_rate_max = 10 #[MW]
discharge_rate_max = 10 #[MW]
efficiency = 0.99
self_discharge_rate = 0
initial_SOC = 20 #[MWh]

#Market Parameters:
    #DAM:
minimum_bid_DAM = 0.1 #[MW]
granularity_DAM = 1 #hours

#Initialize optimization problem:
MMO = gp.Model("Multi Market Optimization")

#Setup indices for decision variables:
days = 365
DAM_horizon = range(granularity_DAM * 24 * days +1)
bidding_slots_DAM = range(10) #arbitrary number for now, to allow for non-uniform biding
side = ["Buy","Sell"]

#import historical data -> for now random perioid function
raw_noise = np.random.uniform(40, 120, len(DAM_horizon))
clearing_price_DAM = gaussian_filter1d(raw_noise, sigma=12)


#========================================================================================================================================
#Decision Variables:
#========================================================================================================================================

Charge = MMO.addVars(DAM_horizon, vtype=GRB.CONTINUOUS, lb=charge_rate_min, ub=charge_rate_max, name="Battery_Charge [MW]") 
Discharge = MMO.addVars(DAM_horizon, vtype=GRB.CONTINUOUS, lb=discharge_rate_min, ub=discharge_rate_max, name="Battery_Discharge [MW]")
Charging_Indicator = MMO.addVars(DAM_horizon, vtype=GRB.BINARY, name= "Charging_Indicator")

SOC = MMO.addVars(DAM_horizon, vtype=GRB.CONTINUOUS, lb=SOC_min, ub=battery_capacity, name="Battery_State_Of_Charge [MWh]") 

DAM_Bid_Price = MMO.addVars(DAM_horizon, bidding_slots_DAM, side, vtype=GRB.CONTINUOUS, lb=0, name="Day_Ahead_Market_Bid [CHF]")
DAM_Bid_Volume = MMO.addVars(DAM_horizon, bidding_slots_DAM, side, vtype=GRB.CONTINUOUS, lb=0, name="Day_Ahead_Market_Volume [#MW]")
DAM_Bid_Placement = MMO.addVars(DAM_horizon, bidding_slots_DAM, side, vtype=GRB.BINARY, name="Day_Ahead_Market_Bid_Placement")

DAM_Bid_Activation = MMO.addVars(DAM_horizon, bidding_slots_DAM, side, vtype=GRB.BINARY, name="Day_Ahead_Market_Bid_Acceptance")
DAM_Executed_volume = MMO.addVars(DAM_horizon, bidding_slots_DAM, side, vtype=GRB.CONTINUOUS, lb=0, name="Day_Ahead_Market_Executed_Volume [MW]")


#========================================================================================================================================
#Constraints:
#=======================================================================================================================================

#Battery State of Charge Balance 
MMO.addConstr(SOC[0] == initial_SOC)
MMO.addConstr(SOC[max(DAM_horizon)] == initial_SOC)

for t in DAM_horizon[:-1]:
    MMO.addConstr(SOC[t+1] == (1 - self_discharge_rate) * SOC[t] + granularity_DAM * (efficiency * Charge[t] - 1 / efficiency * Discharge[t]))

#Day Ahead Market Constraints
for t in DAM_horizon:
    for slot in bidding_slots_DAM:
        #Cannot buy and sell simultaniously in the same bidding slot 
        MMO.addConstr(DAM_Bid_Placement[t, slot, "Buy"] + DAM_Bid_Placement[t, slot, "Sell"] <= 1)
    
        #Market Clearing
        MMO.addGenConstrIndicator(DAM_Bid_Activation[t, slot, "Buy"], True, DAM_Bid_Price[t , slot, "Buy"] >= clearing_price_DAM[t])
        MMO.addGenConstrIndicator(DAM_Bid_Activation[t, slot, "Buy"], False, DAM_Bid_Price[t , slot, "Buy"] <= clearing_price_DAM[t])
        MMO.addConstr(DAM_Bid_Activation[t, slot, "Buy"] <= DAM_Bid_Placement[t, slot, "Buy"])

        MMO.addGenConstrIndicator(DAM_Bid_Activation[t, slot, "Sell"], False, DAM_Bid_Price[t, slot, "Sell"] >= clearing_price_DAM[t])
        MMO.addGenConstrIndicator(DAM_Bid_Activation[t, slot, "Sell"], True, DAM_Bid_Price[t, slot, "Sell"] <= clearing_price_DAM[t])
        MMO.addConstr(DAM_Bid_Activation[t, slot, "Sell"] <= DAM_Bid_Placement[t, slot, "Sell"])

        for s in side:
            #Enfore minimum bidding volume
            MMO.addConstr(DAM_Bid_Placement[t, slot, s] * minimum_bid_DAM <= DAM_Bid_Volume[t, slot, s])
            #Extract Executed Volume 
            MMO.addGenConstrIndicator(DAM_Bid_Activation[t, slot, s], True, DAM_Executed_volume[t, slot, s] == DAM_Bid_Volume[t, slot, s])
            MMO.addGenConstrIndicator(DAM_Bid_Activation[t, slot, s], False, DAM_Executed_volume[t, slot, s] == 0)


for t in DAM_horizon:
    #Link the executed bids to the battery dispatch
    MMO.addConstr(Discharge[t] == quicksum(DAM_Executed_volume[t, slot, "Sell"] for slot in bidding_slots_DAM))
    MMO.addConstr(Charge[t] == quicksum(DAM_Executed_volume[t, slot, "Buy"] for slot in bidding_slots_DAM))

    #Prevent simultanious charging and discharging
    MMO.addGenConstrIndicator(Charging_Indicator[t], True,  Discharge[t] == 0)
    MMO.addGenConstrIndicator(Charging_Indicator[t], False,  Charge[t] == 0)

#========================================================================================================================================
#Objective Function and solving:
#=======================================================================================================================================
Profit = quicksum(clearing_price_DAM[t] * Discharge[t] - clearing_price_DAM[t] * Charge[t] for t in DAM_horizon)

#Solve Optimization Problem
MMO.setObjective(Profit, GRB.MAXIMIZE)
MMO.setParam('TimeLimit', 60) 
MMO.optimize()

print(f"Maximum Profit: {MMO.ObjVal}")


#Plotting:

soc_values = [SOC[t].X for t in DAM_horizon]
time_axis = np.arange(len(DAM_horizon))

# Plot
plt.figure(figsize=(10, 4))
plt.plot(time_axis, soc_values, label='State of Charge', linewidth=2)
plt.xlabel('Hour')
plt.ylabel('State of Charge [MWh]')
plt.title('Battery State of Charge Over Day-Ahead Horizon')
plt.grid(True, linestyle='--', alpha=0.6)
plt.legend()
plt.tight_layout()
plt.show()