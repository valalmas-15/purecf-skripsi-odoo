from collections import Counter

# Check standard Odoo POS Payment Methods
print("--- Standard Odoo POS Payments ---")
payments = self.env['pos.payment'].search([])
methods = [p.payment_method_id.name for p in payments]
counts = Counter(methods)
for method, count in counts.items():
    print(f"{method}: {count}")

# Check custom x_payment_method field in pos.order
print("\n--- Custom x_payment_method field in pos.order ---")
orders = self.env['pos.order'].search([('x_payment_method', '!=', False)])
x_methods = [o.x_payment_method for o in orders]
x_counts = Counter(x_methods)
for method, count in x_counts.items():
    print(f"{method}: {count}")

# Check all payment methods configured
print("\n--- Configured Payment Methods (pos.payment.method) ---")
all_methods = self.env['pos.payment.method'].search([])
for m in all_methods:
    print(f"- {m.name} (ID: {m.id})")
