# Previous Versions of the Dispatch Model

This folder contains older but fully functional versions of the BESS dispatch optimization notebook.  
They are retained for reference and for use in specific analyses where a simplified modelling scope is preferred.

Each version reflects an incremental step in the model development process, with different combinations of market participation and operational constraints.

---

## 1. Version Overview

### **v1_Optimal_Dispatch_Model_DA_only.ipynb**
- Includes **Day-Ahead (DA)** market participation only.  
- Useful for benchmarking or isolating DA-only revenue streams.

### **v2_Optimal_Dispatch_Model_DA_FCR_rolling.ipynb**
- Adds **FCR capacity bidding** with a rolling-horizon implementation.  
- No aFRR modelling included yet.  
- Suitable for DA + FCR revenue comparisons or simplified multi-service scenarios.

### **v3_Optimal_Dispatch_Model_DA_FCR_activation_rolling.ipynb**
- Adds **activation energy** modelling for FCR and improved rolling-horizon logic.  

Those functions are all succesfully implemented in the final version of the BESS dispatch model: 
### **Optimal_Dispatch_Model.ipynb**