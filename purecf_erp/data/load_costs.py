
# Data Ingredient Costs with XML ID mapping
ingredient_data = [
    ("purecf_erp.ing_beans", 175),
    ("purecf_erp.ing_creamer", 46),
    ("purecf_erp.ing_uht", 18.42),
    ("purecf_erp.ing_matcha_powder", 257),
    ("purecf_erp.ing_chocolate_powder", 170),
    ("purecf_erp.ing_redvelvet_powder", 55),
    ("purecf_erp.ing_palme_liquid", 117.3),
    ("purecf_erp.ing_scothcie_liquid", 126.7),
    ("purecf_erp.ing_vanille_liquid", 138.7),
    ("purecf_erp.ing_shaka_liquid", 142.7),
    ("purecf_erp.ing_monkist_liquid", 142.7),
    ("purecf_erp.ing_rume_liquid", 148),
    ("purecf_erp.ing_nutty_liquid", 141.3),
    ("purecf_erp.ing_cup_ice", 860),
    ("purecf_erp.ing_cup_hot", 860),
    ("purecf_erp.ing_beras", 15),
    ("purecf_erp.ing_telur", 1733.3),
    ("purecf_erp.ing_dada_ayam", 30),
    ("purecf_erp.ing_indomie_goreng", 2750),
    ("purecf_erp.ing_indomie_kuah", 2925),
    ("purecf_erp.ing_kwetiaw", 53),
    ("purecf_erp.ing_bawang_putih", 50),
    ("purecf_erp.ing_tomat", 10),
    ("purecf_erp.ing_timun", 10),
    ("purecf_erp.ing_sawi", 10),
    ("purecf_erp.ing_sedotan", 52),
    ("purecf_erp.ing_puremilk", 20),
    ("purecf_erp.ing_skm", 15),
    ("purecf_erp.ing_air_kelapa", 10),
    ("purecf_erp.ing_mineral_water", 1.5),
    ("purecf_erp.ing_sparkling_soda", 25),
    ("purecf_erp.ing_orange_juice", 35),
    ("purecf_erp.ing_saos_tiram", 60),
    ("purecf_erp.ing_kecap", 40),
    ("purecf_erp.ing_minyak", 18),
    ("purecf_erp.ing_selasih", 100),
    ("purecf_erp.ing_cabe_giling", 80),
    ("purecf_erp.ing_udang_rebon", 120),
    ("purecf_erp.ing_nasi_putih", 15),
    ("purecf_erp.ing_masako", 50),
    ("purecf_erp.ing_micin", 40),
    ("purecf_erp.ing_garam", 10),
    ("purecf_erp.ing_cumi", 90),
    ("purecf_erp.ing_udang", 110),
    ("purecf_erp.ing_bumbu_soto", 70),
    ("purecf_erp.ing_cabe_keriting", 60),
    ("purecf_erp.ing_mie_kwetiau", 25),
    ("purecf_erp.ing_tepung_terigu", 14),
    ("purecf_erp.ing_ladaku", 200),
    ("purecf_erp.ing_segitiga_biru", 15),
    ("purecf_erp.ing_bawang_merah", 45),
    ("purecf_erp.ing_cabe_setan", 75),
    ("purecf_erp.ing_elder_liquid", 140),
    ("purecf_erp.ing_blue_lagoon_liquid", 140),
    ("purecf_erp.ing_lemon_based", 130),
    ("purecf_erp.ing_lychee_based", 130),
    ("purecf_erp.ing_lemon_liquid", 130),
    ("purecf_erp.ing_lychee_liquid", 130),
    ("purecf_erp.ing_dryed_lemon", 2000),
    ("purecf_erp.ing_lemon_fruit", 3000),
    ("purecf_erp.ing_lychee_fruit", 2500),
    ("purecf_erp.ing_es_batu", 500),
    ("purecf_erp.ing_espresso", 3500),
]

print("--- Updating Ingredient Costs using XML IDs ---")
for xml_id, cost in ingredient_data:
    try:
        product = env.ref(xml_id)
        product.write({'standard_price': cost})
        print(f"Success: {xml_id} -> {cost}")
    except Exception as e:
        print(f"Error updating {xml_id}: {e}")

env.cr.commit()

print("\n--- Recomputing Product Costs from BoM ---")
# Cari semua product template yang punya BoM
boms = env['mrp.bom'].search([])
products_to_update = boms.mapped('product_tmpl_id')

for product in products_to_update:
    try:
        # Method button_bom_cost menghitung cost berdasarkan komponen di BoM
        product.button_bom_cost()
        print(f"Recomputed Cost for: {product.name} -> {product.standard_price}")
    except Exception as e:
        print(f"Error computing cost for {product.name}: {e}")

env.cr.commit()
print("\n--- DONE ---")
