import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Calendar, MapPin, Car, Trash2, AlertCircle, Loader2, Eye } from 'lucide-react';
import api from '@/lib/api';
import { getOrCreateGuestId } from '@/utils/guestId';

interface Booking {
  id: string;
  vehicle_id: string;
  vehicle_name?: string;
  start_date: string;
  end_date: string;
  pickup_location: string;
  dropoff_location: string;
  total_price: number;
  status: string;
  created_at: string;
}

export function MyBookings() {
  const navigate = useNavigate();
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchBookings();
  }, []);

  const fetchBookings = async () => {
    try {
      const guestId = getOrCreateGuestId();
      
      const response = await api.get('/bookings', {
        headers: {
          'X-Guest-Id': guestId
        }
      });
      
      const bookingsData = response.data.bookings || [];
      setBookings(bookingsData);
    } catch (err: any) {
      console.error('Error fetching bookings:', err);
      setError('Failed to load bookings');
    } finally {
      setLoading(false);
    }
  };

  const handleCancelBooking = async (bookingId: string) => {
    if (!window.confirm('Are you sure you want to cancel this booking?')) {
      return;
    }

    try {
      const guestId = getOrCreateGuestId();
      
      await api.delete(`/bookings/${bookingId}`, {
        headers: {
          'X-Guest-Id': guestId
        }
      });
      
      setBookings(bookings.filter(b => b.id !== bookingId));
    } catch (err: any) {
      alert('Failed to cancel booking');
    }
  };

  const getStatusBadge = (status: string) => {
    const statusConfig: Record<string, { class: string; label: string }> = {
      pending: { class: 'badge-warning', label: 'Pending' },
      confirmed: { class: 'badge-success', label: 'Confirmed' },
      active: { class: 'badge-info', label: 'Active' },
      completed: { class: 'bg-zinc-500/10 text-zinc-400 border border-zinc-500/20', label: 'Completed' },
      cancelled: { class: 'bg-red-500/10 text-red-400 border border-red-500/20', label: 'Cancelled' },
    };

    const config = statusConfig[status] || statusConfig.pending;

    return (
      <span className={`badge ${config.class}`}>
        {config.label}
      </span>
    );
  };

  if (loading) {
    return (
      <div className="min-h-screen pt-24 pb-16" style={{ backgroundColor: 'var(--bg-primary)' }}>
        <div className="container-custom flex flex-col items-center justify-center py-20">
          <Loader2 className="h-10 w-10 animate-spin mb-4" style={{ color: 'var(--accent-primary)' }} />
          <p className="text-theme-secondary">Loading your bookings...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen pt-24 pb-16" style={{ backgroundColor: 'var(--bg-primary)' }}>
      <div className="container-custom">
        {/* Header */}
        <div className="mb-10">
          <h1 className="text-4xl font-bold text-theme-primary mb-3">My Bookings</h1>
          <p className="text-theme-secondary">Manage your vehicle reservations</p>
        </div>

        {error && (
          <div className="bg-red-500/10 border border-red-500/20 text-red-400 px-4 py-3 rounded-xl mb-6 flex items-center animate-fade-in">
            <AlertCircle className="h-5 w-5 mr-2" />
            {error}
          </div>
        )}

        {bookings.length === 0 ? (
          <div className="card text-center py-16">
            <div className="p-4 rounded-2xl bg-blue-50 dark:bg-blue-500/10 w-fit mx-auto mb-6">
              <Car className="h-12 w-12 text-blue-600 dark:text-blue-400" />
            </div>
            <h2 className="text-2xl font-semibold text-theme-primary mb-3">No Bookings Yet</h2>
            <p className="text-theme-secondary mb-8 max-w-md mx-auto">
              Start exploring our premium fleet and make your first booking!
            </p>
            <button
              onClick={() => navigate('/vehicles')}
              className="btn-primary"
            >
              Browse Fleet
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-6">
            {bookings.map((booking) => (
              <div key={booking.id} className="card-hover">
                <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
                  <div className="flex-1">
                    <div className="flex items-start justify-between mb-4">
                      <div>
                        <h3 className="font-semibold text-lg text-theme-primary flex items-center">
                          <div className="p-2 rounded-lg bg-blue-50 dark:bg-blue-500/10 mr-3">
                            <Car className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                          </div>
                          {booking.vehicle_name || `Vehicle #${booking.vehicle_id}`}
                        </h3>
                        <p className="text-sm text-theme-muted mt-1 ml-12">Booking ID: {booking.id}</p>
                      </div>
                      {getStatusBadge(booking.status)}
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 text-sm mb-4">
                      <div className="flex items-center text-theme-secondary">
                        <Calendar className="h-4 w-4 mr-3" style={{ color: 'var(--accent-primary)' }} />
                        <div>
                          <p className="text-xs text-theme-muted">Start Date</p>
                          <p className="font-medium text-theme-primary">{booking.start_date}</p>
                        </div>
                      </div>

                      <div className="flex items-center text-theme-secondary">
                        <Calendar className="h-4 w-4 mr-3 text-gray-500" />
                        <div>
                          <p className="text-xs text-theme-muted">End Date</p>
                          <p className="font-medium text-theme-primary">{booking.end_date}</p>
                        </div>
                      </div>

                      <div className="flex items-center text-theme-secondary">
                        <MapPin className="h-4 w-4 mr-3 text-emerald-500" />
                        <div>
                          <p className="text-xs text-theme-muted">Pickup</p>
                          <p className="font-medium text-theme-primary">{booking.pickup_location}</p>
                        </div>
                      </div>

                      <div className="flex items-center text-theme-secondary">
                        <MapPin className="h-4 w-4 mr-3 text-amber-500" />
                        <div>
                          <p className="text-xs text-theme-muted">Dropoff</p>
                          <p className="font-medium text-theme-primary">{booking.dropoff_location}</p>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center justify-between pt-4" style={{ borderTop: '1px solid var(--border-color)' }}>
                      <div>
                        <span className="text-sm text-theme-muted">Total Amount</span>
                        <span className="ml-2 text-2xl font-bold gradient-text">{booking.total_price || 'N/A'} SAR</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex lg:flex-col gap-3">
                    {(booking.status === 'pending' || booking.status === 'confirmed') && (
                      <button
                        onClick={() => handleCancelBooking(booking.id)}
                        className="btn-secondary text-red-400 hover:text-red-300 hover:border-red-500/30"
                      >
                        <Trash2 className="h-4 w-4 mr-2" />
                        Cancel
                      </button>
                    )}
                    <button
                      onClick={() => navigate(`/vehicles/${booking.vehicle_id}`)}
                      className="btn-secondary"
                    >
                      <Eye className="h-4 w-4 mr-2" />
                      View Vehicle
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
