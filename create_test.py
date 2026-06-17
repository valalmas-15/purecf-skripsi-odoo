import logging
logging.basicConfig(level=logging.INFO)

try:
    admin_id = env['res.users'].search([('login', '=', 'admin')], limit=1).id or 2

    # Create a new POS Config for testing
    pos_config = env['pos.config'].sudo().create({
        'name': 'Cabang Testing Anomali',
    })
    
    # Create a new session
    session = env['pos.session'].sudo().create({
        'config_id': pos_config.id,
        'user_id': admin_id,
        'cash_register_balance_start': 100000.0,
    })
    
    # Open the session
    session.action_pos_session_open()
    
    # Add an order just in case? Not strictly needed for difference, but lets do it if needed.
    
    # Set the actual cash balance to a different amount to simulate anomaly
    session.sudo().write({'cash_register_balance_end_real': 90000.0})
    
    # Close the session
    session.action_pos_session_closing_control()
    
    print(f"=========================================")
    print(f"SUCCESS: Created POS Config ID {pos_config.id}")
    print(f"SUCCESS: Created Session ID {session.id} with difference {session.cash_register_difference}")
    print(f"=========================================")
    env.cr.commit()
except Exception as e:
    print(f"ERROR: {e}")
    env.cr.rollback()
