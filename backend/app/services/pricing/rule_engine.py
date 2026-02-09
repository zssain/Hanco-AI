"""
Pricing Rule Engine
Applies business rules and guardrails on top of ML baseline predictions
"""
from typing import Dict, List, Optional, Tuple
from datetime import date, datetime
from dataclasses import dataclass, field


@dataclass
class PricingFactors:
    """Input factors for pricing calculation"""
    baseline_price_ml: float
    base_daily_rate: float
    rental_length_days: int
    lead_time_days: int
    utilization_rate: float
    demand_index: float
    avg_competitor_price: float
    day_of_week: int  # 0=Monday, 6=Sunday
    month: int  # 1-12
    hour_of_booking: Optional[int] = None  # 0-23
    last_quoted_price: Optional[float] = None


@dataclass
class PricingResult:
    """Output of pricing calculation"""
    final_price_per_day: float
    baseline_price: float
    factors_applied: Dict[str, float]
    guardrails_applied: List[str]
    price_breakdown: Dict[str, float]


class PricingRuleEngine:
    """
    Business rule engine for dynamic pricing
    Applies factors and guardrails to ML baseline predictions
    """
    
    def __init__(
        self,
        min_margin: float = 0.15,  # 15% minimum margin over cost
        max_ceiling_multiplier: float = 3.0,  # 3x base rate max
        competitor_band_tolerance: float = 0.20,  # ±20% of competitor avg
        max_rate_change: float = 0.08,  # ±8% max change from last price
        smoothing_alpha: float = 0.3  # Exponential smoothing weight
    ):
        self.min_margin = min_margin
        self.max_ceiling_multiplier = max_ceiling_multiplier
        self.competitor_band_tolerance = competitor_band_tolerance
        self.max_rate_change = max_rate_change
        self.smoothing_alpha = smoothing_alpha
    
    def calculate_price(self, factors: PricingFactors) -> PricingResult:
        """
        Calculate final price with all business rules applied
        
        Args:
            factors: Input pricing factors
            
        Returns:
            PricingResult with final price and breakdown
        """
        # Start with ML baseline
        current_price = factors.baseline_price_ml
        baseline_price = factors.baseline_price_ml
        
        factors_applied = {}
        guardrails_applied = []
        breakdown = {
            'baseline_ml': baseline_price
        }
        
        # === APPLY FACTORS ===
        
        # 1. Utilization factor (high utilization = higher price)
        utilization_factor = self._calculate_utilization_factor(factors.utilization_rate)
        current_price *= utilization_factor
        factors_applied['utilization'] = utilization_factor
        breakdown['after_utilization'] = current_price
        
        # 2. Lead time factor (last-minute bookings = premium)
        lead_time_factor = self._calculate_lead_time_factor(factors.lead_time_days)
        current_price *= lead_time_factor
        factors_applied['lead_time'] = lead_time_factor
        breakdown['after_lead_time'] = current_price
        
        # 3. Duration discount (longer rentals = discount)
        duration_factor = self._calculate_duration_discount(factors.rental_length_days)
        current_price *= duration_factor
        factors_applied['duration'] = duration_factor
        breakdown['after_duration'] = current_price
        
        # 4. Late-night premium (bookings after 10pm or before 6am)
        if factors.hour_of_booking is not None:
            late_night_factor = self._calculate_late_night_premium(factors.hour_of_booking)
            current_price *= late_night_factor
            factors_applied['late_night'] = late_night_factor
            breakdown['after_late_night'] = current_price
        
        # 5. Weekend/season multiplier
        weekend_factor = self._calculate_weekend_multiplier(factors.day_of_week)
        season_factor = self._calculate_season_multiplier(factors.month)
        temporal_factor = weekend_factor * season_factor
        current_price *= temporal_factor
        factors_applied['weekend'] = weekend_factor
        factors_applied['season'] = season_factor
        breakdown['after_temporal'] = current_price
        
        # 6. Demand multiplier (high demand = higher price)
        demand_factor = self._calculate_demand_multiplier(factors.demand_index)
        current_price *= demand_factor
        factors_applied['demand'] = demand_factor
        breakdown['after_demand'] = current_price
        
        # === APPLY GUARDRAILS ===
        
        # 1. Cost floor (minimum margin)
        cost_floor = factors.base_daily_rate * (1 + self.min_margin)
        if current_price < cost_floor:
            current_price = cost_floor
            guardrails_applied.append('cost_floor')
            breakdown['cost_floor_applied'] = cost_floor
        
        # 2. Absolute ceiling
        absolute_ceiling = factors.base_daily_rate * self.max_ceiling_multiplier
        if current_price > absolute_ceiling:
            current_price = absolute_ceiling
            guardrails_applied.append('absolute_ceiling')
            breakdown['ceiling_applied'] = absolute_ceiling
        
        # 3. Competitor band clamp
        if factors.avg_competitor_price > 0:
            lower_band = factors.avg_competitor_price * (1 - self.competitor_band_tolerance)
            upper_band = factors.avg_competitor_price * (1 + self.competitor_band_tolerance)
            
            if current_price < lower_band:
                current_price = lower_band
                guardrails_applied.append('competitor_floor')
                breakdown['competitor_floor'] = lower_band
            elif current_price > upper_band:
                current_price = upper_band
                guardrails_applied.append('competitor_ceiling')
                breakdown['competitor_ceiling'] = upper_band
        
        # 4. Rate-of-change limit (±8% from last price)
        if factors.last_quoted_price is not None and factors.last_quoted_price > 0:
            max_increase = factors.last_quoted_price * (1 + self.max_rate_change)
            max_decrease = factors.last_quoted_price * (1 - self.max_rate_change)
            
            if current_price > max_increase:
                current_price = max_increase
                guardrails_applied.append('rate_change_cap')
                breakdown['rate_change_cap'] = max_increase
            elif current_price < max_decrease:
                current_price = max_decrease
                guardrails_applied.append('rate_change_floor')
                breakdown['rate_change_floor'] = max_decrease
        
        # 5. Exponential smoothing (smooth price changes)
        if factors.last_quoted_price is not None and factors.last_quoted_price > 0:
            smoothed_price = (
                self.smoothing_alpha * current_price + 
                (1 - self.smoothing_alpha) * factors.last_quoted_price
            )
            current_price = smoothed_price
            guardrails_applied.append('exponential_smoothing')
            breakdown['after_smoothing'] = smoothed_price
        
        breakdown['final_price'] = current_price
        
        return PricingResult(
            final_price_per_day=round(current_price, 2),
            baseline_price=baseline_price,
            factors_applied=factors_applied,
            guardrails_applied=guardrails_applied,
            price_breakdown=breakdown
        )
    
    # === FACTOR CALCULATION METHODS ===
    
    def _calculate_utilization_factor(self, utilization_rate: float) -> float:
        """
        Calculate utilization factor
        
        Low utilization (< 0.3): discount to attract customers
        Medium utilization (0.3 - 0.7): neutral
        High utilization (> 0.7): premium for scarce inventory
        """
        if utilization_rate < 0.3:
            # Low utilization: 10% discount
            return 0.90
        elif utilization_rate < 0.5:
            # Medium-low: 5% discount
            return 0.95
        elif utilization_rate < 0.7:
            # Medium: neutral
            return 1.0
        elif utilization_rate < 0.85:
            # High: 10% premium
            return 1.10
        else:
            # Very high: 20% premium
            return 1.20
    
    def _calculate_lead_time_factor(self, lead_time_days: int) -> float:
        """
        Calculate lead time factor
        
        Last-minute bookings (< 3 days): premium
        Normal advance (3-14 days): neutral
        Early bookings (> 14 days): small discount to lock in demand
        """
        if lead_time_days < 1:
            # Same day: 25% premium
            return 1.25
        elif lead_time_days < 3:
            # 1-2 days: 15% premium
            return 1.15
        elif lead_time_days < 7:
            # 3-6 days: 5% premium
            return 1.05
        elif lead_time_days < 14:
            # 1-2 weeks: neutral
            return 1.0
        elif lead_time_days < 30:
            # 2-4 weeks: 5% discount
            return 0.95
        else:
            # > 30 days: 10% discount
            return 0.90
    
    def _calculate_duration_discount(self, rental_length_days: int) -> float:
        """
        Calculate duration discount
        
        Longer rentals get volume discounts
        D1-D2: no discount
        D3: 3% off
        D4-D6: 5% off
        D7: 10% off
        D8-D13: 12% off
        D14: 15% off
        D15-D29: 18% off
        M1 (30+): 20% off
        """
        if rental_length_days >= 30:
            # M1: 20% discount
            return 0.80
        elif rental_length_days >= 15:
            # D15-D29: 18% discount
            return 0.82
        elif rental_length_days >= 14:
            # D14: 15% discount
            return 0.85
        elif rental_length_days >= 8:
            # D8-D13: 12% discount
            return 0.88
        elif rental_length_days >= 7:
            # D7: 10% discount
            return 0.90
        elif rental_length_days >= 4:
            # D4-D6: 5% discount
            return 0.95
        elif rental_length_days >= 3:
            # D3: 3% discount
            return 0.97
        else:
            # D1-D2: no discount
            return 1.0
    
    def _calculate_late_night_premium(self, hour: int) -> float:
        """
        Calculate late-night booking premium
        
        Bookings made late at night (10pm-6am) often indicate urgency
        """
        if 22 <= hour <= 23 or 0 <= hour <= 5:
            # Late night: 10% premium
            return 1.10
        else:
            # Normal hours: neutral
            return 1.0
    
    def _calculate_weekend_multiplier(self, day_of_week: int) -> float:
        """
        Calculate weekend multiplier
        
        Weekend rentals typically have higher demand
        Saudi weekend: Thursday (3), Friday (4), Saturday (5)
        """
        if day_of_week in [3, 4, 5]:  # Thursday, Friday, Saturday
            # Weekend: 10% premium
            return 1.10
        else:
            # Weekday: neutral
            return 1.0
    
    def _calculate_season_multiplier(self, month: int) -> float:
        """
        Calculate seasonal multiplier for Saudi Arabia
        
        Peak season (Oct-Apr): high demand (pleasant weather)
        Off-season (May-Sep): lower demand (extreme heat)
        """
        if month in [10, 11, 12, 1, 2, 3, 4]:
            # Peak season (pleasant weather): 15% premium
            return 1.15
        elif month in [7, 8]:
            # Extreme heat months: 10% discount
            return 0.90
        else:
            # Shoulder season: 5% discount
            return 0.95
    
    def _calculate_demand_multiplier(self, demand_index: float) -> float:
        """
        Calculate demand multiplier based on demand index (0-1)
        
        High demand index = high conversion rate and quote volume
        """
        if demand_index < 0.2:
            # Very low demand: 10% discount
            return 0.90
        elif demand_index < 0.4:
            # Low demand: 5% discount
            return 0.95
        elif demand_index < 0.6:
            # Medium demand: neutral
            return 1.0
        elif demand_index < 0.8:
            # High demand: 10% premium
            return 1.10
        else:
            # Very high demand: 20% premium
            return 1.20


# === HELPER FUNCTIONS ===

def calculate_lead_time_days(booking_date: date, rental_start_date: date) -> int:
    """Calculate lead time in days between booking and rental start"""
    delta = rental_start_date - booking_date
    return max(0, delta.days)


def get_hour_of_booking(booking_datetime: datetime) -> int:
    """Extract hour from booking datetime"""
    return booking_datetime.hour


def apply_pricing_rules(
    baseline_price: float,
    base_rate: float,
    rental_days: int,
    lead_days: int,
    utilization: float,
    demand: float,
    competitor_price: float,
    day_of_week: int,
    month: int,
    last_price: Optional[float] = None,
    hour: Optional[int] = None
) -> PricingResult:
    """
    Convenience function to apply pricing rules
    
    Args:
        baseline_price: ML model prediction
        base_rate: Vehicle base daily rate
        rental_days: Rental duration in days
        lead_days: Days between booking and rental start
        utilization: Fleet utilization rate (0-1)
        demand: Demand index (0-1)
        competitor_price: Average competitor price
        day_of_week: Day of week (0=Monday)
        month: Month (1-12)
        last_price: Last quoted price for this vehicle/period
        hour: Hour of booking (0-23)
        
    Returns:
        PricingResult with final price and breakdown
    """
    engine = PricingRuleEngine()
    
    factors = PricingFactors(
        baseline_price_ml=baseline_price,
        base_daily_rate=base_rate,
        rental_length_days=rental_days,
        lead_time_days=lead_days,
        utilization_rate=utilization,
        demand_index=demand,
        avg_competitor_price=competitor_price,
        day_of_week=day_of_week,
        month=month,
        hour_of_booking=hour,
        last_quoted_price=last_price
    )
    
    return engine.calculate_price(factors)
