import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import api from '@/lib/api';
import { getOrCreateGuestId } from '@/utils/guestId';
import { 
  Car, MessageSquare, TrendingUp, Award, Bot, 
  ArrowUpRight, Calendar
} from 'lucide-react';

interface BookingActivity {
  id: string;
  [key: string]: any;
}

interface DashboardData {
  total_bookings: number;
  loyalty_points: number;
  saved_amount: string;
  ai_bookings: number;
  recent_activity: BookingActivity[];
}

export function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [dashboardData, setDashboardData] = useState<DashboardData>({
    total_bookings: 0,
    loyalty_points: 0,
    saved_amount: 'SAR 0',
    ai_bookings: 0,
    recent_activity: []
  });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchDashboard = async () => {
  
      
      try {
        setLoading(true);
        
        const guestId = getOrCreateGuestId();
        
        // Fetch bookings from backend API
        const response = await api.get('/bookings', {
          headers: {
            'X-Guest-Id': guestId
          }
        });
        
        const bookingsData = response.data.bookings || [];
        
        const totalBookings = bookingsData.length;
        const totalSpent = bookingsData.reduce((sum: number, b: any) => sum + (b.total_price || 0), 0);
        const savedAmount = totalSpent * 0.1; // Assume 10% savings from dynamic pricing
        
        setDashboardData({
          total_bookings: totalBookings,
          loyalty_points: totalBookings * 10,
          saved_amount: `SAR ${savedAmount.toFixed(0)}`,
          ai_bookings: bookingsData.filter((b: any) => b.guest_id).length, // Count guest bookings from chatbot
          recent_activity: bookingsData.slice(0, 5)
        });
      } catch (error) {
        console.error('Error fetching dashboard:', error);
        // Set default data on error
        setDashboardData({
          total_bookings: 0,
          loyalty_points: 0,
          saved_amount: 'SAR 0',
          ai_bookings: 0,
          recent_activity: []
        });
      } finally {
        setLoading(false);
      }
    };

    fetchDashboard();
  }, [user]);

  const stats = [
    {
      label: 'Total Bookings',
      value: loading ? '...' : dashboardData.total_bookings,
      subtext: 'Since joining',
      icon: Calendar,
      iconBg: 'bg-blue-50 dark:bg-blue-500/10',
      iconColor: 'text-blue-600 dark:text-blue-400',
    },
    {
      label: 'Loyalty Points',
      value: loading ? '...' : dashboardData.loyalty_points.toLocaleString(),
      subtext: 'Redeem for discounts',
      icon: Award,
      iconBg: 'bg-amber-50 dark:bg-amber-500/10',
      iconColor: 'text-amber-600 dark:text-amber-400',
    },
    {
      label: 'Saved Amount',
      value: loading ? '...' : dashboardData.saved_amount,
      subtext: 'Through dynamic pricing',
      icon: TrendingUp,
      iconBg: 'bg-emerald-50 dark:bg-emerald-500/10',
      iconColor: 'text-emerald-600 dark:text-emerald-400',
    },
    {
      label: 'AI Bookings',
      value: loading ? '...' : dashboardData.ai_bookings,
      subtext: 'Via chatbot',
      icon: Bot,
      iconBg: 'bg-gray-100 dark:bg-white/5',
      iconColor: 'text-gray-600 dark:text-gray-400',
    },
  ];

  return (
    <div className="min-h-screen pt-24 pb-16" style={{ backgroundColor: 'var(--bg-primary)' }}>
      <div className="container-custom">
        {/* Header */}
        <div className="mb-10 flex items-center gap-5">
          <img
            src="/teclusion.png"
            alt="Teclusion"
            className="h-16 w-16 rounded-2xl object-contain shadow-md border border-[var(--border-color)] bg-white dark:bg-white/10 p-1"
          />
          <div>
            <h1 className="text-4xl font-bold text-theme-primary mb-1">
              Welcome back, <span className="gradient-text">{user?.displayName || user?.email?.split('@')[0]}</span>!
            </h1>
            <p className="text-theme-secondary">Here's an overview of your activity</p>
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-10">
          {stats.map((stat, index) => (
            <div key={index} className="card-hover group">
              <div className="flex items-start justify-between mb-4">
                <div className={`p-3 rounded-xl ${stat.iconBg}`}>
                  <stat.icon className={`h-6 w-6 ${stat.iconColor}`} />
                </div>
                <ArrowUpRight className="h-5 w-5 text-theme-muted group-hover:text-theme-primary transition-colors" />
              </div>
              <div className="stat-value text-3xl">{stat.value}</div>
              <p className="text-theme-secondary text-sm mt-1">{stat.label}</p>
              <p className="text-theme-muted text-xs mt-1">{stat.subtext}</p>
            </div>
          ))}
        </div>

        {/* Quick Actions */}
        <div className="card overflow-hidden">
          <h2 className="text-xl font-semibold text-theme-primary mb-6">Quick Actions</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Browse Fleet */}
            <button
              onClick={() => navigate('/vehicles')}
              className="group relative p-6 rounded-xl bg-blue-50 dark:bg-blue-500/5 border border-[var(--border-color)] hover:border-blue-300 dark:hover:border-blue-500/30 transition-all overflow-hidden"
            >
              <div className="relative flex items-center space-x-4">
                <div className="p-3 rounded-xl bg-blue-600 group-hover:scale-105 transition-transform">
                  <Car className="h-6 w-6 text-white" />
                </div>
                <div className="text-left">
                  <h3 className="font-semibold text-theme-primary text-lg">Browse Fleet</h3>
                  <p className="text-theme-secondary text-sm">Find your perfect ride</p>
                </div>
              </div>
              <ArrowUpRight className="absolute top-4 right-4 h-5 w-5 text-theme-muted group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors" />
            </button>

            {/* AI Assistant */}
            <button
              onClick={() => {
                const chatButton = document.querySelector('button[aria-label="Open chat"]') as HTMLButtonElement;
                if (chatButton) chatButton.click();
              }}
              className="group relative p-6 rounded-xl bg-gray-50 dark:bg-white/5 border border-[var(--border-color)] hover:border-gray-300 dark:hover:border-white/20 transition-all overflow-hidden"
            >
              <div className="relative flex items-center space-x-4">
                <div className="p-3 rounded-xl bg-gray-700 dark:bg-gray-600 group-hover:scale-105 transition-transform">
                  <MessageSquare className="h-6 w-6 text-white" />
                </div>
                <div className="text-left">
                  <h3 className="font-semibold text-theme-primary text-lg">AI Assistant</h3>
                  <p className="text-theme-secondary text-sm">Chat with our AI bot</p>
                </div>
              </div>
              <ArrowUpRight className="absolute top-4 right-4 h-5 w-5 text-theme-muted group-hover:text-theme-primary transition-colors" />
            </button>

            {/* My Bookings */}
            <button
              onClick={() => navigate('/my-bookings')}
              className="group relative p-6 rounded-xl bg-emerald-50 dark:bg-emerald-500/5 border border-[var(--border-color)] hover:border-emerald-300 dark:hover:border-emerald-500/30 transition-all overflow-hidden"
            >
              <div className="relative flex items-center space-x-4">
                <div className="p-3 rounded-xl bg-emerald-600 group-hover:scale-105 transition-transform">
                  <Calendar className="h-6 w-6 text-white" />
                </div>
                <div className="text-left">
                  <h3 className="font-semibold text-theme-primary text-lg">My Bookings</h3>
                  <p className="text-theme-secondary text-sm">View your reservations</p>
                </div>
              </div>
              <ArrowUpRight className="absolute top-4 right-4 h-5 w-5 text-theme-muted group-hover:text-emerald-600 dark:group-hover:text-emerald-400 transition-colors" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
