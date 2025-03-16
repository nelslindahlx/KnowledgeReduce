import json

# Load the notebook
with open('CivicHonorsKGv18.ipynb', 'r') as f:
    notebook = json.load(f)

# Extract code cells for detailed analysis
code_cells = [cell for cell in notebook['cells'] if cell['cell_type'] == 'code']

# Print full content of each code cell with a header
for i, cell in enumerate(code_cells):
    print(f"\n{'='*80}\nCODE CELL {i+1}\n{'='*80}")
    source = ''.join(cell['source'])
    print(source)
