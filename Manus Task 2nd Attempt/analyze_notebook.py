import json

# Load the notebook
with open('CivicHonorsKGv18.ipynb', 'r') as f:
    notebook = json.load(f)

# Analyze structure
print(f"Number of cells: {len(notebook['cells'])}")

# Count cell types
cell_types = {}
for cell in notebook['cells']:
    cell_type = cell['cell_type']
    cell_types[cell_type] = cell_types.get(cell_type, 0) + 1

print("\nCell types:")
for cell_type, count in cell_types.items():
    print(f"- {cell_type}: {count}")

# Extract code cells to understand structure
print("\nCode structure:")
code_cells = [cell for cell in notebook['cells'] if cell['cell_type'] == 'code']
for i, cell in enumerate(code_cells):
    source = ''.join(cell['source']).strip()
    if source:
        first_line = source.split('\n')[0]
        print(f"Cell {i+1}: {first_line[:100]}...")
