import logging
logging.basicConfig(level=logging.INFO)

try:
    admin_id = env['res.users'].search([('login', '=', 'admin')], limit=1).id or 2

    # Create a new POS Config for testing
    pos_config = env['pos.config'].sudo().create({
        'name': 'Toko Cabang Baru (Testing)',
    })
    
    # Find a product
    product = env['product.product'].search([('available_in_pos', '=', True)], limit=1)
    if not product:
        product = env['product.product'].search([], limit=1)
        product.available_in_pos = True
    
    # Find cash payment method
    payment_method = env['pos.payment.method'].search([('is_cash_count', '=', True)], limit=1)
    if not payment_method:
        payment_method = env['pos.payment.method'].search([], limit=1)
    
    # We must add payment method to config BEFORE opening session
    pos_config.write({'payment_method_ids': [(4, payment_method.id)]})

    # Create a new session
    session = env['pos.session'].sudo().create({
        'config_id': pos_config.id,
        'user_id': admin_id,
        'cash_register_balance_start': 500000.0,
    })
    session.action_pos_session_open()

    # Create POS Order
    order = env['pos.order'].sudo().create({
        'session_id': session.id,
        'amount_total': 150000.0,
        'amount_tax': 0.0,
        'amount_paid': 150000.0,
        'amount_return': 0.0,
        'lines': [(0, 0, {
            'product_id': product.id,
            'qty': 1,
            'price_unit': 150000.0,
            'price_subtotal': 150000.0,
            'price_subtotal_incl': 150000.0,
        })],
    })
    
    # Create Payment
    env['pos.payment'].sudo().create({
        'pos_order_id': order.id,
        'payment_method_id': payment_method.id,
        'amount': 150000.0,
        'session_id': session.id,
    })
    
    order.action_pos_order_paid()
    
    # Expected cash: 500k + 150k = 650k
    # We set actual to 600k to create a 50k missing anomaly
    session.sudo().write({'cash_register_balance_end_real': 600000.0})
    
    # Close session
    session.action_pos_session_closing_control()
    
    print(f"=========================================")
    print(f"SUCCESS: Created Toko Cabang Baru (Testing)")
    print(f"Session ID: {session.id}")
    print(f"Expected: 650000.0")
    print(f"Actual: 600000.0")
    print(f"Difference: {session.cash_register_difference}")
    print(f"=========================================")
    env.cr.commit()
except Exception as e:
    print(f"ERROR: {e}")
    env.cr.rollback()
