import numpy as np
import gurobipy as gp
from gurobipy import GRB
from gurobipy import quicksum

#Decision Variables:

#Constraints:

#Initialize optimization problem:
MMO = gp.Model("Multi Market Optimization")

days = 365
total_hours = days * 24
Horizon = range(total_hours + 1)

Charge = MMO.addVars(Horizon, vtype=GRB.CONTINUOUS, lb=0, ub=10 name="Battery_Charge [MW]") 
Discharge = MMO.addVars(Horizon, vtype=GRB.CONTINUOUS, lb=0, ub=10, name="Battery_Discharge [MW]")
SOC = MMO.addVars(Horizon, vtype=GRB.CONTINUOUS, lb=0, ub=40, name="Battery_Discharge [MWh]") 