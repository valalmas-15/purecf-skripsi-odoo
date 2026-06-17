import logging
logging.basicConfig(level=logging.INFO)

try:
    session = env['pos.session'].sudo().browse(40)
    session.write({
        'cash_register_balance_start': 100000.0,
        'cash_register_balance_end_real': 90000.0,
        'state': 'closed'
    })
    
    print(f"=========================================")
    print(f"SUCCESS: Updated Session ID 40")
    print(f"Start: {session.cash_register_balance_start}")
    print(f"End Real: {session.cash_register_balance_end_real}")
    print(f"End Theo: {session.cash_register_balance_end}")
    print(f"Difference: {session.cash_register_difference}")
    print(f"=========================================")
    env.cr.commit()
    
    # Try updating directly in sql
    env.cr.execute("UPDATE pos_session SET cash_register_balance_start=100000.0, cash_register_balance_end_real=90000.0 WHERE id=40")
    env.cr.commit()
except Exception as e:
    print(f"ERROR: {e}")
    env.cr.rollback()
