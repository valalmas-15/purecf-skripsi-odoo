import logging
try:
    env.cr.execute("UPDATE pos_session SET cash_register_difference = -10000.0, state = 'closed' WHERE id=40")
    env.cr.commit()
    print("SUCCESS")
except Exception as e:
    print(f"ERROR: {e}")
    env.cr.rollback()
