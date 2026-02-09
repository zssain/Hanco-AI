import { Routes, Route } from 'react-router-dom';
import { Layout } from './components/Layout';

// Pages
// import { Home } from './pages/Home'; // Not used
import { Dashboard } from './pages/Dashboard';
import { Vehicles } from './pages/Vehicles';
import { VehicleDetails } from './pages/VehicleDetails';
import { Booking } from './pages/Booking';
import { MyBookings } from './pages/MyBookings';
import { Payment } from './pages/Payment';
import { Admin } from './pages/Admin';
import { NotFound } from './pages/NotFound';

export function AppRouter() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="vehicles" element={<Vehicles />} />
        <Route path="vehicles/:id" element={<VehicleDetails />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="booking/:id" element={<Booking />} />
        <Route path="my-bookings" element={<MyBookings />} />
        <Route path="payment" element={<Payment />} />
        <Route path="admin" element={<Admin />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
