import { useState, useEffect } from 'react';
import api from '@/lib/api';
import { BarChart3, DollarSign, Car, Users, Calendar, TrendingUp } from 'lucide-react';

interface Booking {
  id: string;
  vehicle_id: string;
  vehicle_name?: string;
  start_date: string;
  end_date: string;
  status: string;
  total_amount: number;
  created_at: string;
}

export function Admin() {
  const [stats, setStats] = useState({
    totalBookings: 0,
    totalRevenue: 0,
    totalVehicles: 0,
    totalUsers: 0
  });
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [bookingsRes, vehiclesRes] = await Promise.all([
          api.get('/bookings'),
          api.get('/vehicles')
        ]);

        const bookingsData = bookingsRes.data?.bookings || (Array.isArray(bookingsRes.data) ? bookingsRes.data : []);
        setBookings(bookingsData);
        
        const totalRevenue = bookingsData.reduce((sum: number, b: any) => sum + (b.total_amount || b.total_price || 0), 0);
        
        const vehiclesData = vehiclesRes.data?.vehicles || (Array.isArray(vehiclesRes.data) ? vehiclesRes.data : []);
        setStats({
          totalBookings: bookingsData.length,
          totalRevenue: totalRevenue,
          totalVehicles: vehiclesData.length,
          totalUsers: 0
        });
      } catch (error) {
        console.error('Error fetching admin data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  const getStatusBadge = (status: string) => {
    const statusClasses = {
      confirmed: 'bg-green-500/20 text-green-400 border border-green-500/30',
      pending: 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30',
      active: 'bg-blue-500/20 text-blue-400 border border-blue-500/30',
      completed: 'bg-gray-500/20 text-gray-400 border border-gray-500/30',
      cancelled: 'bg-red-500/20 text-red-400 border border-red-500/30'
    };

    return statusClasses[status as keyof typeof statusClasses] || 'bg-gray-500/20 text-gray-400 border border-gray-500/30';
  };

  if (loading) {
    return (
      <div className="min-h-screen py-12 flex items-center justify-center" style={{ backgroundColor: 'var(--bg-primary)' }}>
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-blue-200 dark:border-blue-500/30 rounded-full animate-spin mx-auto mb-4" style={{ borderTopColor: 'var(--accent-primary)' }}></div>
          <p className="text-theme-secondary">Loading admin dashboard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen py-8" style={{ backgroundColor: 'var(--bg-primary)' }}>
      <div className="container-custom">
        <div className="mb-8">
          <h1 className="text-3xl md:text-4xl font-bold mb-2 text-theme-primary">
            Admin <span className="gradient-text">Dashboard</span>
          </h1>
          <p className="text-theme-secondary">Manage bookings, vehicles, and platform analytics</p>
        </div>

        <div className="space-y-8">
          {/* Stats Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <div className="card group hover:border-blue-300 dark:hover:border-blue-500/30">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-theme-secondary mb-1">Total Bookings</p>
                  <p className="text-3xl font-bold" style={{ color: 'var(--accent-primary)' }}>{stats.totalBookings}</p>
                </div>
                <div className="w-12 h-12 rounded-xl flex items-center justify-center group-hover:scale-105 transition-transform" style={{ backgroundColor: 'var(--accent-primary)' }}>
                  <BarChart3 className="h-6 w-6 text-white" />
                </div>
              </div>
              <div className="flex items-center mt-3 text-sm text-theme-muted">
                <TrendingUp className="h-4 w-4 mr-1 text-green-500" />
                <span>All time bookings</span>
              </div>
            </div>

            <div className="card group hover:border-green-300 dark:hover:border-green-500/30">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-theme-secondary mb-1">Total Revenue</p>
                  <p className="text-3xl font-bold text-emerald-600 dark:text-emerald-400">{stats.totalRevenue.toFixed(0)} SAR</p>
                </div>
                <div className="w-12 h-12 bg-emerald-600 rounded-xl flex items-center justify-center group-hover:scale-105 transition-transform">
                  <DollarSign className="h-6 w-6 text-white" />
                </div>
              </div>
              <div className="flex items-center mt-3 text-sm text-theme-muted">
                <TrendingUp className="h-4 w-4 mr-1 text-green-500" />
                <span>Total earnings</span>
              </div>
            </div>

            <div className="card group hover:border-gray-300 dark:hover:border-gray-500/30">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-theme-secondary mb-1">Total Vehicles</p>
                  <p className="text-3xl font-bold text-gray-700 dark:text-gray-300">{stats.totalVehicles}</p>
                </div>
                <div className="w-12 h-12 bg-gray-600 rounded-xl flex items-center justify-center group-hover:scale-105 transition-transform">
                  <Car className="h-6 w-6 text-white" />
                </div>
              </div>
              <div className="flex items-center mt-3 text-sm text-theme-muted">
                <span>Fleet size</span>
              </div>
            </div>

            <div className="card group hover:border-blue-300 dark:hover:border-blue-500/30">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-theme-secondary mb-1">Active Users</p>
                  <p className="text-3xl font-bold text-blue-600 dark:text-blue-400">{stats.totalUsers}</p>
                </div>
                <div className="w-12 h-12 bg-blue-600 rounded-xl flex items-center justify-center group-hover:scale-105 transition-transform">
                  <Users className="h-6 w-6 text-white" />
                </div>
              </div>
              <div className="flex items-center mt-3 text-sm text-theme-muted">
                <span>Registered users</span>
              </div>
            </div>
          </div>

          {/* Recent Bookings Table */}
          <div className="card">
            <div className="p-6 border-b" style={{ borderColor: 'var(--border-color)' }}>
              <div className="flex items-center">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center mr-3" style={{ backgroundColor: 'var(--accent-primary)' }}>
                  <Calendar className="h-5 w-5 text-white" />
                </div>
                <div>
                  <h2 className="text-xl font-semibold text-theme-primary">Recent Bookings</h2>
                  <p className="text-theme-secondary text-sm">Latest booking transactions</p>
                </div>
              </div>
            </div>
            
            <div className="p-6">
              {bookings.length === 0 ? (
                <div className="text-center py-12">
                  <div className="w-16 h-16 bg-blue-50 dark:bg-blue-500/10 rounded-2xl flex items-center justify-center mx-auto mb-4">
                    <Calendar className="h-8 w-8 text-theme-muted" />
                  </div>
                  <p className="text-theme-secondary">No bookings yet</p>
                  <p className="text-theme-muted text-sm mt-1">Bookings will appear here once customers start renting</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b" style={{ borderColor: 'var(--border-color)' }}>
                        <th className="text-left py-3 px-4 text-theme-secondary font-medium text-sm uppercase tracking-wider">ID</th>
                        <th className="text-left py-3 px-4 text-theme-secondary font-medium text-sm uppercase tracking-wider">Vehicle</th>
                        <th className="text-left py-3 px-4 text-theme-secondary font-medium text-sm uppercase tracking-wider">Start Date</th>
                        <th className="text-left py-3 px-4 text-theme-secondary font-medium text-sm uppercase tracking-wider">End Date</th>
                        <th className="text-left py-3 px-4 text-theme-secondary font-medium text-sm uppercase tracking-wider">Status</th>
                        <th className="text-left py-3 px-4 text-theme-secondary font-medium text-sm uppercase tracking-wider">Total</th>
                      </tr>
                    </thead>
                    <tbody>
                      {bookings.slice(0, 10).map((booking) => (
                        <tr key={booking.id} className="border-b hover:bg-gray-50 dark:hover:bg-white/5 transition-colors" style={{ borderColor: 'var(--border-color)' }}>
                          <td className="py-4 px-4 font-mono text-sm" style={{ color: 'var(--accent-primary)' }}>{booking.id.slice(0, 8)}</td>
                          <td className="py-4 px-4 text-theme-primary">{booking.vehicle_name || booking.vehicle_id}</td>
                          <td className="py-4 px-4 text-theme-secondary">{new Date(booking.start_date).toLocaleDateString()}</td>
                          <td className="py-4 px-4 text-theme-secondary">{new Date(booking.end_date).toLocaleDateString()}</td>
                          <td className="py-4 px-4">
                            <span className={`px-3 py-1 rounded-full text-xs font-medium ${getStatusBadge(booking.status)}`}>
                              {booking.status}
                            </span>
                          </td>
                          <td className="py-4 px-4 font-semibold text-theme-primary">{booking.total_amount.toFixed(2)} SAR</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
