import { Link } from 'react-router-dom';
import { AlertCircle, Home, ArrowLeft } from 'lucide-react';

export function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden" style={{ backgroundColor: 'var(--bg-primary)' }}>
      {/* Background Effects */}
      <div className="absolute inset-0 bg-grid opacity-20" />
      <div className="absolute top-1/3 left-1/3 w-96 h-96 bg-blue-500/5 rounded-full blur-[120px]" />

      <div className="text-center relative z-10 animate-scale-in">
        <div className="p-4 rounded-2xl bg-blue-50 dark:bg-blue-500/10 w-fit mx-auto mb-8">
          <AlertCircle className="h-16 w-16 text-blue-600 dark:text-blue-400" />
        </div>
        <h1 className="text-8xl font-bold gradient-text mb-4">404</h1>
        <p className="text-xl text-theme-secondary mb-10">Oops! Page not found</p>
        <div className="flex gap-4 justify-center">
          <Link to="/" className="btn-primary">
            <Home className="h-5 w-5 mr-2" />
            Go Home
          </Link>
          <button onClick={() => window.history.back()} className="btn-secondary">
            <ArrowLeft className="h-5 w-5 mr-2" />
            Go Back
          </button>
        </div>
      </div>
    </div>
  );
}
