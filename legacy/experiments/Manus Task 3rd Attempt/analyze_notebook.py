#!/usr/bin/env python3
import json

# Load the notebook
with open('CivicHonorsKGv18.ipynb', 'r') as f:
    notebook = json.load(f)

# Extract code cells
code_cells = [cell for cell in notebook['cells'] if cell['cell_type'] == 'code']
print(f"Total code cells: {len(code_cells)}")

# Print first few code cells
for i, cell in enumerate(code_cells[:5]):
    print(f"\n--- CODE CELL {i+1} ---")
    print(''.join(cell['source']))
