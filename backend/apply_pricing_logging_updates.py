"""
Script to apply the required pricing decision logging updates.
"""

# Read the file
with open('app/api/v1/pricing.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replacement 1: Update write_pricing_decision call
content = content.replace(
    'await write_pricing_decision(\n            decision_id=decision_id,\n            vehicle_id=vehicle.vehicle_id,\n            branch_key=branch_key,\n            class_bucket=vehicle.class_bucket,\n            duration_days=duration_days,\n            duration_key=duration_key,\n            market_stats=market_stats,\n            features=features,\n            ml_price=ml_price_per_day,\n            rule_price=rule_price,\n            blended_price=blended_price,\n            final_price=final_price,\n            floor_price=floor_price,\n            ceiling_price=ceiling_price,\n            model_version="onnx_v1",\n            discounts_applied=discounts_applied,\n            premiums_applied=premiums_applied\n        )',
    'await write_pricing_decision(\n            decision_id=decision_id,\n            vehicle_id=vehicle.vehicle_id,\n            vehicle_name=getattr(vehicle, \'vehicle_name\', None),\n            branch_key=branch_key,\n            branch_type=vehicle.branch_type or "City",\n            city=branch_key,\n            pickup_at=pickup_at,\n            dropoff_at=dropoff_at,\n            class_bucket=vehicle.class_bucket,\n            duration_days=duration_days,\n            duration_key=duration_key,\n            base_daily_rate=vehicle.base_daily_rate,\n            cost_per_day=vehicle.cost_per_day,\n            market_stats=market_stats,\n            features=features,\n            ml_price=ml_price_per_day,\n            rule_price=rule_price,\n            blended_price=blended_price,\n            final_price=final_price,\n            floor_price=floor_price,\n            ceiling_price=ceiling_price,\n            model_version="onnx_v1",\n            discounts_applied=discounts_applied,\n            premiums_applied=premiums_applied,\n            cache_hit=False\n        )'
)
print("✓ Updated write_pricing_decision call")

# Replacement 2: Update compute_vehicle_price call  
content = content.replace(
    'task = compute_vehicle_price(\n                vehicle=vehicle,\n                branch_key=request.branch_key,\n                duration_days=duration_days,\n                duration_key=duration_key,\n                pickup_date=pickup_date,\n                is_weekend=is_weekend,\n                market_stats=market_stats,\n                weather_defaults=weather_defaults\n            )',
    'task = compute_vehicle_price(\n                vehicle=vehicle,\n                branch_key=request.branch_key,\n                pickup_at=request.pickup_at,\n                dropoff_at=request.dropoff_at,\n                duration_days=duration_days,\n                duration_key=duration_key,\n                pickup_date=pickup_date,\n                is_weekend=is_weekend,\n                market_stats=market_stats,\n                weather_defaults=weather_defaults\n            )'
)
print("✓ Updated compute_vehicle_price call")

# Write the updated file
with open('app/api/v1/pricing.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("\n✅ Successfully applied pricing decision logging updates!")
