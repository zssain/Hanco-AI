import { Link } from 'react-router-dom';
import { ArrowRight, Car, Brain, TrendingUp, Shield, Zap, Globe } from 'lucide-react';

export function Home() {
  return (
    <div className="pt-16" style={{ backgroundColor: 'var(--bg-primary)' }}>
      {/* Hero Section */}
      <section className="relative min-h-[85vh] flex items-center overflow-hidden">
        {/* Subtle Background */}
        <div className="absolute inset-0 bg-grid opacity-40" />
        <div className="absolute top-1/4 left-1/3 w-[500px] h-[500px] rounded-full blur-[160px] opacity-30" style={{ backgroundColor: 'var(--accent-primary)' }} />
        
        <div className="container-custom relative z-10">
          <div className="max-w-3xl mx-auto text-center">
            {/* Badge */}
            <div className="inline-flex items-center px-4 py-1.5 rounded-full border mb-8 animate-fade-in" style={{ borderColor: 'var(--border-color)', backgroundColor: 'var(--bg-secondary)' }}>
              <span className="text-sm text-theme-secondary">AI-Powered Car Rental Platform</span>
            </div>

            {/* Main Heading */}
            <h1 className="text-4xl md:text-6xl font-bold mb-6 leading-tight animate-slide-up text-theme-primary">
              Premium Rentals,
              <br />
              <span className="gradient-text">Intelligent Pricing</span>
            </h1>

            <p className="text-lg text-theme-secondary mb-10 max-w-xl mx-auto leading-relaxed animate-slide-up delay-100">
              Experience the future of car rental in Saudi Arabia with ML-powered dynamic pricing 
              and a premium fleet of vehicles.
            </p>

            {/* CTA Buttons */}
            <div className="flex flex-col sm:flex-row gap-3 justify-center animate-slide-up delay-200">
              <Link to="/vehicles" className="btn-primary text-base px-8 py-3">
                Explore Fleet
                <ArrowRight className="ml-2 h-5 w-5" />
              </Link>
              <Link to="/login" className="btn-secondary text-base px-8 py-3">
                Get Started
              </Link>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-3 gap-8 mt-20 animate-fade-in delay-300">
              <div className="text-center">
                <div className="text-3xl md:text-4xl font-bold text-theme-primary">500+</div>
                <div className="stat-label">Premium Vehicles</div>
              </div>
              <div className="text-center">
                <div className="text-3xl md:text-4xl font-bold text-theme-primary">10K+</div>
                <div className="stat-label">Happy Customers</div>
              </div>
              <div className="text-center">
                <div className="text-3xl md:text-4xl font-bold text-theme-primary">4.9</div>
                <div className="stat-label">Customer Rating</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Search Section */}
      <section className="relative py-16 border-t" style={{ borderColor: 'var(--border-color)' }}>
        <div className="container-custom">
          <div className="card max-w-4xl mx-auto p-8">
            <h2 className="text-2xl font-semibold text-theme-primary mb-6 text-center">Find Your Perfect Vehicle</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
              <div>
                <label className="block text-theme-secondary text-sm font-medium mb-2">City</label>
                <select className="select w-full">
                  <option>Riyadh</option>
                  <option>Jeddah</option>
                  <option>Dammam</option>
                  <option>Makkah</option>
                </select>
              </div>
              <div>
                <label className="block text-theme-secondary text-sm font-medium mb-2">Start Date</label>
                <input type="date" className="input w-full" />
              </div>
              <div>
                <label className="block text-theme-secondary text-sm font-medium mb-2">End Date</label>
                <input type="date" className="input w-full" />
              </div>
            </div>
            <Link 
              to="/vehicles" 
              className="btn-primary w-full text-base py-3 justify-center"
            >
              <Car className="mr-2 h-5 w-5" />
              Search Available Vehicles
            </Link>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="section-darker border-t" style={{ borderColor: 'var(--border-color)' }}>
        <div className="container-custom">
          <div className="text-center mb-14">
            <h2 className="text-3xl font-bold text-theme-primary mb-3">
              Why Choose Us
            </h2>
            <p className="text-theme-secondary max-w-lg mx-auto">
              Leveraging AI technology to deliver an unmatched car rental experience
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[
              { icon: Brain, title: 'Dynamic Pricing', desc: 'ML-powered pricing that analyzes market conditions, demand patterns, and competitor rates in real-time.', color: 'text-blue-600 dark:text-blue-400', bg: 'bg-blue-50 dark:bg-blue-500/10' },
              { icon: Car, title: 'AI Chatbot', desc: 'Natural language booking assistant powered by Gemini AI for seamless, conversational experiences.', color: 'text-emerald-600 dark:text-emerald-400', bg: 'bg-emerald-50 dark:bg-emerald-500/10' },
              { icon: Car, title: 'Premium Fleet', desc: 'From economy to luxury, choose from a wide selection of well-maintained vehicles across Saudi Arabia.', color: 'text-gray-700 dark:text-gray-300', bg: 'bg-gray-100 dark:bg-gray-500/10' },
              { icon: TrendingUp, title: 'Smart Savings', desc: 'Get the best rates automatically with our intelligent pricing engine that optimizes for value.', color: 'text-amber-600 dark:text-amber-400', bg: 'bg-amber-50 dark:bg-amber-500/10' },
              { icon: Shield, title: 'Secure Booking', desc: 'Enterprise-grade security with encrypted transactions and comprehensive insurance options.', color: 'text-indigo-600 dark:text-indigo-400', bg: 'bg-indigo-50 dark:bg-indigo-500/10' },
              { icon: Globe, title: 'Multi-City Coverage', desc: 'Available in Riyadh, Jeddah, Dammam, Makkah, and expanding across the Kingdom.', color: 'text-rose-600 dark:text-rose-400', bg: 'bg-rose-50 dark:bg-rose-500/10' },
            ].map((feature, i) => (
              <div key={i} className="card-hover group">
                <div className={`p-3 rounded-lg ${feature.bg} w-fit mb-5 group-hover:scale-105 transition-transform`}>
                  <feature.icon className={`h-5 w-5 ${feature.color}`} />
                </div>
                <h3 className="text-lg font-semibold text-theme-primary mb-2">{feature.title}</h3>
                <p className="text-theme-secondary text-sm leading-relaxed">{feature.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="section border-t" style={{ borderColor: 'var(--border-color)' }}>
        <div className="container-custom">
          <div className="max-w-2xl mx-auto text-center">
            <h2 className="text-3xl font-bold text-theme-primary mb-4">
              Ready to Get Started?
            </h2>
            <p className="text-theme-secondary text-lg mb-8">
              Join thousands of satisfied customers using our AI-powered platform.
            </p>
            <div className="flex flex-col sm:flex-row gap-3 justify-center">
              <Link to="/register" className="btn-primary text-base px-8 py-3">
                <Zap className="mr-2 h-5 w-5" />
                Create Account
              </Link>
              <Link to="/vehicles" className="btn-outline text-base px-8 py-3">
                Browse Fleet
              </Link>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
