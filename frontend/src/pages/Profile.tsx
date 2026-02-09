import { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import { User, Mail, Phone, MapPin, Camera, Save, LogOut, Car, Calendar, CreditCard } from 'lucide-react';

export function Profile() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState({
    name: user?.displayName || 'Guest User',
    email: user?.email || '',
    phone: '+966 50 123 4567',
    address: 'Riyadh, Saudi Arabia'
  });

  const handleSave = () => {
    // TODO: Implement profile update API call
    setIsEditing(false);
  };

  const handleLogout = async () => {
    await logout();
    navigate('/');
  };

  if (!user) {
    return (
      <div className="min-h-screen py-12" style={{ backgroundColor: 'var(--bg-primary)' }}>
        <div className="container-custom">
          <div className="max-w-md mx-auto text-center">
            <div className="card p-8">
              <div className="w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-6" style={{ backgroundColor: 'var(--accent-primary)' }}>
                <User className="h-10 w-10 text-white" />
              </div>
              <h2 className="text-2xl font-bold text-theme-primary mb-2">Sign In Required</h2>
              <p className="text-theme-secondary mb-6">Please sign in to view your profile</p>
              <button
                onClick={() => navigate('/login')}
                className="btn-primary w-full justify-center py-3"
              >
                Sign In
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen py-12" style={{ backgroundColor: 'var(--bg-primary)' }}>
      <div className="container-custom">
        <h1 className="text-3xl md:text-4xl font-bold mb-8 text-theme-primary">
          My <span className="gradient-text">Profile</span>
        </h1>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Profile Card */}
          <div className="lg:col-span-1">
            <div className="card text-center">
              <div className="relative inline-block mb-4">
                <div className="w-24 h-24 rounded-full flex items-center justify-center mx-auto" style={{ backgroundColor: 'var(--accent-primary)' }}>
                  <span className="text-3xl font-bold text-white">
                    {formData.name.charAt(0).toUpperCase()}
                  </span>
                </div>
                <button className="absolute bottom-0 right-0 w-8 h-8 rounded-full flex items-center justify-center hover:opacity-90 transition-colors" style={{ backgroundColor: 'var(--accent-primary)' }}>
                  <Camera className="h-4 w-4 text-white" />
                </button>
              </div>
              <h2 className="text-xl font-bold text-theme-primary mb-1">{formData.name}</h2>
              <p className="text-theme-secondary text-sm mb-4">{formData.email}</p>
              <div className="flex justify-center gap-2 mb-6">
                <span className="px-3 py-1 bg-blue-50 dark:bg-blue-500/10 rounded-full text-xs font-medium" style={{ color: 'var(--accent-primary)' }}>
                  Premium Member
                </span>
                <span className="px-3 py-1 bg-green-500/20 text-green-500 rounded-full text-xs font-medium">
                  Verified
                </span>
              </div>
              <button
                onClick={handleLogout}
                className="w-full py-3 bg-red-500/10 text-red-500 rounded-xl font-medium hover:bg-red-500/20 transition-colors flex items-center justify-center"
              >
                <LogOut className="h-4 w-4 mr-2" />
                Sign Out
              </button>
            </div>

            {/* Quick Stats */}
            <div className="card mt-6">
              <h3 className="text-lg font-semibold text-theme-primary mb-4">Quick Stats</h3>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center text-theme-secondary">
                    <Car className="h-4 w-4 mr-2" style={{ color: 'var(--accent-primary)' }} />
                    Total Rentals
                  </div>
                  <span className="text-theme-primary font-semibold">12</span>
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center text-theme-secondary">
                    <Calendar className="h-4 w-4 mr-2 text-gray-500" />
                    Active Bookings
                  </div>
                  <span className="text-theme-primary font-semibold">1</span>
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center text-theme-secondary">
                    <CreditCard className="h-4 w-4 mr-2 text-green-500" />
                    Total Spent
                  </div>
                  <span className="text-theme-primary font-semibold">4,500 SAR</span>
                </div>
              </div>
            </div>
          </div>

          {/* Profile Details */}
          <div className="lg:col-span-2">
            <div className="card">
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-xl font-semibold text-theme-primary">Profile Information</h3>
                {!isEditing ? (
                  <button
                    onClick={() => setIsEditing(true)}
                    className="px-4 py-2 bg-blue-50 dark:bg-blue-500/10 rounded-lg text-sm font-medium hover:bg-blue-100 dark:hover:bg-blue-500/20 transition-colors"
                    style={{ color: 'var(--accent-primary)' }}
                  >
                    Edit Profile
                  </button>
                ) : (
                  <button
                    onClick={handleSave}
                    className="btn-primary py-2"
                  >
                    <Save className="h-4 w-4 mr-2" />
                    Save Changes
                  </button>
                )}
              </div>

              <div className="space-y-6">
                <div>
                  <label className="block text-sm font-medium text-theme-secondary mb-2 flex items-center">
                    <User className="h-4 w-4 mr-2" style={{ color: 'var(--accent-primary)' }} />
                    Full Name
                  </label>
                  {isEditing ? (
                    <input
                      type="text"
                      className="input"
                      value={formData.name}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    />
                  ) : (
                    <p className="text-theme-primary rounded-xl px-4 py-3" style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border-color)' }}>{formData.name}</p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-theme-secondary mb-2 flex items-center">
                    <Mail className="h-4 w-4 mr-2" style={{ color: 'var(--accent-primary)' }} />
                    Email Address
                  </label>
                  {isEditing ? (
                    <input
                      type="email"
                      className="input"
                      value={formData.email}
                      onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    />
                  ) : (
                    <p className="text-theme-primary rounded-xl px-4 py-3" style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border-color)' }}>{formData.email}</p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-theme-secondary mb-2 flex items-center">
                    <Phone className="h-4 w-4 mr-2" style={{ color: 'var(--accent-primary)' }} />
                    Phone Number
                  </label>
                  {isEditing ? (
                    <input
                      type="tel"
                      className="input"
                      value={formData.phone}
                      onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                    />
                  ) : (
                    <p className="text-theme-primary rounded-xl px-4 py-3" style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border-color)' }}>{formData.phone}</p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-theme-secondary mb-2 flex items-center">
                    <MapPin className="h-4 w-4 mr-2" style={{ color: 'var(--accent-primary)' }} />
                    Address
                  </label>
                  {isEditing ? (
                    <input
                      type="text"
                      className="input"
                      value={formData.address}
                      onChange={(e) => setFormData({ ...formData, address: e.target.value })}
                    />
                  ) : (
                    <p className="text-theme-primary rounded-xl px-4 py-3" style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border-color)' }}>{formData.address}</p>
                  )}
                </div>
              </div>
            </div>

            {/* Preferences Card */}
            <div className="card mt-6">
              <h3 className="text-xl font-semibold text-theme-primary mb-6">Preferences</h3>
              <div className="space-y-4">
                <label className="flex items-center justify-between p-4 rounded-xl cursor-pointer hover:bg-gray-50 dark:hover:bg-white/5 transition-colors" style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border-color)' }}>
                  <div>
                    <span className="text-theme-primary font-medium">Email Notifications</span>
                    <p className="text-theme-muted text-sm">Receive booking updates and promotions</p>
                  </div>
                  <input type="checkbox" defaultChecked className="w-5 h-5 rounded focus:ring-blue-500" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-color)', accentColor: 'var(--accent-primary)' }} />
                </label>
                <label className="flex items-center justify-between p-4 rounded-xl cursor-pointer hover:bg-gray-50 dark:hover:bg-white/5 transition-colors" style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border-color)' }}>
                  <div>
                    <span className="text-theme-primary font-medium">SMS Notifications</span>
                    <p className="text-theme-muted text-sm">Get text alerts for important updates</p>
                  </div>
                  <input type="checkbox" className="w-5 h-5 rounded focus:ring-blue-500" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-color)', accentColor: 'var(--accent-primary)' }} />
                </label>
                <label className="flex items-center justify-between p-4 rounded-xl cursor-pointer hover:bg-gray-50 dark:hover:bg-white/5 transition-colors" style={{ backgroundColor: 'var(--bg-card)', border: '1px solid var(--border-color)' }}>
                  <div>
                    <span className="text-theme-primary font-medium">Marketing Communications</span>
                    <p className="text-theme-muted text-sm">Receive special offers and deals</p>
                  </div>
                  <input type="checkbox" defaultChecked className="w-5 h-5 rounded focus:ring-blue-500" style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border-color)', accentColor: 'var(--accent-primary)' }} />
                </label>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
