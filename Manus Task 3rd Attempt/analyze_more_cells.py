#!/usr/bin/env python3
import json

# Load the notebook
with open('CivicHonorsKGv18.ipynb', 'r') as f:
    notebook = json.load(f)

# Extract code cells
code_cells = [cell for cell in notebook['cells'] if cell['cell_type'] == 'code']
print(f"Total code cells: {len(code_cells)}")

# Print more code cells to understand data cleaning and advanced techniques
for i, cell in enumerate(code_cells[5:10]):
    print(f"\n--- CODE CELL {i+6} ---")
    print(''.join(cell['source']))
