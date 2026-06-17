expenses = env['purecf.expense'].search([])
print(f"Total expenses in Odoo: {len(expenses)}")
for exp in sorted(expenses, key=lambda e: (e.date, e.amount)):
    print(exp.id, exp.date, exp.amount, exp.note)
