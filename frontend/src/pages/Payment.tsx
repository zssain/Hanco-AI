import { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { auth } from '@/lib/firebase';
import { CreditCard, Shield, Lock, Calendar, MapPin, Car } from 'lucide-react';

interface BookingDetails {
  booking_id: string;
  vehicle_name: string;
  start_date: string;
  end_date: string;
  pickup_location: string;
  total_price: number;
  status: string;
}

export function Payment() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const bookingId = searchParams.get('booking_id');

  const [booking, setBooking] = useState<BookingDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState('');

  // Card form state
  const [cardNumber, setCardNumber] = useState('');
  const [cardName, setCardName] = useState('');
  const [expiryDate, setExpiryDate] = useState('');
  const [cvv, setCvv] = useState('');

  useEffect(() => {
    if (!bookingId) {
      setError('No booking ID provided');
      setLoading(false);
      return;
    }

    // Fetch booking details
    const fetchBooking = async () => {
      try {
        // SECURITY: Get fresh token from Firebase auth (not localStorage)
        if (!auth.currentUser) {
          setError('You must be logged in to view this page');
          setLoading(false);
          navigate('/login');
          return;
        }
        const token = await auth.currentUser.getIdToken();
        const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
        const response = await axios.get(
          `${API_BASE_URL}/api/v1/bookings/${bookingId}`,
          {
            headers: { Authorization: `Bearer ${token}` },
          }
        );

        const data = response.data;
        setBooking({
          booking_id: data.booking_id,
          vehicle_name: data.selected_vehicle?.name || 'Vehicle',
          start_date: data.start_date,
          end_date: data.end_date,
          pickup_location: data.pickup_location,
          total_price: data.pricing_info?.recommended_price?.total_price || 0,
          status: data.status,
        });
      } catch (err: any) {
        console.error('Error fetching booking:', err);
        setError(err.response?.data?.detail || 'Failed to load booking details');
      } finally {
        setLoading(false);
      }
    };

    fetchBooking();
  }, [bookingId]);

  const handlePayment = async (e: React.FormEvent) => {
    e.preventDefault();
    setProcessing(true);
    setError('');

    try {
      // SECURITY: Get fresh token from Firebase auth (not localStorage)
      if (!auth.currentUser) {
        setError('You must be logged in to make payments');
        setProcessing(false);
        navigate('/login');
        return;
      }
      const token = await auth.currentUser.getIdToken();
      const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
      const response = await axios.post(
        `${API_BASE_URL}/api/v1/payments/pay`,
        {
          booking_id: bookingId,
          card_number: cardNumber.replace(/\s/g, ''),
          card_holder: cardName,
          expiry_date: expiryDate,
          cvv: cvv,
          amount: booking?.total_price || 0,
        },
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );

      if (response.data.status === 'success') {
        // Payment successful - redirect to bookings
        alert('✅ Payment successful! Your booking is confirmed.');
        navigate('/my-bookings');
      } else {
        setError(response.data.message || 'Payment failed');
      }
    } catch (err: any) {
      console.error('Payment error:', err);
      setError(err.response?.data?.detail || 'Payment processing failed');
    } finally {
      setProcessing(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: 'var(--bg-primary)' }}>
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-blue-200 dark:border-blue-500/30 rounded-full animate-spin mx-auto mb-4" style={{ borderTopColor: 'var(--accent-primary)' }}></div>
          <p className="text-theme-secondary">Loading booking details...</p>
        </div>
      </div>
    );
  }

  if (error && !booking) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: 'var(--bg-primary)' }}>
        <div className="text-center">
          <div className="w-16 h-16 bg-red-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
            <span className="text-2xl">❌</span>
          </div>
          <p className="text-red-400 text-xl mb-4">{error}</p>
          <button
            onClick={() => navigate('/my-bookings')}
            className="btn-primary"
          >
            Go to My Bookings
          </button>
        </div>
      </div>
    );
  }

  if (!booking) {
    return null;
  }

  // Format card number with spaces
  const formatCardNumber = (value: string) => {
    const cleaned = value.replace(/\s/g, '');
    const groups = cleaned.match(/.{1,4}/g);
    return groups ? groups.join(' ') : cleaned;
  };

  return (
    <div className="min-h-screen py-12 px-4 sm:px-6 lg:px-8" style={{ backgroundColor: 'var(--bg-primary)' }}>
      <div className="max-w-4xl mx-auto">
        <div className="card overflow-hidden">
          {/* Header */}
          <div className="px-6 py-8 -m-6 mb-6" style={{ backgroundColor: 'var(--accent-primary)' }}>
            <h1 className="text-3xl font-bold text-white flex items-center">
              <Lock className="h-8 w-8 mr-3" />
              Complete Payment
            </h1>
            <p className="text-white/70 mt-2">Secure payment for your booking</p>
          </div>

          <div className="grid md:grid-cols-2 gap-8">
            {/* Booking Summary */}
            <div className="space-y-4">
              <h2 className="text-xl font-semibold text-theme-primary mb-4 flex items-center">
                <Car className="h-5 w-5 mr-2" style={{ color: 'var(--accent-primary)' }} />
                Booking Summary
              </h2>
              
              <div className="rounded-xl p-4 space-y-3" style={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border-color)' }}>
                <div className="flex justify-between py-2" style={{ borderBottom: '1px solid var(--border-color)' }}>
                  <span className="text-theme-secondary">Booking ID:</span>
                  <span className="font-mono text-sm" style={{ color: 'var(--accent-primary)' }}>{booking.booking_id.slice(0, 12)}...</span>
                </div>
                
                <div className="flex justify-between py-2" style={{ borderBottom: '1px solid var(--border-color)' }}>
                  <span className="text-theme-secondary">Vehicle:</span>
                  <span className="font-semibold text-theme-primary">{booking.vehicle_name}</span>
                </div>
                
                <div className="flex justify-between py-2" style={{ borderBottom: '1px solid var(--border-color)' }}>
                  <span className="text-theme-secondary flex items-center">
                    <Calendar className="h-4 w-4 mr-1" />
                    Dates:
                  </span>
                  <span className="text-theme-primary">{booking.start_date} to {booking.end_date}</span>
                </div>
                
                <div className="flex justify-between py-2" style={{ borderBottom: '1px solid var(--border-color)' }}>
                  <span className="text-theme-secondary flex items-center">
                    <MapPin className="h-4 w-4 mr-1" />
                    Pickup:
                  </span>
                  <span className="text-theme-primary">{booking.pickup_location}</span>
                </div>
                
                <div className="pt-3 mt-3">
                  <div className="flex justify-between items-center">
                    <span className="text-lg font-semibold text-theme-primary">Total Amount:</span>
                    <span className="text-2xl font-bold" style={{ color: 'var(--accent-primary)' }}>{booking.total_price} SAR</span>
                  </div>
                </div>
              </div>

              <div className="flex items-start space-x-2 text-sm text-theme-secondary p-3 rounded-xl bg-blue-50 dark:bg-blue-500/10" style={{ border: '1px solid var(--border-color)' }}>
                <Shield className="h-5 w-5 flex-shrink-0 mt-0.5" style={{ color: 'var(--accent-primary)' }} />
                <p>Your payment is secured with industry-standard encryption</p>
              </div>
            </div>

            {/* Payment Form */}
            <div className="space-y-4">
              <h2 className="text-xl font-semibold text-theme-primary mb-4 flex items-center">
                <CreditCard className="h-5 w-5 mr-2" style={{ color: 'var(--accent-primary)' }} />
                Payment Details
              </h2>
              
              <form onSubmit={handlePayment} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-theme-secondary mb-2">
                    Card Number
                  </label>
                  <input
                    type="text"
                    value={cardNumber}
                    onChange={(e) => {
                      const formatted = formatCardNumber(e.target.value);
                      if (formatted.replace(/\s/g, '').length <= 16) {
                        setCardNumber(formatted);
                      }
                    }}
                    placeholder="1234 5678 9012 3456"
                    className="input"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-theme-secondary mb-2">
                    Cardholder Name
                  </label>
                  <input
                    type="text"
                    value={cardName}
                    onChange={(e) => setCardName(e.target.value)}
                    placeholder="John Doe"
                    className="input"
                    required
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-theme-secondary mb-2">
                      Expiry Date
                    </label>
                    <input
                      type="text"
                      value={expiryDate}
                      onChange={(e) => {
                        let value = e.target.value.replace(/\D/g, '');
                        if (value.length >= 2) {
                          value = value.slice(0, 2) + '/' + value.slice(2, 4);
                        }
                        setExpiryDate(value);
                      }}
                      placeholder="MM/YY"
                      maxLength={5}
                      className="input"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-theme-secondary mb-2">
                      CVV
                    </label>
                    <input
                      type="text"
                      value={cvv}
                      onChange={(e) => {
                        const value = e.target.value.replace(/\D/g, '');
                        if (value.length <= 3) {
                          setCvv(value);
                        }
                      }}
                      placeholder="123"
                      maxLength={3}
                      className="input"
                      required
                    />
                  </div>
                </div>

                {error && (
                  <div className="bg-red-500/10 border border-red-500/30 text-red-400 px-4 py-3 rounded-xl">
                    {error}
                  </div>
                )}

                <button
                  type="submit"
                  disabled={processing}
                  className="btn-primary w-full py-4 justify-center text-base"
                >
                  {processing ? (
                    <span className="flex items-center justify-center">
                      <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2"></div>
                      Processing...
                    </span>
                  ) : (
                    `Pay ${booking.total_price} SAR`
                  )}
                </button>
              </form>

              <div className="text-xs text-center rounded-xl p-3" style={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border-color)' }}>
                <p className="flex items-center justify-center text-theme-secondary">
                  <CreditCard className="h-4 w-4 mr-1" />
                  Test Card: 4242 4242 4242 4242
                </p>
                <p className="text-theme-muted mt-1">Any future expiry date and 3-digit CVV</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
