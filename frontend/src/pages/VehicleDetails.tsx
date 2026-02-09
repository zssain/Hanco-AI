import { useParams, useNavigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import api from '@/lib/api';
import { pricingService } from '../services/pricingService';
import { Calendar, MapPin, TrendingDown, Info, Users, Settings, Fuel, Loader2, ArrowLeft } from 'lucide-react';

export function VehicleDetails() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [vehicle, setVehicle] = useState<any>(null);
  const [pricingResult, setPricingResult] = useState<any>(null);
  const [competitorLoading, setCompetitorLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [formData, setFormData] = useState({
    startDate: new Date().toISOString().split('T')[0],
    endDate: new Date(Date.now() + 86400000 * 3).toISOString().split('T')[0], // 3 days default
    city: 'Riyadh',
    pickup: 'Riyadh Airport',
    dropoff: 'Riyadh Airport'
  });

  useEffect(() => {
    const fetchVehicle = async () => {
      try {
        if (!id) return;
        const response = await api.get(`/vehicles/${id}`);
        console.log('🚗 Vehicle API Response:', response.data);
        console.log('📋 Vehicle data keys:', Object.keys(response.data));
        console.log('🔍 Vehicle properties:', {
          name: response.data.name,
          seats: response.data.seats,
          transmission: response.data.transmission,
          fuel_type: response.data.fuel_type,
          location: response.data.location,
          category: response.data.category
        });
        setVehicle({ id: response.data.id, ...response.data });
      } catch (error) {
        console.error('Error fetching vehicle:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchVehicle();
  }, [id]);

  useEffect(() => {
    const calculatePrice = async () => {
      if (!vehicle || !formData.startDate || !formData.endDate) return;
      
      const start = new Date(formData.startDate);
      const end = new Date(formData.endDate);
      const baseRate = vehicle.current_price || vehicle.base_daily_rate || 150;
      
      // First show sync result with cached/fallback data
      const syncResult = pricingService.calculatePrice(
        baseRate,
        vehicle.category || 'Sedan',
        start,
        end,
        formData.city,
        formData.pickup,
        formData.dropoff
      );
      setPricingResult(syncResult);

      // Then use UNIFIED PRICING API for consistent pricing with chatbot
      setCompetitorLoading(true);
      try {
        const asyncResult = await pricingService.calculatePriceAsync(
          baseRate,
          vehicle.category || 'Sedan',
          start,
          end,
          formData.city,
          formData.pickup,
          formData.dropoff,
          id  // Pass vehicle ID for unified pricing API
        );
        setPricingResult(asyncResult);
      } catch (error) {
        console.error('Error fetching competitor prices:', error);
        // Keep sync result if async fails
      } finally {
        setCompetitorLoading(false);
      }
    };

    calculatePrice();
  }, [vehicle, formData.startDate, formData.endDate, formData.city, formData.pickup, formData.dropoff, id]);

  if (loading) {
    return (
      <div className="min-h-screen pt-24 pb-16" style={{ backgroundColor: 'var(--bg-primary)' }}>
        <div className="container-custom flex flex-col items-center justify-center py-20">
          <Loader2 className="h-10 w-10 animate-spin mb-4" style={{ color: 'var(--accent-primary)' }} />
          <p className="text-theme-secondary">Loading vehicle details...</p>
        </div>
      </div>
    );
  }

  if (!vehicle) {
    return (
      <div className="min-h-screen pt-24 pb-16" style={{ backgroundColor: 'var(--bg-primary)' }}>
        <div className="container-custom">
          <div className="card text-center py-16">
            <h2 className="text-2xl font-semibold text-theme-primary mb-3">Vehicle Not Found</h2>
            <p className="text-theme-secondary mb-6">The vehicle you're looking for doesn't exist.</p>
            <button onClick={() => navigate('/vehicles')} className="btn-primary">
              <ArrowLeft className="h-5 w-5 mr-2" />
              Back to Vehicles
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen pt-24 pb-16" style={{ backgroundColor: 'var(--bg-primary)' }}>
      <div className="container-custom">
        {/* Back Button */}
        <button 
          onClick={() => navigate('/vehicles')} 
          className="flex items-center text-theme-secondary hover:text-theme-primary transition-colors mb-8"
        >
          <ArrowLeft className="h-5 w-5 mr-2" />
          Back to Vehicles
        </button>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Image Section */}
          <div>
            <div className="card overflow-hidden p-0">
              <div className="relative h-96 bg-gray-100 dark:bg-white/5">
                {vehicle.image ? (
                  <img
                    src={vehicle.image}
                    alt={vehicle.name}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center">
                    <span className="text-8xl opacity-30">🚗</span>
                  </div>
                )}
                {/* Category Badge */}
                <div className="absolute top-4 right-4">
                  <span className="badge-info">{vehicle.category}</span>
                </div>
              </div>
            </div>

            {/* Vehicle Features */}
            <div className="grid grid-cols-2 gap-4 mt-6">
              <div className="card-hover">
                <div className="flex items-center">
                  <div className="p-2 rounded-lg bg-blue-50 dark:bg-blue-500/10 mr-3">
                    <Users className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                  </div>
                  <div>
                    <p className="text-xs text-theme-muted">Seats</p>
                    <p className="font-semibold text-theme-primary">{vehicle.seats} Passengers</p>
                  </div>
                </div>
              </div>
              <div className="card-hover">
                <div className="flex items-center">
                  <div className="p-2 rounded-lg bg-gray-100 dark:bg-white/5 mr-3">
                    <Settings className="h-5 w-5 text-gray-600 dark:text-gray-400" />
                  </div>
                  <div>
                    <p className="text-xs text-theme-muted">Transmission</p>
                    <p className="font-semibold text-theme-primary">{vehicle.transmission}</p>
                  </div>
                </div>
              </div>
              <div className="card-hover">
                <div className="flex items-center">
                  <div className="p-2 rounded-lg bg-emerald-50 dark:bg-emerald-500/10 mr-3">
                    <Fuel className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
                  </div>
                  <div>
                    <p className="text-xs text-theme-muted">Fuel Type</p>
                    <p className="font-semibold text-theme-primary">{vehicle.fuel_type}</p>
                  </div>
                </div>
              </div>
              <div className="card-hover">
                <div className="flex items-center">
                  <div className="p-2 rounded-lg bg-amber-50 dark:bg-amber-500/10 mr-3">
                    <MapPin className="h-5 w-5 text-amber-600 dark:text-amber-400" />
                  </div>
                  <div>
                    <p className="text-xs text-theme-muted">Location</p>
                    <p className="font-semibold text-theme-primary">{vehicle.location}</p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Booking Form Section */}
          <div className="card">
            <h1 className="text-3xl font-bold text-theme-primary mb-2">{vehicle.name}</h1>
            <p className="text-theme-secondary mb-6">{vehicle.make} {vehicle.model} {vehicle.year}</p>

            {/* Rental Details Form */}
            <div className="space-y-5">
              <h3 className="font-semibold text-lg text-theme-primary flex items-center">
                <Calendar className="h-5 w-5 mr-2" style={{ color: 'var(--accent-primary)' }} />
                Select Dates
              </h3>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-theme-secondary mb-2">Start Date</label>
                  <input
                    type="date"
                    className="input w-full"
                    value={formData.startDate}
                    min={new Date().toISOString().split('T')[0]}
                    onChange={(e) => setFormData({ ...formData, startDate: e.target.value })}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-theme-secondary mb-2">End Date</label>
                  <input
                    type="date"
                    className="input w-full"
                    value={formData.endDate}
                    min={formData.startDate}
                    onChange={(e) => setFormData({ ...formData, endDate: e.target.value })}
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-theme-secondary mb-2 flex items-center">
                  <MapPin className="h-4 w-4 mr-1" style={{ color: 'var(--accent-primary)' }} />
                  City
                </label>
                <select
                  className="select w-full"
                  value={formData.city}
                  onChange={(e) => setFormData({ ...formData, city: e.target.value })}
                >
                  <option value="Riyadh">Riyadh</option>
                  <option value="Jeddah">Jeddah</option>
                  <option value="Dammam">Dammam</option>
                  <option value="Mecca">Mecca</option>
                  <option value="Medina">Medina</option>
                </select>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-theme-secondary mb-2">Pickup Location</label>
                  <select
                    className="select w-full"
                    value={formData.pickup}
                    onChange={(e) => setFormData({ ...formData, pickup: e.target.value })}
                  >
                    <option value="Riyadh Airport">Riyadh Airport</option>
                    <option value="Riyadh City">Riyadh City Center</option>
                    <option value="Jeddah Airport">Jeddah Airport</option>
                    <option value="Jeddah City">Jeddah City Center</option>
                    <option value="Dammam Airport">Dammam Airport</option>
                    <option value="Dammam City">Dammam City Center</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-theme-secondary mb-2">Dropoff Location</label>
                  <select
                    className="select w-full"
                    value={formData.dropoff}
                    onChange={(e) => setFormData({ ...formData, dropoff: e.target.value })}
                  >
                    <option value="Riyadh Airport">Riyadh Airport</option>
                    <option value="Riyadh City">Riyadh City Center</option>
                    <option value="Jeddah Airport">Jeddah Airport</option>
                    <option value="Jeddah City">Jeddah City Center</option>
                    <option value="Dammam Airport">Dammam Airport</option>
                    <option value="Dammam City">Dammam City Center</option>
                  </select>
                </div>
              </div>

              {pricingResult && (
                <>
                  {/* Dynamic Price Display */}
                  <div className="p-6 rounded-xl bg-blue-50 dark:bg-blue-500/10" style={{ border: '1px solid var(--border-color)' }}>
                    <div className="flex justify-between items-start mb-4">
                      <div>
                        <p className="text-sm text-theme-secondary mb-1 flex items-center">
                          <Info className="h-4 w-4 mr-1" style={{ color: 'var(--accent-primary)' }} />
                          AI-Powered Dynamic Price
                        </p>
                        <div className="flex items-baseline gap-3">
                          <span className="text-4xl font-bold gradient-text">{pricingResult.dailyPrice} SAR</span>
                          <span className="text-sm text-theme-secondary">/day</span>
                        </div>
                        {pricingResult.savings > 0 && (
                          <div className="flex items-center gap-2 mt-2">
                            <span className="text-sm line-through text-theme-muted">{Math.round(vehicle.base_daily_rate)} SAR</span>
                            <span className="text-sm font-medium text-emerald-500 flex items-center">
                              <TrendingDown className="h-4 w-4 mr-1" />
                              Save {pricingResult.savings} SAR
                            </span>
                          </div>
                        )}
                      </div>
                      <div className="text-right">
                        <p className="text-sm text-theme-secondary">Total</p>
                        <p className="text-2xl font-bold text-theme-primary">{pricingResult.totalPrice} SAR</p>
                        <p className="text-xs text-theme-muted mt-1">
                          {Math.ceil((new Date(formData.endDate).getTime() - new Date(formData.startDate).getTime()) / (1000 * 60 * 60 * 24))} days
                        </p>
                      </div>
                    </div>
                    
                    {/* Pricing Factors */}
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      {pricingResult.factors.advanceBookingDiscount > 0 && (
                        <div className="flex items-center text-emerald-400">
                          <span className="mr-1">✓</span>
                          <span>Early booking: -{Math.round(pricingResult.factors.advanceBookingDiscount * 100)}%</span>
                        </div>
                      )}
                      {pricingResult.factors.durationDiscount > 0 && (
                        <div className="flex items-center text-emerald-400">
                          <span className="mr-1">✓</span>
                          <span>Duration discount: -{Math.round(pricingResult.factors.durationDiscount * 100)}%</span>
                        </div>
                      )}
                      {formData.pickup !== formData.dropoff && (
                        <div className="flex items-center text-amber-400">
                          <span className="mr-1">!</span>
                          <span>One-way rental: +15%</span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Competitor Comparison */}
                  <div className="card">
                    <h4 className="font-semibold text-sm mb-3 flex items-center text-theme-primary">
                      <Info className="h-4 w-4 mr-2" style={{ color: 'var(--accent-primary)' }} />
                      Competitor Price Comparison
                      {competitorLoading && (
                        <span className="ml-2 text-xs text-theme-muted animate-pulse">Fetching live data...</span>
                      )}
                    </h4>
                    
                    {/* One-way rental warning */}
                    {pricingResult.isOneWay && pricingResult.competitorDataLimited && (
                      <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-2 mb-3">
                        <p className="text-xs text-amber-400 flex items-center">
                          <span className="mr-1">⚠️</span>
                          <span>One-way rental: Competitor prices are estimates (+25% applied)</span>
                        </p>
                      </div>
                    )}

                    {/* No competitor data for this category warning */}
                    {!pricingResult.isOneWay && pricingResult.competitorDataLimited && (
                      <div className="bg-blue-50 dark:bg-blue-500/10 rounded-lg p-2 mb-3" style={{ border: '1px solid var(--border-color)' }}>
                        <p className="text-xs flex items-center" style={{ color: 'var(--accent-primary)' }}>
                          <span className="mr-1">ℹ️</span>
                          <span>Limited competitor data for this vehicle class. Price based on standard rates.</span>
                        </p>
                      </div>
                    )}
                    
                    <div className="space-y-2">
                      {pricingResult.competitors.map((comp: any, idx: number) => (
                        <div key={idx} className="flex justify-between items-center text-sm py-2 last:border-0" style={{ borderBottom: '1px solid var(--border-color)' }}>
                          <div className="flex flex-col">
                            <span className="text-theme-secondary">
                              {comp.company}
                              {comp.isEstimate && (
                                <span className="ml-1 text-xs text-amber-500 font-medium">(Est.)</span>
                              )}
                            </span>
                            {comp.vehicleName && (
                              <span className="text-xs text-theme-muted">{comp.vehicleName}</span>
                            )}
                          </div>
                          <div className="text-right">
                            <span className="font-medium text-theme-primary">{Math.round(comp.dailyRate)} SAR/day</span>
                            {comp.sourceUrl && (
                              <a 
                                href={comp.sourceUrl} 
                                target="_blank" 
                                rel="noopener noreferrer"
                                className="block text-xs hover:underline" style={{ color: 'var(--accent-primary)' }}
                              >
                                View source
                              </a>
                            )}
                          </div>
                        </div>
                      ))}
                      <div className="pt-3 mt-3" style={{ borderTop: '1px solid var(--border-color)' }}>
                        <div className="flex justify-between items-center font-semibold">
                          <span className="gradient-text">OUR PRICE {pricingResult.dailyPrice <= pricingResult.factors.competitorAvg ? '(You save!)' : '(Premium)'}</span>
                          <span className="gradient-text">{pricingResult.dailyPrice} SAR/day</span>
                        </div>
                        {pricingResult.dailyPrice < pricingResult.factors.competitorAvg ? (
                          <p className="text-xs text-emerald-400 mt-1">
                            ⭐ {Math.round(((pricingResult.factors.competitorAvg - pricingResult.dailyPrice) / pricingResult.factors.competitorAvg) * 100)}% cheaper than competitors!
                          </p>
                        ) : pricingResult.dailyPrice > pricingResult.factors.competitorAvg ? (
                          <p className="text-xs text-amber-400 mt-1">
                            👑 Premium service: {Math.round(((pricingResult.dailyPrice - pricingResult.factors.competitorAvg) / pricingResult.factors.competitorAvg) * 100)}% above market (includes quality guarantee)
                          </p>
                        ) : (
                          <p className="text-xs mt-1" style={{ color: 'var(--accent-primary)' }}>
                            ✓ Competitive market rate
                          </p>
                        )}
                      </div>
                      {/* Show when data was last scraped */}
                      {pricingResult.lastScraped && (
                        <div className="pt-2 mt-2" style={{ borderTop: '1px solid var(--border-color)' }}>
                          <p className="text-xs text-theme-muted">
                            📊 Prices scraped: {new Date(pricingResult.lastScraped).toLocaleString('en-SA', { 
                              dateStyle: 'medium', 
                              timeStyle: 'short' 
                            })}
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                </>
              )}

              <button
                onClick={() => navigate(`/booking/${id}`, { state: { ...formData, price: pricingResult?.totalPrice } })}
                disabled={!pricingResult}
                className="btn-primary w-full py-4 justify-center text-base"
              >
                Proceed to Booking
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
