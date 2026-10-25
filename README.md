# Real Exchange Rate (RER) Analyzer

A modern, minimal Python web application that dynamically calculates and plots the Real and Nominal Exchange rates between countries using IMF Data (SDMX 3.0 API).

## Application Features
- **Dynamic IMF Extraction**: Queries monthly Consumer Price Index (CPI) and Nominal Exchange rate data dynamically starting from January 1976.
- **On-the-Fly Mathematics**:
  - Automatically calculates $S(t)$, transforming local currency units into Country 2 per Country 1 currency structures.
  - Computes the dynamic $RER(t)$ equation: $S(t) \times [P_1(t) / P_2(t)]$.
  - Generates the `Real Index(t)` anchored dynamically based on user-selected time boundaries (automatically recalculating $RER^*$).
- **Dual-Axis Charting**: Select between viewing Real, Nominal, or a dual-axis combination using robust, interactive Plotly visualizations. 
- **CSV Data Download**: Export all parameters and calculation observations directly to a CSV within the selected sample window.

## Requirements
- Python 3.12 
- See `requirements.txt` for standard dependencies.

## Quickstart

1. Install dependencies from the terminal:
   ```bash
   pip install -r requirements.txt
