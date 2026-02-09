import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Filter, MapPin, Users, Settings, Star, Loader2 } from 'lucide-react';
import api from '@/lib/api';

export function Vehicles() {
  const navigate = useNavigate();
  const [vehicles, setVehicles] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    const fetchVehicles = async () => {
      try {
        // Fetch vehicles from API
        const response = await api.get('/vehicles');
        const vehiclesList = response.data.vehicles || [];
        setVehicles(vehiclesList);
      } catch (error) {
        console.error('Error fetching vehicles:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchVehicles();
  }, []);

  const filteredVehicles = vehicles.filter(vehicle => 
    vehicle.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    vehicle.make?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    vehicle.model?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="min-h-screen pt-24 pb-16" style={{ backgroundColor: 'var(--bg-primary)' }}>
      <div className="container-custom">
        {/* Header */}
        <div className="mb-10">
          <h1 className="text-4xl font-bold text-theme-primary mb-3">Our Fleet</h1>
          <p className="text-theme-secondary">Browse and select from our premium fleet</p>
        </div>

        {/* Search & Filters */}
        <div className="card mb-8">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-zinc-500" />
              <input
                type="text"
                placeholder="Search vehicles..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="input pl-12 w-full"
              />
            </div>
            <button className="btn-secondary flex items-center justify-center">
              <Filter className="h-4 w-4 mr-2" />
              Filters
            </button>
          </div>
        </div>

        {/* Vehicle Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {loading ? (
            <div className="col-span-full flex flex-col items-center justify-center py-20">
              <Loader2 className="h-10 w-10 animate-spin mb-4" style={{ color: 'var(--accent-primary)' }} />
              <p className="text-theme-secondary">Loading vehicles...</p>
            </div>
          ) : filteredVehicles.length > 0 ? (
            filteredVehicles.map((vehicle) => (
              <div
                key={vehicle.id}
                onClick={() => navigate(`/vehicles/${vehicle.id}`)}
                className="vehicle-card overflow-hidden"
              >
                {/* Image */}
                <div className="relative h-48 -mx-6 -mt-6 mb-6 overflow-hidden bg-gray-100 dark:bg-white/5">
                  {vehicle.image ? (
                    <img 
                      src={vehicle.image} 
                      alt={vehicle.name}
                      className="w-full h-full object-cover vehicle-image transition-transform duration-500"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <span className="text-6xl opacity-50">🚗</span>
                    </div>
                  )}
                  {/* Category Badge */}
                  <div className="absolute top-4 right-4">
                    <span className="badge-info">{vehicle.category}</span>
                  </div>
                </div>

                {/* Content */}
                <div>
                  <div className="flex justify-between items-start mb-2">
                    <h3 className="text-xl font-semibold text-theme-primary transition-colors">
                      {vehicle.name}
                    </h3>
                  </div>
                  
                  <p className="text-theme-muted text-sm mb-4">
                    {vehicle.make} {vehicle.model} {vehicle.year}
                  </p>

                  {/* Price */}
                  <div className="mb-4">
                    <span className="text-3xl font-bold gradient-text">
                      {vehicle.current_price || vehicle.base_daily_rate}
                    </span>
                    <span className="text-theme-muted text-sm ml-1">SAR/day</span>
                  </div>

                  {/* Features */}
                  <div className="flex items-center gap-4 text-sm text-theme-secondary mb-4">
                    <span className="flex items-center gap-1">
                      <MapPin className="h-4 w-4" style={{ color: 'var(--accent-primary)' }} />
                      {vehicle.location}
                    </span>
                  </div>

                  <div className="flex items-center gap-4 text-sm text-theme-secondary mb-6">
                    <span className="flex items-center gap-1">
                      <Users className="h-4 w-4" />
                      {vehicle.seats} seats
                    </span>
                    <span className="flex items-center gap-1">
                      <Settings className="h-4 w-4" />
                      {vehicle.transmission}
                    </span>
                    <span className="flex items-center gap-1">
                      <Star className="h-4 w-4 text-amber-400" />
                      {vehicle.rating}
                    </span>
                  </div>

                  {/* Footer */}
                  <div className="flex justify-between items-center pt-4" style={{ borderTop: '1px solid var(--border-color)' }}>
                    <span
                      className={`badge ${
                        vehicle.availability_status === 'available'
                          ? 'badge-success'
                          : 'badge-warning'
                      }`}
                    >
                      {vehicle.availability_status || 'Available'}
                    </span>
                    <button className="btn-primary text-sm py-2 px-4">
                      Book Now
                    </button>
                  </div>
                </div>
              </div>
            ))
          ) : (
            <div className="col-span-full">
              <div className="card text-center py-16">
                <div className="text-6xl mb-4">🚗</div>
                <h3 className="text-xl font-semibold text-theme-primary mb-2">No vehicles found</h3>
                <p className="text-theme-secondary">
                  {searchQuery 
                    ? 'Try adjusting your search criteria' 
                    : 'Please check if the backend is connected'}
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
