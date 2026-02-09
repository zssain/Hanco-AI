import { useState, useEffect } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import api from '@/lib/api';
import { useAuth } from '../contexts/AuthContext';
import { pricingService } from '../services/pricingService';
import { getOrCreateGuestId } from '@/utils/guestId';
import { Calendar, CreditCard, MapPin, Car, CheckCircle, Shield, Info } from 'lucide-react';

export function Booking() {
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();
  const [vehicle, setVehicle] = useState<any>(null);
  const [formData, setFormData] = useState({
    startDate: location.state?.startDate || '',
    endDate: location.state?.endDate || '',
    city: location.state?.city || 'Riyadh',
    pickup: location.state?.pickup || 'Riyadh Airport',
    dropoff: location.state?.dropoff || 'Riyadh Airport',
    cardNumber: '',
    expiryDate: '',
    cvv: '',
    cardName: '',
    guestName: '',
    guestEmail: '',
    guestPhone: ''
  });
  const [insuranceSelected, setInsuranceSelected] = useState(false);
  const [pricingResult, setPricingResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [bookingId, setBookingId] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    const fetchVehicle = async () => {
      try {
        if (!id) return;
        const response = await api.get(`/vehicles/${id}`);
        setVehicle({ id: response.data.id, ...response.data });
      } catch (error) {
        console.error('Error fetching vehicle:', error);
      }
    };

    fetchVehicle();
  }, [id]);

  useEffect(() => {
    // Use async unified pricing for consistent pricing with chatbot
    const calculateUnifiedPrice = async () => {
      if (formData.startDate && formData.endDate && vehicle) {
        const start = new Date(formData.startDate);
        const end = new Date(formData.endDate);
        const baseRate = vehicle.current_price || vehicle.base_daily_rate || 150;
        
        // Pass vehicleId to use unified pricing API (same as chatbot)
        const result = await pricingService.calculatePriceAsync(
          baseRate,
          vehicle.category || 'Sedan',
          start,
          end,
          formData.city,
          formData.pickup,
          formData.dropoff,
          id  // vehicle ID for unified pricing
        );
        
        setPricingResult(result);
      }
    };
    
    calculateUnifiedPrice();
  }, [formData.startDate, formData.endDate, formData.city, formData.pickup, formData.dropoff, vehicle, id]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      // Guest bookings are allowed - no authentication required

      if (!pricingResult) {
        throw new Error('Price calculation failed');
      }

      // Get or create guest ID for tracking
      const guestId = getOrCreateGuestId();

      // Calculate insurance amount
      const insuranceAmount = insuranceSelected ? Math.round(pricingResult.totalPrice * 0.15) : 0;
      const finalTotal = pricingResult.totalPrice + insuranceAmount;

      // Create booking via API
      const bookingData = {
        vehicle_id: id,
        start_date: formData.startDate,
        end_date: formData.endDate,
        pickup_location: formData.pickup,
        dropoff_location: formData.dropoff,
        total_price: finalTotal,
        daily_price: pricingResult.dailyPrice,
        insurance_selected: insuranceSelected,
        insurance_amount: insuranceAmount,
        guest_name: !user ? formData.guestName : undefined,
        guest_email: !user ? formData.guestEmail : undefined,
        guest_phone: !user ? formData.guestPhone : undefined,
      };

      const response = await api.post('/bookings', bookingData, {
        headers: {
          'X-Guest-Id': guestId
        }
      });
      
      setBookingId(response.data.id || response.data.booking_id);
      setSuccess(true);
    } catch (err: any) {
      setError(err.message || 'Booking failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="min-h-screen py-12" style={{ backgroundColor: 'var(--bg-primary)' }}>
        <div className="container-custom">
          <div className="max-w-2xl mx-auto text-center">
            <div className="card p-8 animate-scale-in">
              <div className="w-20 h-20 bg-emerald-500 rounded-full flex items-center justify-center mx-auto mb-6">
                <CheckCircle className="h-10 w-10 text-white" />
              </div>
              <h1 className="text-3xl font-bold text-theme-primary mb-2">Booking Confirmed!</h1>
              <p className="text-theme-secondary mb-8">Your vehicle has been successfully booked.</p>
              
              <div className="card rounded-xl p-6 mb-8 text-left">
                <h2 className="font-semibold text-lg mb-4 text-theme-primary flex items-center">
                  <Info className="h-5 w-5 mr-2" style={{ color: 'var(--accent-primary)' }} />
                  Booking Details
                </h2>
                <div className="space-y-3 text-sm">
                  <div className="flex justify-between py-2" style={{ borderBottom: '1px solid var(--border-color)' }}>
                    <span className="text-theme-secondary">Booking ID:</span>
                    <span className="font-mono font-semibold" style={{ color: 'var(--accent-primary)' }}>{bookingId}</span>
                  </div>
                  <div className="flex justify-between py-2" style={{ borderBottom: '1px solid var(--border-color)' }}>
                    <span className="text-theme-secondary">Vehicle:</span>
                    <span className="font-semibold text-theme-primary">{vehicle?.name}</span>
                  </div>
                  <div className="flex justify-between py-2" style={{ borderBottom: '1px solid var(--border-color)' }}>
                    <span className="text-theme-secondary">Duration:</span>
                    <span className="text-theme-primary">{formData.startDate} to {formData.endDate}</span>
                  </div>
                  <div className="flex justify-between py-2" style={{ borderBottom: '1px solid var(--border-color)' }}>
                    <span className="text-theme-secondary">Total Paid:</span>
                    <span className="font-bold" style={{ color: 'var(--accent-primary)' }}>{pricingResult?.totalPrice} SAR</span>
                  </div>
                  <div className="flex justify-between py-2" style={{ borderBottom: '1px solid var(--border-color)' }}>
                    <span className="text-theme-secondary">Daily Rate:</span>
                    <span className="font-semibold text-theme-primary">{pricingResult?.dailyPrice} SAR/day</span>
                  </div>
                  <div className="flex justify-between py-2">
                    <span className="text-theme-secondary">Status:</span>
                    <span className="px-3 py-1 bg-green-500/20 text-green-400 rounded-full text-xs font-medium">
                      Confirmed
                    </span>
                  </div>
                </div>
              </div>

              <div className="flex gap-4">
                <button
                  onClick={() => navigate('/my-bookings')}
                  className="btn-primary flex-1 py-3 justify-center"
                >
                  View My Bookings
                </button>
                <button
                  onClick={() => navigate('/vehicles')}
                  className="flex-1 btn-secondary py-3 justify-center"
                >
                  Browse Fleet
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!vehicle) {
    return (
      <div className="min-h-screen py-12 flex items-center justify-center" style={{ backgroundColor: 'var(--bg-primary)' }}>
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-blue-200 dark:border-blue-500/30 rounded-full animate-spin mx-auto mb-4" style={{ borderTopColor: 'var(--accent-primary)' }}></div>
          <p className="text-theme-secondary">Loading booking details...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen py-12" style={{ backgroundColor: 'var(--bg-primary)' }}>
      <div className="container-custom">
        <h1 className="text-3xl md:text-4xl font-bold mb-8 text-theme-primary">
          Complete Your <span className="gradient-text">Booking</span>
        </h1>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2">
            <form onSubmit={handleSubmit} className="space-y-6">
              {error && (
                <div className="bg-red-500/10 border border-red-500/30 text-red-400 px-4 py-3 rounded-xl">
                  {error}
                </div>
              )}

            {/* Guest Information - only shown if not logged in */}
            {!user && (
              <div className="card">
                <h2 className="text-xl font-semibold mb-4 text-theme-primary flex items-center">
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center mr-3" style={{ backgroundColor: 'var(--accent-primary)' }}>
                    <svg className="h-4 w-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                    </svg>
                  </div>
                  Your Information
                </h2>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium mb-2 text-theme-secondary">Full Name</label>
                    <input
                      type="text"
                      className="input"
                      placeholder="John Doe"
                      required
                      value={formData.guestName}
                      onChange={(e) => setFormData({ ...formData, guestName: e.target.value })}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2 text-theme-secondary">Email</label>
                    <input
                      type="email"
                      className="input"
                      placeholder="john@example.com"
                      required
                      value={formData.guestEmail}
                      onChange={(e) => setFormData({ ...formData, guestEmail: e.target.value })}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2 text-theme-secondary">Phone Number</label>
                    <input
                      type="tel"
                      className="input"
                      placeholder="+966 50 123 4567"
                      required
                      value={formData.guestPhone}
                      onChange={(e) => setFormData({ ...formData, guestPhone: e.target.value })}
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Rental Period */}
            <div className="card">
              <h2 className="text-xl font-semibold mb-4 flex items-center text-theme-primary">
                <div className="w-8 h-8 rounded-lg flex items-center justify-center mr-3" style={{ backgroundColor: 'var(--accent-primary)' }}>
                  <Calendar className="h-4 w-4 text-white" />
                </div>
                Rental Period
              </h2>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-2 text-theme-secondary">Start Date</label>
                  <input
                    type="date"
                    className="input"
                    required
                    min={new Date().toISOString().split('T')[0]}
                    value={formData.startDate}
                    onChange={(e) => setFormData({ ...formData, startDate: e.target.value })}
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2 text-theme-secondary">End Date</label>
                  <input
                    type="date"
                    className="input"
                    required
                    min={formData.startDate}
                    value={formData.endDate}
                    onChange={(e) => setFormData({ ...formData, endDate: e.target.value })}
                  />
                </div>
              </div>

              <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-2 flex items-center text-theme-secondary">
                    <MapPin className="h-4 w-4 mr-1" style={{ color: 'var(--accent-primary)' }} />
                    City
                  </label>
                  <select
                    className="input"
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

                <div>
                  <label className="block text-sm font-medium mb-2 text-theme-secondary">Pickup Location</label>
                  <select
                    className="input"
                    value={formData.pickup}
                    onChange={(e) => setFormData({ ...formData, pickup: e.target.value })}
                  >
                    <option value="Riyadh Airport">Riyadh Airport</option>
                    <option value="Riyadh Downtown">Riyadh Downtown</option>
                    <option value="Jeddah Airport">Jeddah Airport</option>
                    <option value="Jeddah Corniche">Jeddah Corniche</option>
                    <option value="Dammam Airport">Dammam Airport</option>
                    <option value="Dammam City">Dammam City</option>
                    <option value="Mecca Central">Mecca Central</option>
                    <option value="Medina Airport">Medina Airport</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2 text-theme-secondary">Dropoff Location</label>
                  <select
                    className="input"
                    value={formData.dropoff}
                    onChange={(e) => setFormData({ ...formData, dropoff: e.target.value })}
                  >
                    <option value="Riyadh Airport">Riyadh Airport</option>
                    <option value="Riyadh Downtown">Riyadh Downtown</option>
                    <option value="Jeddah Airport">Jeddah Airport</option>
                    <option value="Jeddah Corniche">Jeddah Corniche</option>
                    <option value="Dammam Airport">Dammam Airport</option>
                    <option value="Dammam City">Dammam City</option>
                    <option value="Mecca Central">Mecca Central</option>
                    <option value="Medina Airport">Medina Airport</option>
                  </select>
                </div>
              </div>
            </div>

            {/* Insurance Option */}
            <div className="card">
              <h2 className="text-xl font-semibold mb-4 flex items-center text-theme-primary">
                <div className="w-8 h-8 rounded-lg flex items-center justify-center mr-3" style={{ backgroundColor: 'var(--accent-primary)' }}>
                  <Shield className="h-4 w-4 text-white" />
                </div>
                Insurance Protection
              </h2>
              
              <div className="rounded-xl p-4" style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border-color)' }}>
                <label className="flex items-start cursor-pointer group">
                  <input
                    type="checkbox"
                    checked={insuranceSelected}
                    onChange={(e) => setInsuranceSelected(e.target.checked)}
                    className="mt-1 h-5 w-5 rounded focus:ring-blue-500"
                    style={{ borderColor: 'var(--border-color)', backgroundColor: 'var(--bg-card)', accentColor: 'var(--accent-primary)' }}
                  />
                  <div className="ml-3">
                    <span className="font-semibold text-theme-primary group-hover:opacity-80 transition-colors">Comprehensive Insurance Coverage</span>
                    <p className="text-sm text-theme-secondary mt-1">
                      Protect your rental with full coverage including collision damage, theft protection, and roadside assistance.
                    </p>
                    <p className="text-sm font-medium mt-2" style={{ color: 'var(--accent-primary)' }}>
                      +15% of rental total ({pricingResult ? Math.round(pricingResult.totalPrice * 0.15) : 0} SAR)
                    </p>
                  </div>
                </label>
              </div>
            </div>

            {/* Payment */}
            <div className="card">
              <h2 className="text-xl font-semibold mb-4 flex items-center text-theme-primary">
                <div className="w-8 h-8 rounded-lg flex items-center justify-center mr-3" style={{ backgroundColor: 'var(--accent-primary)' }}>
                  <CreditCard className="h-4 w-4 text-white" />
                </div>
                Payment Information
              </h2>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-2 text-theme-secondary">Cardholder Name</label>
                  <input
                    type="text"
                    className="input"
                    placeholder="John Doe"
                    required
                    value={formData.cardName}
                    onChange={(e) => setFormData({ ...formData, cardName: e.target.value })}
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2 text-theme-secondary">Card Number</label>
                  <input
                    type="text"
                    className="input"
                    placeholder="1234 5678 9012 3456"
                    required
                    maxLength={19}
                    value={formData.cardNumber}
                    onChange={(e) => setFormData({ ...formData, cardNumber: e.target.value })}
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-2 text-theme-secondary">Expiry Date</label>
                    <input
                      type="text"
                      className="input"
                      placeholder="MM/YY"
                      required
                      maxLength={5}
                      value={formData.expiryDate}
                      onChange={(e) => setFormData({ ...formData, expiryDate: e.target.value })}
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium mb-2 text-theme-secondary">CVV</label>
                    <input
                      type="text"
                      className="input"
                      placeholder="123"
                      required
                      maxLength={4}
                      value={formData.cvv}
                      onChange={(e) => setFormData({ ...formData, cvv: e.target.value })}
                    />
                  </div>
                </div>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading || !pricingResult}
              className="btn-primary w-full py-4 justify-center text-base"
            >
              {loading ? (
                <>
                  <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2"></div>
                  Processing...
                </>
              ) : (
                `Confirm Booking & Pay ${pricingResult ? (pricingResult.totalPrice + (insuranceSelected ? Math.round(pricingResult.totalPrice * 0.15) : 0)) : 0} SAR`
              )}
            </button>
          </form>
        </div>

        {/* Summary Sidebar */}
        <div className="lg:col-span-1">
          <div className="card sticky top-24">
            <h2 className="text-xl font-semibold mb-4 flex items-center text-theme-primary">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center mr-3" style={{ backgroundColor: 'var(--accent-primary)' }}>
                <Car className="h-4 w-4 text-white" />
              </div>
              Booking Summary
            </h2>

            <div className="mb-4">
              <img
                src={vehicle.image || 'https://via.placeholder.com/400x200'}
                alt={vehicle.name}
                className="w-full rounded-xl mb-3"
                style={{ border: '1px solid var(--border-color)' }}
              />
              <h3 className="font-semibold text-lg text-theme-primary">{vehicle.name}</h3>
              <p className="text-sm text-theme-secondary">{vehicle.make} {vehicle.model}</p>
            </div>

            <div className="pt-4 space-y-3" style={{ borderTop: '1px solid var(--border-color)' }}>
              <div className="flex justify-between text-sm">
                <span className="text-theme-secondary">Start Date:</span>
                <span className="font-medium text-theme-primary">{formData.startDate || '-'}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-theme-secondary">End Date:</span>
                <span className="font-medium text-theme-primary">{formData.endDate || '-'}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-theme-secondary">Pickup:</span>
                <span className="font-medium text-theme-primary">{formData.pickup}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-theme-secondary">Dropoff:</span>
                <span className="font-medium text-theme-primary">{formData.dropoff}</span>
              </div>
            </div>

            {pricingResult && (
              <div className="mt-4 pt-4" style={{ borderTop: '1px solid var(--border-color)' }}>
                <div className="space-y-2 mb-3">
                  <div className="flex justify-between text-sm">
                    <span className="text-theme-secondary">Daily Rate:</span>
                    <span className="font-medium text-theme-primary">{pricingResult.dailyPrice} SAR/day</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-theme-secondary">Duration:</span>
                    <span className="font-medium text-theme-primary">{pricingResult.days} days</span>
                  </div>
                  {pricingResult.savings > 0 && (
                    <div className="flex justify-between text-sm">
                      <span className="text-theme-secondary">You Save:</span>
                      <span className="font-medium text-green-500">-{pricingResult.savings} SAR</span>
                    </div>
                  )}
                  <div className="flex justify-between text-sm">
                    <span className="text-theme-secondary">Subtotal:</span>
                    <span className="font-medium text-theme-primary">{pricingResult.totalPrice} SAR</span>
                  </div>
                  {insuranceSelected && (
                    <div className="flex justify-between text-sm">
                      <span className="text-theme-secondary">Insurance (15%):</span>
                      <span className="font-medium" style={{ color: 'var(--accent-primary)' }}>+{Math.round(pricingResult.totalPrice * 0.15)} SAR</span>
                    </div>
                  )}
                </div>
                <div className="flex justify-between items-center pt-3" style={{ borderTop: '1px solid var(--border-color)' }}>
                  <span className="text-lg font-semibold text-theme-primary">Total Amount:</span>
                  <span className="text-2xl font-bold" style={{ color: 'var(--accent-primary)' }}>
                    {pricingResult.totalPrice + (insuranceSelected ? Math.round(pricingResult.totalPrice * 0.15) : 0)} SAR
                  </span>
                </div>
                <p className="text-xs text-theme-muted mt-1">
                  {insuranceSelected ? 'Includes insurance & dynamic pricing' : 'Includes dynamic pricing & taxes'}
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  </div>
  );
}
