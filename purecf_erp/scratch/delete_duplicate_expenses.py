# Delete all imported April expenses to start fresh
dates = ['2026-04-07 10:00:00', '2026-04-14 10:00:00', '2026-04-21 10:00:00', '2026-04-28 10:00:00']
old_expenses = env['purecf.expense'].search([
    ('note', '=like', '[Bahan Baku] Pembelian %'),
    ('date', 'in', dates)
])
print(f"Deleting {len(old_expenses)} duplicate/old April expenses...")
old_expenses.unlink()
env.cr.commit()
print("Cleanup complete.")
