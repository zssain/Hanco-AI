import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { LayoutDashboard, Calendar, Car, Menu, X, MessageSquare, Sun, Moon } from 'lucide-react';
import { useTheme } from '../contexts/ThemeContext';

export function Navbar() {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const location = useLocation();
  const { toggleTheme, isDark } = useTheme();

  const isActive = (path: string) => location.pathname === path;

  const navLinks = [
    { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { path: '/my-bookings', label: 'My Bookings', icon: Calendar },
    { path: '/vehicles', label: 'Fleet', icon: Car },
  ];

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 glass-dark">
      <div className="container-custom">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link to="/" className="flex items-center space-x-3 group">
            <img 
              src="/teclusion.png" 
              alt="Dynamic Pricing Engine" 
              className="h-9 w-9 object-contain"
            />
            <span className="text-lg font-semibold text-theme-primary">Dynamic Pricing Engine</span>
          </Link>

          {/* Desktop Navigation Links */}
          <div className="hidden md:flex items-center space-x-6">
            {navLinks.map(({ path, label, icon: Icon }) => (
              <Link
                key={path}
                to={path}
                className={`nav-link flex items-center space-x-1.5 ${isActive(path) ? 'active' : ''}`}
              >
                {Icon && <Icon className="h-4 w-4" />}
                <span>{label}</span>
              </Link>
            ))}
          </div>

          {/* Right Section */}
          <div className="flex items-center space-x-2">
            {/* Theme Toggle */}
            <button
              onClick={toggleTheme}
              className="p-2 rounded-lg transition-all duration-200 hover:bg-gray-100 dark:hover:bg-white/10"
              aria-label="Toggle theme"
            >
              {isDark ? (
                <Sun className="h-5 w-5 text-amber-400" />
              ) : (
                <Moon className="h-5 w-5 text-gray-500" />
              )}
            </button>

            <Link 
              to="/dashboard" 
              className="hidden sm:flex btn-primary text-sm"
            >
              <MessageSquare className="h-4 w-4 mr-2" />
              AI Assistant
            </Link>

            {/* Mobile Menu Button */}
            <button 
              className="md:hidden p-2 text-theme-secondary hover:text-theme-primary transition-colors"
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
            >
              {isMobileMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
            </button>
          </div>
        </div>

        {/* Mobile Menu */}
        {isMobileMenuOpen && (
          <div className="md:hidden py-4 border-t border-[var(--border-color)] animate-slide-down">
            <div className="flex flex-col space-y-1">
              {navLinks.map(({ path, label, icon: Icon }) => (
                <Link
                  key={path}
                  to={path}
                  onClick={() => setIsMobileMenuOpen(false)}
                  className={`flex items-center space-x-2 px-4 py-2.5 rounded-lg transition-colors ${
                    isActive(path) 
                      ? 'bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400' 
                      : 'text-theme-secondary hover:text-theme-primary hover:bg-gray-50 dark:hover:bg-white/5'
                  }`}
                >
                  {Icon && <Icon className="h-4 w-4" />}
                  <span>{label}</span>
                </Link>
              ))}
              
              {/* Mobile Theme Toggle */}
              <button
                onClick={toggleTheme}
                className="flex items-center space-x-2 px-4 py-2.5 rounded-lg text-theme-secondary hover:text-theme-primary hover:bg-gray-50 dark:hover:bg-white/5 transition-colors"
              >
                {isDark ? (
                  <>
                    <Sun className="h-4 w-4 text-amber-400" />
                    <span>Light Mode</span>
                  </>
                ) : (
                  <>
                    <Moon className="h-4 w-4 text-gray-500" />
                    <span>Dark Mode</span>
                  </>
                )}
              </button>

              <Link 
                to="/dashboard" 
                onClick={() => setIsMobileMenuOpen(false)}
                className="mx-4 mt-2 btn-primary text-sm justify-center"
              >
                <MessageSquare className="h-4 w-4 mr-2" />
                AI Assistant
              </Link>
            </div>
          </div>
        )}
      </div>
    </nav>
  );
}
