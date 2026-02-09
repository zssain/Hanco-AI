/**
 * Dynamic Pricing Service
 * 
 * Features ML-powered pricing with:
 * - Temporal factors (day of week, season, holidays)
 * - REAL competitor pricing from 24h scraper
 * - Demand-based adjustments
 * - City-specific pricing
 * - Rental duration discounts
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface CompetitorRate {
  company: string;
  dailyRate: number;
  category: string;
  scrapedAt?: string;  // Timestamp of when this was scraped
  vehicleName?: string;  // Car name (e.g., "Toyota Camry")
  sourceUrl?: string;  // Link to competitor website
  isEstimate?: boolean;  // True if price is estimated (e.g., one-way)
}

interface APICompetitorPrice {
  id: string;
  provider: string;
  city: string;
  category: string;
  price: number;
  currency: string;
  url?: string;
  vehicle_name?: string;
  scraped_at: string;
}

interface PricingFactors {
  baseRate: number;
  competitorAvg: number;
  competitorMin: number;
  competitorMax: number;
  demandMultiplier: number;
  seasonalMultiplier: number;
  weekendMultiplier: number;
  advanceBookingDiscount: number;
  durationDiscount: number;
  cityMultiplier: number;
}

interface PricingResult {
  dailyPrice: number;
  totalPrice: number;
  originalPrice: number;
  savings: number;
  factors: PricingFactors;
  competitors: CompetitorRate[];
  lastScraped?: string;  // When competitor prices were last updated
  isOneWay?: boolean;  // True if pickup != dropoff city
  competitorDataLimited?: boolean;  // True if competitor data may not be accurate
  breakdown: {
    label: string;
    value: number;
    impact: string;
  }[];
}

export class DynamicPricingService {
  // Cache for competitor data from API (city -> category -> rates)
  private competitorCache: Map<string, { data: CompetitorRate[]; timestamp: number; lastScraped: string }> = new Map();
  private readonly CACHE_TTL_MS = 5 * 60 * 1000; // 5 minute cache (data is scraped every 24h, but we cache locally for 5 min)

  // Category price multipliers (relative to sedan baseline)
  private categoryMultipliers: Record<string, number> = {
    'economy': 0.75,
    'compact': 0.85,
    'sedan': 1.0,
    'suv': 1.5,
    'luxury': 2.5,
    'minivan': 1.3,
    'truck': 1.4,
  };

  // Fallback data in case API is unavailable (will be scaled by category)
  private fallbackData: Record<string, CompetitorRate[]> = {
    'economy': [
      { company: 'Yelo', dailyRate: 150, category: 'Economy' },
      { company: 'Lumi', dailyRate: 145, category: 'Economy' },
      { company: 'Key', dailyRate: 130, category: 'Economy' },
      { company: 'Budget', dailyRate: 140, category: 'Economy' },
    ],
    'compact': [
      { company: 'Yelo', dailyRate: 155, category: 'Compact' },
      { company: 'Lumi', dailyRate: 150, category: 'Compact' },
      { company: 'Key', dailyRate: 140, category: 'Compact' },
      { company: 'Budget', dailyRate: 148, category: 'Compact' },
    ],
    'sedan': [
      { company: 'Yelo', dailyRate: 180, category: 'Sedan' },
      { company: 'Lumi', dailyRate: 175, category: 'Sedan' },
      { company: 'Key', dailyRate: 165, category: 'Sedan' },
      { company: 'Budget', dailyRate: 170, category: 'Sedan' },
    ],
    'suv': [
      { company: 'Yelo', dailyRate: 270, category: 'SUV' },
      { company: 'Lumi', dailyRate: 260, category: 'SUV' },
      { company: 'Key', dailyRate: 245, category: 'SUV' },
      { company: 'Budget', dailyRate: 255, category: 'SUV' },
    ],
    'luxury': [
      { company: 'Yelo', dailyRate: 450, category: 'Luxury' },
      { company: 'Lumi', dailyRate: 430, category: 'Luxury' },
      { company: 'Key', dailyRate: 400, category: 'Luxury' },
      { company: 'Budget', dailyRate: 420, category: 'Luxury' },
    ],
  };

  /**
   * Fetch REAL competitor prices from the API (scraped every 24 hours)
   */
  async fetchCompetitorPrices(city: string, category: string): Promise<{ competitors: CompetitorRate[]; lastScraped: string }> {
    const cacheKey = `${city.toLowerCase()}-${category.toLowerCase()}`;
    const now = Date.now();

    // Check cache first
    const cached = this.competitorCache.get(cacheKey);
    if (cached && (now - cached.timestamp) < this.CACHE_TTL_MS) {
      console.log(`[PricingService] Using cached competitor data for ${cacheKey}`);
      return { competitors: cached.data, lastScraped: cached.lastScraped };
    }

    try {
      console.log(`[PricingService] Fetching REAL competitor prices for city=${city}, category=${category}`);
      
      const response = await fetch(
        `${API_BASE_URL}/api/v1/competitors?city=${encodeURIComponent(city)}&category=${encodeURIComponent(category)}&limit=50`
      );

      if (!response.ok) {
        throw new Error(`API returned ${response.status}`);
      }

      const data = await response.json();
      const prices: APICompetitorPrice[] = data.prices || [];

      if (prices.length === 0) {
        console.warn(`[PricingService] No competitor prices found for ${city}/${category}, using fallback`);
        return { 
          competitors: this.getFallbackData(category), 
          lastScraped: 'N/A (fallback data)' 
        };
      }

      // Transform API data to CompetitorRate format
      // Apply category multiplier if scraped data is from a different category
      const requestedCategory = category.toLowerCase();
      const competitors: CompetitorRate[] = prices.map(p => {
        const scrapedCategory = p.category.toLowerCase();
        let adjustedPrice = p.price;
        
        // If scraped data is from different category, apply multiplier
        if (scrapedCategory !== requestedCategory) {
          const scrapedMultiplier = this.categoryMultipliers[scrapedCategory] || 1;
          const requestedMultiplier = this.categoryMultipliers[requestedCategory] || 1;
          adjustedPrice = p.price * (requestedMultiplier / scrapedMultiplier);
        }
        
        return {
          company: this.formatProviderName(p.provider),
          dailyRate: Math.round(adjustedPrice),
          category: requestedCategory,  // Use requested category for display
          scrapedAt: p.scraped_at,
          vehicleName: p.vehicle_name,  // Include car name
          sourceUrl: p.url,  // Include source URL
        };
      });

      // Deduplicate by provider (keep the most recent for each)
      const uniqueCompetitors = this.deduplicateByProvider(competitors);
      
      // Get the most recent scraped_at timestamp
      const lastScraped = prices[0]?.scraped_at || 'Unknown';

      // Update cache
      this.competitorCache.set(cacheKey, {
        data: uniqueCompetitors,
        timestamp: now,
        lastScraped,
      });

      console.log(`[PricingService] Loaded ${uniqueCompetitors.length} REAL competitor prices (scraped: ${lastScraped})`);
      return { competitors: uniqueCompetitors, lastScraped };

    } catch (error) {
      console.error('[PricingService] Error fetching competitor prices:', error);
      return { 
        competitors: this.getFallbackData(category), 
        lastScraped: 'N/A (API unavailable)' 
      };
    }
  }

  private formatProviderName(provider: string): string {
    const providerNames: Record<string, string> = {
      'budget': 'Budget',
      'yelo': 'Yelo',
      'lumi': 'Lumi',
      'key': 'Key Rent a Car',
      'hertz': 'Hertz',
      'europcar': 'Europcar',
      'theeb': 'Theeb',
    };
    return providerNames[provider.toLowerCase()] || provider.charAt(0).toUpperCase() + provider.slice(1);
  }

  private deduplicateByProvider(competitors: CompetitorRate[]): CompetitorRate[] {
    const seen = new Map<string, CompetitorRate>();
    for (const comp of competitors) {
      const key = comp.company.toLowerCase();
      if (!seen.has(key)) {
        seen.set(key, comp);
      }
    }
    return Array.from(seen.values());
  }

  private getFallbackData(category: string): CompetitorRate[] {
    const normalizedCategory = category.toLowerCase();
    return this.fallbackData[normalizedCategory] || this.fallbackData['sedan'];
  }

  /**
   * Get cached competitor data synchronously (for use in calculatePrice)
   */
  private getCachedCompetitors(city: string, category: string): CompetitorRate[] {
    const cacheKey = `${city.toLowerCase()}-${category.toLowerCase()}`;
    const cached = this.competitorCache.get(cacheKey);
    if (cached) {
      return cached.data;
    }
    return this.getFallbackData(category);
  }

  /**
   * NEW: Call the unified pricing API for consistent pricing across all channels
   * This is the SINGLE SOURCE OF TRUTH - same engine used by chatbot
   */
  async getUnifiedPrice(
    vehicleId: string,
    pickupBranchKey: string,
    pickupDate: Date,
    dropoffDate: Date,
    includeInsurance: boolean = false,
    dropoffBranchKey?: string  // Optional: for one-way rentals
  ): Promise<{
    dailyRate: number;
    durationDays: number;
    baseTotal: number;
    insuranceAmount: number;
    finalTotal: number;
    competitorAvg: number | null;
    savingsVsCompetitor: number | null;
    classBucket: string;  // Vehicle class used for pricing
    marketDataUsed: boolean;  // Whether competitor data was available
    isOneWay: boolean;  // Whether this is a one-way rental
    oneWayPremium: number;  // Premium applied (e.g., 0.15)
    breakdown: Record<string, unknown>;
    source: string;
  } | null> {
    try {
      const requestBody: Record<string, unknown> = {
        vehicle_id: vehicleId,
        branch_key: pickupBranchKey.toLowerCase().replace(/\s+/g, '_'),
        pickup_date: pickupDate.toISOString().split('T')[0],
        dropoff_date: dropoffDate.toISOString().split('T')[0],
        include_insurance: includeInsurance,
      };
      
      // Add dropoff_branch_key if it's a one-way rental
      if (dropoffBranchKey) {
        requestBody.dropoff_branch_key = dropoffBranchKey.toLowerCase().replace(/\s+/g, '_');
      }
      
      const response = await fetch(`${API_BASE_URL}/api/v1/pricing/unified-price`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        console.warn(`[PricingService] Unified API returned ${response.status}`);
        return null;
      }

      const data = await response.json();
      return {
        dailyRate: data.daily_rate,
        durationDays: data.duration_days,
        baseTotal: data.base_total,
        insuranceAmount: data.insurance_amount,
        finalTotal: data.final_total,
        competitorAvg: data.competitor_avg,
        savingsVsCompetitor: data.savings_vs_competitor,
        classBucket: data.class_bucket,  // Category used for pricing
        marketDataUsed: data.market_data_used,  // Whether competitor data was available
        isOneWay: data.is_one_way || false,  // One-way rental flag
        oneWayPremium: data.one_way_premium || 0,  // One-way premium applied
        breakdown: data.breakdown,
        source: data.source,
      };
    } catch (error) {
      console.error('[PricingService] Error calling unified pricing API:', error);
      return null;
    }
  }

  /**
   * Calculate dynamic price using ML-inspired algorithm (async version with REAL competitor data)
   * NOW USES UNIFIED API for consistent pricing with chatbot
   */
  async calculatePriceAsync(
    baseRate: number,
    category: string,
    startDate: Date,
    endDate: Date,
    city: string,
    pickupLocation: string,
    dropoffLocation: string,
    vehicleId?: string  // Optional: if provided, uses unified API
  ): Promise<PricingResult> {
    // If vehicleId is provided, try to use the unified pricing API first
    if (vehicleId) {
      try {
        // Convert locations to branch keys for API
        const pickupBranchKey = this.locationToBranchKey(pickupLocation);
        const dropoffBranchKey = this.locationToBranchKey(dropoffLocation);
        
        // Only pass dropoff if it's different from pickup (one-way rental)
        const isOneWay = pickupBranchKey !== dropoffBranchKey;
        
        const unifiedResult = await this.getUnifiedPrice(
          vehicleId,
          pickupBranchKey,
          startDate,
          endDate,
          false, // insurance handled separately in UI
          isOneWay ? dropoffBranchKey : undefined  // Pass dropoff for one-way rentals
        );
        
        if (unifiedResult) {
          console.log(`[PricingService] Using unified pricing API: ${unifiedResult.dailyRate} SAR/day, class=${unifiedResult.classBucket}, marketData=${unifiedResult.marketDataUsed}, isOneWay=${unifiedResult.isOneWay}`);
          
          // Convert unified result to PricingResult format
          const days = unifiedResult.durationDays;
          const dailyPrice = unifiedResult.dailyRate;
          const totalPrice = unifiedResult.baseTotal;
          const originalPrice = Math.round(baseRate * days);
          
          // ⚠️ IMPORTANT: Use classBucket from unified API, NOT the category passed to this function
          // This ensures competitor display matches what was used for pricing
          const pricingCategory = unifiedResult.classBucket || category;
          
          // Fetch competitor data for display using the SAME category as pricing used
          const { competitors, lastScraped } = await this.fetchCompetitorPrices(city, pricingCategory);
          
          // For one-way rentals, adjust competitor display prices to show estimated one-way rates
          let adjustedCompetitors = competitors;
          if (unifiedResult.isOneWay) {
            adjustedCompetitors = competitors.map(c => ({
              ...c,
              dailyRate: Math.round(c.dailyRate * (1 + unifiedResult.oneWayPremium)),
              isEstimate: true,
            }));
          }
          
          const competitorRates = adjustedCompetitors.map(c => c.dailyRate);
          const competitorAvg = unifiedResult.competitorAvg || 
            (competitorRates.length > 0 ? competitorRates.reduce((a, b) => a + b, 0) / competitorRates.length : baseRate);
          
          return {
            dailyPrice,
            totalPrice,
            originalPrice,
            savings: originalPrice - totalPrice,
            factors: {
              baseRate,
              competitorAvg: Math.round(competitorAvg),
              competitorMin: competitorRates.length > 0 ? Math.min(...competitorRates) : baseRate * 0.9,
              competitorMax: competitorRates.length > 0 ? Math.max(...competitorRates) : baseRate * 1.1,
              demandMultiplier: (unifiedResult.breakdown as Record<string, number>)?.demand_index || 1.0,
              seasonalMultiplier: 1.0,
              weekendMultiplier: (unifiedResult.breakdown as Record<string, number>)?.weekend_premium ? 1.03 : 1.0,
              advanceBookingDiscount: 0,
              durationDiscount: (unifiedResult.breakdown as Record<string, number>)?.duration_discount || 0,
              cityMultiplier: 1.0,
            },
            competitors: adjustedCompetitors,
            lastScraped,
            breakdown: [
              { label: 'Base Rate', value: baseRate, impact: 'base' },
              { label: 'ML Optimized', value: dailyPrice, impact: dailyPrice > baseRate ? '+' : '-' },
              { label: 'Competitor Avg', value: Math.round(competitorAvg), impact: 'reference' },
            ],
            isOneWay: unifiedResult.isOneWay,  // Use API's determination
            // Mark as limited if unified API says no market data was used OR it's one-way
            competitorDataLimited: !unifiedResult.marketDataUsed || unifiedResult.isOneWay,
          };
        }
      } catch (error) {
        console.warn('[PricingService] Unified API failed, falling back to local calculation:', error);
      }
    }
    
    // Fallback: Fetch REAL competitor prices from API and calculate locally
    const { competitors, lastScraped } = await this.fetchCompetitorPrices(city, category);
    
    return this.calculatePriceWithCompetitors(
      baseRate, category, startDate, endDate, city, 
      pickupLocation, dropoffLocation, competitors, lastScraped
    );
  }

  /**
   * Calculate dynamic price synchronously (uses cached data)
   */
  calculatePrice(
    baseRate: number,
    category: string,
    startDate: Date,
    endDate: Date,
    city: string,
    pickupLocation: string,
    dropoffLocation: string
  ): PricingResult {
    // Use cached competitor data
    const competitors = this.getCachedCompetitors(city, category);
    return this.calculatePriceWithCompetitors(
      baseRate, category, startDate, endDate, city, 
      pickupLocation, dropoffLocation, competitors
    );
  }

  /**
   * Core pricing calculation logic
   */
  private calculatePriceWithCompetitors(
    baseRate: number,
    _category: string,  // Kept for future use
    startDate: Date,
    endDate: Date,
    city: string,
    pickupLocation: string,
    dropoffLocation: string,
    competitors: CompetitorRate[],
    lastScraped?: string
  ): PricingResult {
    // Calculate rental days
    const days = Math.ceil((endDate.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24));
    const daysUntilPickup = Math.ceil((startDate.getTime() - new Date().getTime()) / (1000 * 60 * 60 * 24));

    // Detect one-way rental (pickup city != dropoff city)
    const pickupCity = this.extractCityFromLocation(pickupLocation);
    const dropoffCity = this.extractCityFromLocation(dropoffLocation);
    const isOneWay = pickupCity !== dropoffCity;
    
    // For one-way rentals, competitor data is limited (we only have single-city prices)
    // Mark competitor prices as estimates and apply one-way premium to them
    let adjustedCompetitors = competitors;
    let competitorDataLimited = false;
    
    if (isOneWay) {
      competitorDataLimited = true;
      // Apply estimated one-way premium to competitor prices (25% is industry standard)
      adjustedCompetitors = competitors.map(c => ({
        ...c,
        dailyRate: Math.round(c.dailyRate * 1.25),
        isEstimate: true,
      }));
      console.log(`[PricingService] One-way rental detected: ${pickupCity} → ${dropoffCity}. Competitor prices are estimates.`);
    }

    // Get competitor rates
    const competitorRates = adjustedCompetitors.map(c => c.dailyRate);
    const competitorAvg = competitorRates.length > 0 
      ? competitorRates.reduce((a, b) => a + b, 0) / competitorRates.length 
      : baseRate;
    const competitorMin = competitorRates.length > 0 ? Math.min(...competitorRates) : baseRate * 0.9;
    const competitorMax = competitorRates.length > 0 ? Math.max(...competitorRates) : baseRate * 1.1;

    // Calculate factors
    const demandMultiplier = this.calculateDemandMultiplier(startDate, city);
    const seasonalMultiplier = this.calculateSeasonalMultiplier(startDate);
    const weekendMultiplier = this.calculateWeekendMultiplier(startDate);
    const advanceBookingDiscount = this.calculateAdvanceBookingDiscount(daysUntilPickup);
    const durationDiscount = this.calculateDurationDiscount(days);
    const cityMultiplier = this.getCityMultiplier(city);
    const intercityPremium = this.calculateIntercityPremium(pickupLocation, dropoffLocation);

    // PROFIT-FIRST pricing: Use internal costs + positioning, competitors for guardrails only
    // We do NOT chase competitor prices - DPE is a premium brand
    
    // Calculate adjusted price from our base rate
    let adjustedPrice = baseRate;
    
    // Apply multipliers
    adjustedPrice *= demandMultiplier;
    adjustedPrice *= seasonalMultiplier;
    adjustedPrice *= weekendMultiplier;
    adjustedPrice *= cityMultiplier;
    
    // Apply intercity premium FIRST (before guardrails, so it's included in floor/ceiling check)
    adjustedPrice *= intercityPremium;
    
    // Apply discounts
    adjustedPrice *= (1 - advanceBookingDiscount);
    adjustedPrice *= (1 - durationDiscount);
    
    // COMPETITIVE GUARDRAILS:
    // Floor: Never below 80% of base rate (protects margin)
    // Ceiling: For same-city, stay at/below competitor average to be competitive
    const floorPrice = baseRate * 0.80;
    let ceilingPrice: number;
    
    if (isOneWay) {
      // One-way rentals: Allow 10% above competitor avg (no direct comparison)
      ceilingPrice = competitorAvg * 1.10;
    } else {
      // Same-city rentals: Match competitor average to stay competitive
      ceilingPrice = competitorAvg;
    }
    
    adjustedPrice = Math.max(floorPrice, Math.min(adjustedPrice, ceilingPrice));
    
    const dailyPrice = Math.round(adjustedPrice);
    const totalPrice = dailyPrice * days;
    const originalPrice = Math.round(baseRate * days);
    const savings = originalPrice - totalPrice;

    // Build breakdown
    const breakdown = [
      { label: 'Base Rate', value: baseRate, impact: 'base' },
      { label: 'Demand Factor', value: demandMultiplier, impact: demandMultiplier > 1 ? '+' : '-' },
      { label: 'Season Factor', value: seasonalMultiplier, impact: seasonalMultiplier > 1 ? '+' : '-' },
      { label: 'Weekend Premium', value: weekendMultiplier, impact: weekendMultiplier > 1 ? '+' : '-' },
      { label: 'City Adjustment', value: cityMultiplier, impact: cityMultiplier > 1 ? '+' : '-' },
      { label: 'Intercity Factor', value: intercityPremium, impact: intercityPremium > 1 ? '+' : '-' },
      { label: 'Advance Booking', value: advanceBookingDiscount * 100, impact: advanceBookingDiscount > 0 ? '-' : '0' },
      { label: 'Duration Discount', value: durationDiscount * 100, impact: durationDiscount > 0 ? '-' : '0' },
    ];

    return {
      dailyPrice,
      totalPrice,
      originalPrice,
      savings,
      factors: {
        baseRate,
        competitorAvg: Math.round(competitorAvg),
        competitorMin: Math.round(competitorMin),
        competitorMax: Math.round(competitorMax),
        demandMultiplier,
        seasonalMultiplier,
        weekendMultiplier,
        advanceBookingDiscount,
        durationDiscount,
        cityMultiplier,
      },
      competitors: adjustedCompetitors,
      lastScraped,
      breakdown,
      isOneWay,
      competitorDataLimited,
    };
  }

  /**
   * Extract city name from location string
   */
  private extractCityFromLocation(location: string): string {
    if (!location) return '';
    // Location format could be "Jeddah Airport", "Riyadh - Downtown", etc.
    const normalized = location.toLowerCase().trim();
    
    // Check for known Saudi cities
    const cities = ['jeddah', 'riyadh', 'dammam', 'mecca', 'medina', 'khobar', 'dhahran', 'tabuk', 'abha', 'taif'];
    for (const city of cities) {
      if (normalized.includes(city)) {
        return city;
      }
    }
    
    // Fallback: return first word
    return normalized.split(/[\s\-,]/)[0];
  }

  /**
   * Convert location string to branch key for API
   * e.g., "Riyadh Airport" -> "riyadh_airport", "Jeddah City Center" -> "jeddah_city_center"
   */
  private locationToBranchKey(location: string): string {
    if (!location) return 'riyadh';
    return location.toLowerCase().trim().replace(/[\s\-]+/g, '_');
  }

  private calculateDemandMultiplier(date: Date, city: string): number {
    const dayOfWeek = date.getDay();
    let multiplier = 1.0;
    
    // High demand on weekends (Friday/Saturday in Saudi Arabia)
    // REDUCED from 1.15 to 1.05
    if (dayOfWeek === 5 || dayOfWeek === 6) {
      multiplier = 1.05;
    } else if (dayOfWeek === 4) {
      // Moderate demand on Thursdays
      multiplier = 1.03;
    }
    
    // Check for major events/holidays - apply small additional premium
    const month = date.getMonth() + 1;
    
    // Ramadan period (approximate - varies yearly) - REDUCED from 1.25
    if (month === 3 || month === 4) {
      multiplier = Math.max(multiplier, 1.08);
    }
    
    // Hajj season - REDUCED from 1.40/1.20
    if (month === 7 || month === 8) {
      multiplier = Math.max(multiplier, city.toLowerCase() === 'jeddah' ? 1.12 : 1.08);
    }
    
    // Summer vacation (June-August) - REDUCED from 1.12
    if (month >= 6 && month <= 8) {
      multiplier = Math.max(multiplier, 1.05);
    }
    
    return multiplier;
  }

  private calculateSeasonalMultiplier(date: Date): number {
    const month = date.getMonth() + 1;
    
    // Peak season (October-April): Pleasant weather - REDUCED from 1.08
    if (month >= 10 || month <= 4) {
      return 1.02;
    }
    
    // Summer (May-September): Very hot, lower demand - REDUCED discount from 0.92
    return 0.98;
  }

  private calculateWeekendMultiplier(date: Date): number {
    const dayOfWeek = date.getDay();
    
    // Friday/Saturday in Saudi Arabia - REDUCED from 1.12
    if (dayOfWeek === 5 || dayOfWeek === 6) {
      return 1.03;
    }
    
    return 1.0;
  }

  private calculateAdvanceBookingDiscount(daysUntilPickup: number): number {
    if (daysUntilPickup >= 30) return 0.15; // 15% off for 30+ days
    if (daysUntilPickup >= 14) return 0.10; // 10% off for 14+ days
    if (daysUntilPickup >= 7) return 0.05;  // 5% off for 7+ days
    return 0;
  }

  private calculateDurationDiscount(days: number): number {
    if (days >= 30) return 0.20; // 20% off monthly rentals
    if (days >= 14) return 0.15; // 15% off bi-weekly
    if (days >= 7) return 0.10;  // 10% off weekly
    if (days >= 3) return 0.05;  // 5% off 3+ days
    return 0;
  }

  private getCityMultiplier(city: string): number {
    // REDUCED all premiums to be less aggressive
    const cityFactors: Record<string, number> = {
      'riyadh': 1.0,    // Base city
      'jeddah': 1.02,   // Higher demand (tourism) - REDUCED from 1.05
      'dammam': 0.98,   // Lower demand - REDUCED from 0.95
      'mecca': 1.05,    // High demand (religious tourism) - REDUCED from 1.15
      'medina': 1.04,   // High demand (religious tourism) - REDUCED from 1.12
      'taif': 1.02,     // Summer tourism - REDUCED from 1.08
    };
    
    return cityFactors[city.toLowerCase()] || 1.0;
  }

  private calculateIntercityPremium(pickup: string, dropoff: string): number {
    // Extract city names from location strings (e.g., "Riyadh Airport" -> "Riyadh")
    const pickupCity = pickup.split(' ')[0].toLowerCase();
    const dropoffCity = dropoff.split(' ')[0].toLowerCase();
    
    // Same city, different locations (e.g., Airport to City Center)
    if (pickupCity === dropoffCity) {
      return 1.0; // No premium for same city
    }
    
    // Distance-based intercity premiums (one-way rentals)
    // Based on actual distances in Saudi Arabia
    const distancePremiums: Record<string, Record<string, number>> = {
      'riyadh': {
        'jeddah': 1.25,   // ~950 km - Major route
        'dammam': 1.18,   // ~400 km
        'mecca': 1.28,    // ~870 km
        'medina': 1.30,   // ~850 km
        'taif': 1.22,     // ~750 km
      },
      'jeddah': {
        'riyadh': 1.25,   // ~950 km
        'dammam': 1.35,   // ~1,300 km - Longest route
        'mecca': 1.08,    // ~80 km - Short distance
        'medina': 1.15,   // ~420 km
        'taif': 1.10,     // ~170 km
      },
      'dammam': {
        'riyadh': 1.18,   // ~400 km
        'jeddah': 1.35,   // ~1,300 km
        'mecca': 1.32,    // ~1,250 km
        'medina': 1.30,   // ~1,150 km
        'taif': 1.28,     // ~1,100 km
      },
      'mecca': {
        'riyadh': 1.28,   // ~870 km
        'jeddah': 1.08,   // ~80 km
        'dammam': 1.32,   // ~1,250 km
        'medina': 1.12,   // ~340 km
        'taif': 1.12,     // ~90 km
      },
      'medina': {
        'riyadh': 1.30,   // ~850 km
        'jeddah': 1.15,   // ~420 km
        'dammam': 1.30,   // ~1,150 km
        'mecca': 1.12,    // ~340 km
        'taif': 1.18,     // ~280 km
      },
    };
    
    // Get premium based on route, default to 1.20 if route not defined
    const premium = distancePremiums[pickupCity]?.[dropoffCity] || 1.20;
    
    return premium;
  }

  /**
   * Get competitor comparison for display (async version with REAL data)
   */
  async getCompetitorComparisonAsync(city: string, category: string, ourPrice: number): Promise<{
    competitors: CompetitorRate[];
    ourPosition: string;
    savings: number;
    percentLower: number;
    lastScraped?: string;
  }> {
    const { competitors, lastScraped } = await this.fetchCompetitorPrices(city, category);
    return this.buildComparisonResult(competitors, ourPrice, lastScraped);
  }

  /**
   * Get competitor comparison synchronously (uses cached data)
   */
  getCompetitorComparison(category: string, ourPrice: number): {
    competitors: CompetitorRate[];
    ourPosition: string;
    savings: number;
    percentLower: number;
  } {
    const competitors = this.getCachedCompetitors('riyadh', category);
    return this.buildComparisonResult(competitors, ourPrice);
  }

  private buildComparisonResult(
    competitors: CompetitorRate[], 
    ourPrice: number, 
    lastScraped?: string
  ): {
    competitors: CompetitorRate[];
    ourPosition: string;
    savings: number;
    percentLower: number;
    lastScraped?: string;
  } {
    const competitorAvg = competitors.length > 0 
      ? competitors.reduce((sum, c) => sum + c.dailyRate, 0) / competitors.length
      : ourPrice;
    const savings = Math.round(competitorAvg - ourPrice);
    const percentLower = Math.round(((competitorAvg - ourPrice) / competitorAvg) * 100);
    
    let position = 'competitive';
    if (competitors.length > 0 && ourPrice < Math.min(...competitors.map(c => c.dailyRate))) {
      position = 'best';
    } else if (ourPrice <= competitorAvg) {
      position = 'better';
    }
    
    return {
      competitors,
      ourPosition: position,
      savings,
      percentLower,
      lastScraped,
    };
  }
}

export const pricingService = new DynamicPricingService();
