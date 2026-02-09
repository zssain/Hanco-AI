"""
Updated compute_vehicle_price function with production pricing logic.

This file contains the complete replacement for the compute_vehicle_price function
in backend/app/api/v1/pricing.py (starting at line 434).

To apply:
1. Open backend/app/api/v1/pricing.py
2. Find the compute_vehicle_price function (line 434)
3. Replace the entire function (lines 434-577) with the code below
"""

async def compute_vehicle_price(
    vehicle: VehicleQuoteInput,
    branch_key: str,
    duration_days: int,
    duration_key: str,
    pickup_date: date,
    is_weekend: bool,
    market_stats: Optional[Dict[str, float]],
    weather_defaults: Dict[str, float]
) -> Dict[str, Any]:
    """
    Production pricing logic per vehicle with full ML + Rule blending.
    
    Pipeline:
    1. Check cache (30min TTL)
    2. Build ONNX features → ml_price_per_day
    3. Compute rule_price_per_day with duration discounts + airport/weekend premiums
    4. Compute floor (cost * 1.15 or base * 0.8)
    5. Compute ceiling (market p90 * 1.15 or base * 2.0)
    6. Blend: 60% rule + 40% ML
    7. Clamp to [floor, ceiling]
    8. Round to nearest 1 SAR (or 5 SAR if >50)
    9. Final total = daily * duration + add_ons
    10. Log decision + write cache
    
    Returns: {vehicle_id, daily_price, total_price, breakdown, cached}
    """
    try:
        # ============ Step 1: Check Cache ============
        cached_data = await check_pricing_cache(
            branch_key=branch_key,
            vehicle_id=vehicle.vehicle_id,
            pickup_date=pickup_date,
            duration_key=duration_key
        )
        
        if cached_data:
            return {
                'vehicle_id': vehicle.vehicle_id,
                'daily_price': cached_data['final_price_per_day'],
                'total_price': cached_data['total_price'],
                'breakdown': cached_data.get('breakdown', {}),
                'cached': True
            }
        
        # ============ Step 2: Build ONNX Features ============
        # Get competitor average price
        avg_competitor_price = float(vehicle.base_daily_rate)
        if market_stats and market_stats.get('median') is not None:
            avg_competitor_price = float(market_stats['median'])
        
        # Compute demand index with real-time signals
        demand_index = compute_demand_index(
            branch_key=branch_key,
            class_bucket=vehicle.class_bucket,
            pickup_date=pickup_date
        )
        
        # FEATURE_ORDER: rental_length_days, day_of_week, month, base_daily_rate,
        #                avg_temp, rain, wind, avg_competitor_price, demand_index, bias
        features = {
            'rental_length_days': float(duration_days),
            'day_of_week': float(pickup_date.weekday()),
            'month': float(pickup_date.month),
            'base_daily_rate': float(vehicle.base_daily_rate),
            'avg_temp': float(weather_defaults['avg_temp']),
            'rain': float(weather_defaults['rain']),
            'wind': float(weather_defaults['wind']),
            'avg_competitor_price': float(avg_competitor_price),
            'demand_index': float(demand_index),
            'bias': 1.0
        }
        
        # Get ML price from ONNX model
        ml_price_per_day = float(predict_price(features))
        
        # ============ Step 3: Rule-Based Price with Discounts/Premiums ============
        rule_price_per_day = float(vehicle.base_daily_rate)
        discounts_applied = {}
        premiums_applied = {}
        
        # Duration discounts (match durationKey: D3, D7, M1)
        if duration_key == "M1":  # 30+ days
            discount = 0.15
            rule_price_per_day *= (1 - discount)
            discounts_applied['duration_M1'] = discount
        elif duration_key == "D7":  # 7-29 days
            discount = 0.07
            rule_price_per_day *= (1 - discount)
            discounts_applied['duration_D7'] = discount
        elif duration_key == "D3":  # 3-6 days
            discount = 0.03
            rule_price_per_day *= (1 - discount)
            discounts_applied['duration_D3'] = discount
        # D1 (1-2 days) = no discount
        
        # Airport premium (+5%)
        if vehicle.branch_type and vehicle.branch_type.lower() == "airport":
            premium = 0.05
            rule_price_per_day *= (1 + premium)
            premiums_applied['airport'] = premium
        
        # Saudi weekend premium (+3% on Friday/Saturday)
        if is_weekend:
            premium = 0.03
            rule_price_per_day *= (1 + premium)
            premiums_applied['weekend'] = premium
        
        # ============ Step 4: Compute Floor ============
        if vehicle.cost_per_day and vehicle.cost_per_day > 0:
            floor_price = vehicle.cost_per_day * 1.15  # 15% margin over cost
        else:
            floor_price = vehicle.base_daily_rate * 0.80  # 80% of base
        
        # ============ Step 5: Compute Ceiling ============
        if market_stats and market_stats.get('p90') is not None:
            ceiling_price = market_stats['p90'] * 1.15  # 15% above market p90
        else:
            ceiling_price = vehicle.base_daily_rate * 2.0  # 2x base as fallback
        
        # ============ Step 6: Blend ML + Rule (60% rule, 40% ML) ============
        blended_price = (0.6 * rule_price_per_day) + (0.4 * ml_price_per_day)
        
        # ============ Step 7: Clamp to [floor, ceiling] ============
        final_price_per_day = max(floor_price, min(blended_price, ceiling_price))
        
        # ============ Step 8: Round to Nearest 1 or 5 SAR ============
        # Round to nearest 1 SAR for prices < 50, otherwise nearest 5 SAR
        if final_price_per_day < 50:
            final_price_per_day = round(final_price_per_day)
        else:
            final_price_per_day = round(final_price_per_day / 5) * 5
        
        # ============ Step 9: Compute Final Total ============
        # Note: add_ons can be added here in future (insurance, GPS, child seat, etc.)
        add_ons_total = 0.0  # Placeholder for future add-ons
        final_total = (final_price_per_day * duration_days) + add_ons_total
        
        # ============ Breakdown for Transparency ============
        breakdown = {
            'base_daily_rate': round(vehicle.base_daily_rate, 2),
            'ml_price_per_day': round(ml_price_per_day, 2),
            'rule_price_per_day': round(rule_price_per_day, 2),
            'blended_price': round(blended_price, 2),
            'floor': round(floor_price, 2),
            'ceiling': round(ceiling_price, 2),
            'final_price_per_day': round(final_price_per_day, 2),
            'duration_days': duration_days,
            'subtotal': round(final_price_per_day * duration_days, 2),
            'add_ons': round(add_ons_total, 2),
            'final_total': round(final_total, 2),
            'discounts': discounts_applied,
            'premiums': premiums_applied,
            'demand_index': round(demand_index, 3),
            'avg_competitor_price': round(avg_competitor_price, 2),
            'market_stats_used': market_stats is not None and market_stats.get('count', 0) > 0
        }
        
        # ============ Step 10: Write Decision Log ============
        decision_id = str(uuid.uuid4())
        await write_pricing_decision(
            decision_id=decision_id,
            vehicle_id=vehicle.vehicle_id,
            branch_key=branch_key,
            class_bucket=vehicle.class_bucket,
            duration_days=duration_days,
            duration_key=duration_key,
            market_stats=market_stats,
            features=features,
            ml_price=ml_price_per_day,
            rule_price=rule_price_per_day,
            blended_price=blended_price,
            final_price=final_price_per_day,
            floor_price=floor_price,
            ceiling_price=ceiling_price,
            model_version="onnx_v1_production",
            discounts_applied=discounts_applied,
            premiums_applied=premiums_applied
        )
        
        # ============ Write Cache (30min TTL) ============
        await write_pricing_cache(
            branch_key=branch_key,
            vehicle_id=vehicle.vehicle_id,
            pickup_date=pickup_date,
            duration_key=duration_key,
            final_price_per_day=final_price_per_day,
            total_price=final_total,
            currency="SAR",
            breakdown=breakdown,
            model_version="onnx_v1_production",
            competitor_median=market_stats.get('median') if market_stats else None
        )
        
        return {
            'vehicle_id': vehicle.vehicle_id,
            'daily_price': final_price_per_day,
            'total_price': final_total,
            'breakdown': breakdown,
            'cached': False
        }
        
    except Exception as e:
        logger.error(f"Error computing price for vehicle {vehicle.vehicle_id}: {str(e)}")
        # Fallback to base rate with minimal markup
        fallback_price = vehicle.base_daily_rate
        fallback_total = fallback_price * duration_days
        return {
            'vehicle_id': vehicle.vehicle_id,
            'daily_price': fallback_price,
            'total_price': fallback_total,
            'breakdown': {
                'error': str(e), 
                'fallback': fallback_price,
                'fallback_total': fallback_total
            },
            'cached': False
        }
