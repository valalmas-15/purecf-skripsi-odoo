from datetime import date
analysis = env['purecf.stock.usage.analysis'].create({
    'date_from': date(2024, 4, 1),
    'date_to': date(2024, 4, 30)
})
data = analysis.get_usage_data(analysis.date_from, analysis.date_to)
for d in data:
    if d['stock_in'] > 0:
        print(f"{d['ingredient_name']} : {d['stock_in']}")
