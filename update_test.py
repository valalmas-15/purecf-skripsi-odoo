import logging
logging.basicConfig(level=logging.INFO)

try:
    session = env['pos.session'].sudo().browse(40)
    session.write({
        'cash_register_balance_end_real': 90000.0,
        'state': 'closed'
    })
    
    print(f"=========================================")
    print(f"SUCCESS: Updated Session ID 40")
    print(f"End Real: {session.cash_register_balance_end_real}")
    print(f"Difference: {session.cash_register_difference}")
    print(f"=========================================")
    env.cr.commit()
except Exception as e:
    print(f"ERROR: {e}")
    env.cr.rollback()
