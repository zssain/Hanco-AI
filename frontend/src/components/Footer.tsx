import { Link } from 'react-router-dom';
import { Mail, Phone, MapPin, Linkedin, Twitter, Instagram } from 'lucide-react';

export function Footer() {
  return (
    <footer className="border-t border-[var(--border-color)] mt-auto" style={{ backgroundColor: 'var(--bg-secondary)' }}>
      {/* Main Footer */}
      <div className="container-custom py-16">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-12">
          {/* Brand */}
          <div className="lg:col-span-1">
            <Link to="/" className="flex items-center space-x-3 mb-6">
              <img 
                src="/teclusion.png" 
                alt="Dynamic Pricing Engine" 
                className="h-10 w-10 object-contain"
              />
              <span className="text-xl font-bold text-theme-primary">Dynamic Pricing Engine</span>
            </Link>
            <p className="text-theme-secondary text-sm leading-relaxed mb-6">
              AI-powered car rental platform in Saudi Arabia. Experience intelligent pricing and seamless booking.
            </p>
            <div className="flex space-x-4">
              <a href="#" className="p-2 rounded-lg bg-gray-100 dark:bg-white/5 text-theme-secondary hover:text-blue-600 dark:hover:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-500/10 transition-all">
                <Linkedin className="h-5 w-5" />
              </a>
              <a href="#" className="p-2 rounded-lg bg-gray-100 dark:bg-white/5 text-theme-secondary hover:text-blue-600 dark:hover:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-500/10 transition-all">
                <Twitter className="h-5 w-5" />
              </a>
              <a href="#" className="p-2 rounded-lg bg-gray-100 dark:bg-white/5 text-theme-secondary hover:text-blue-600 dark:hover:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-500/10 transition-all">
                <Instagram className="h-5 w-5" />
              </a>
            </div>
          </div>

          {/* Quick Links */}
          <div>
            <h3 className="font-semibold text-theme-primary mb-6">Quick Links</h3>
            <ul className="space-y-4">
              <li>
                <Link to="/" className="text-theme-secondary hover:text-theme-primary transition-colors text-sm">
                  Home
                </Link>
              </li>
              <li>
                <Link to="/vehicles" className="text-theme-secondary hover:text-theme-primary transition-colors text-sm">
                  Fleet
                </Link>
              </li>
              <li>
                <Link to="/my-bookings" className="text-theme-secondary hover:text-theme-primary transition-colors text-sm">
                  My Bookings
                </Link>
              </li>
              <li>
                <Link to="/dashboard" className="text-theme-secondary hover:text-theme-primary transition-colors text-sm">
                  Dashboard
                </Link>
              </li>
            </ul>
          </div>

          {/* Cities */}
          <div>
            <h3 className="font-semibold text-theme-primary mb-6">Our Locations</h3>
            <ul className="space-y-4">
              <li className="flex items-center space-x-2 text-theme-secondary text-sm">
                <MapPin className="h-4 w-4 text-theme-muted" />
                <span>Riyadh</span>
              </li>
              <li className="flex items-center space-x-2 text-theme-secondary text-sm">
                <MapPin className="h-4 w-4 text-theme-muted" />
                <span>Jeddah</span>
              </li>
              <li className="flex items-center space-x-2 text-theme-secondary text-sm">
                <MapPin className="h-4 w-4 text-theme-muted" />
                <span>Dammam</span>
              </li>
              <li className="flex items-center space-x-2 text-theme-secondary text-sm">
                <MapPin className="h-4 w-4 text-theme-muted" />
                <span>Makkah</span>
              </li>
            </ul>
          </div>

          {/* Contact */}
          <div>
            <h3 className="font-semibold text-theme-primary mb-6">Contact Us</h3>
            <ul className="space-y-4">
              <li>
                <a href="mailto:info@teclusion.ai" className="flex items-center space-x-3 text-theme-secondary hover:text-theme-primary transition-colors text-sm group">
                  <div className="p-2 rounded-lg bg-gray-100 dark:bg-white/5 group-hover:bg-blue-50 dark:group-hover:bg-blue-500/10 transition-colors">
                    <Mail className="h-4 w-4" />
                  </div>
                  <span>info@teclusion.ai</span>
                </a>
              </li>
              <li>
                <a href="tel:+966501234567" className="flex items-center space-x-3 text-theme-secondary hover:text-theme-primary transition-colors text-sm group">
                  <div className="p-2 rounded-lg bg-gray-100 dark:bg-white/5 group-hover:bg-blue-50 dark:group-hover:bg-blue-500/10 transition-colors">
                    <Phone className="h-4 w-4" />
                  </div>
                  <span>+966 50 123 4567</span>
                </a>
              </li>
            </ul>
          </div>
        </div>
      </div>

      {/* Bottom Bar */}
      <div className="border-t border-[var(--border-color)]">
        <div className="container-custom py-6">
          <div className="flex flex-col md:flex-row justify-between items-center space-y-4 md:space-y-0">
            <p className="text-theme-muted text-sm">
              © {new Date().getFullYear()} Dynamic Pricing Engine — All rights reserved.
            </p>
            <div className="flex space-x-6 text-sm">
              <a href="#" className="text-theme-muted hover:text-theme-primary transition-colors">Privacy Policy</a>
              <a href="#" className="text-theme-muted hover:text-theme-primary transition-colors">Terms of Service</a>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
}
