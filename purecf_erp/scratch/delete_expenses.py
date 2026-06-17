# pyrefly: ignore [missing-import]
import odoo
from odoo import api, SUPERUSER_ID

def delete_expenses():
    odoo.tools.config['db_name'] = 'purecf'
    registry = odoo.registry('purecf')
    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})
        expenses = env['purecf.expense'].search([])
        count = len(expenses)
        expenses.unlink()
        print(f"Deleted {count} expense records.")

if __name__ == "__main__":
    delete_expenses()
