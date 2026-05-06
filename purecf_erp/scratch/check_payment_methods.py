import os
import sys

# Add Odoo path if necessary, but here we likely just want to run a script that uses the Odoo environment
# Since I can't easily run a script with 'odoo shell' non-interactively without more setup,
# I will try to find existing scripts in the scratch directory to see how they are executed.

def list_scratch():
    print("Files in scratch:")
    for f in os.listdir('/Users/alle/Projects/Odoo17/purecf_erp/scratch'):
        print(f" - {f}")

list_scratch()
