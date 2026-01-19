"use client";

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState, useEffect } from 'react';
import { useAuth } from '@/lib/hooks/useAuth';

export default function Navigation() {
  const pathname = usePathname();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const { isAuthenticated, user, logout, isLoading } = useAuth();

  // Handle hash navigation on page load
  useEffect(() => {
    const handleHashScroll = () => {
      const hash = window.location.hash.replace('#', '');
      if (hash) {
        setTimeout(() => {
          const element = document.getElementById(hash);
          if (element) {
            const offset = 80;
            const elementPosition = element.getBoundingClientRect().top;
            const offsetPosition = elementPosition + window.pageYOffset - offset;
            window.scrollTo({
              top: offsetPosition,
              behavior: 'smooth'
            });
          }
        }, 100);
      }
    };

    handleHashScroll();
    window.addEventListener('hashchange', handleHashScroll);
    return () => window.removeEventListener('hashchange', handleHashScroll);
  }, [pathname]);

  const scrollToSection = (hash: string) => {
    const element = document.getElementById(hash);
    if (element) {
      const offset = 80;
      const elementPosition = element.getBoundingClientRect().top;
      const offsetPosition = elementPosition + window.pageYOffset - offset;
      window.scrollTo({
        top: offsetPosition,
        behavior: 'smooth'
      });
      return true;
    }
    return false;
  };

  const handleHashClick = (e: React.MouseEvent<HTMLAnchorElement>, href: string) => {
    if (href.includes('#')) {
      e.preventDefault();
      const hash = href.split('#')[1];
      
      if (pathname !== '/') {
        window.location.href = `/#${hash}`;
        return;
      }
      
      if (!scrollToSection(hash)) {
        setTimeout(() => {
          if (!scrollToSection(hash)) {
            setTimeout(() => scrollToSection(hash), 200);
          }
        }, 50);
      }
    }
  };

  // Public navigation items (for non-authenticated users)
  const publicNavItems = [
    { href: '/', label: 'Home' },
    { href: '/#tools', label: 'Calculators' },
    { href: '/#pricing', label: 'Pricing' },
    { href: '/mission', label: 'Mission' },
  ];

  // Authenticated navigation items (for logged-in users)
  // Primary: Home, Calendar, Analytics, Coach
  // Secondary: everything else
  const primaryNavItems = [
    { href: '/home', label: 'Home', icon: '🏠' },
    { href: '/calendar', label: 'Calendar', icon: '📅' },
    { href: '/analytics', label: 'Analytics', icon: '📊' },
    { href: '/coach', label: 'Coach', icon: '🤖' },
  ];
  
  const secondaryNavItems = [
    { href: '/activities', label: 'Activities', icon: '🏃' },
    { href: '/training-load', label: 'Load', icon: '📈' },
    { href: '/checkin', label: 'Check-in', icon: '✅' },
    { href: '/nutrition', label: 'Nutrition', icon: '🥗' },
    { href: '/compare', label: 'Compare', icon: '👻' },
    { href: '/personal-bests', label: 'PBs', icon: '🏆' },
    { href: '/tools', label: 'Tools', icon: '🧮' },
    { href: '/diagnostic', label: 'Diagnostic', icon: '📋' },
  ];
  
  // Legacy - keeping for mobile menu only
  const authNavItems = [
    ...primaryNavItems,
    ...secondaryNavItems,
  ];

  const NavLink = ({ href, label, isHash = false, highlight = false }: { 
    href: string; 
    label: string; 
    isHash?: boolean;
    highlight?: boolean;
  }) => {
    const isActive = pathname === href;
    const baseClasses = `px-4 py-2 rounded-lg text-sm font-medium transition-colors`;
    const activeClasses = highlight 
      ? 'bg-green-600/20 text-green-400'
      : 'bg-slate-800 text-white';
    const inactiveClasses = highlight
      ? 'bg-green-600/10 text-green-400 hover:bg-green-600/20'
      : 'text-slate-300 hover:bg-slate-800 hover:text-white';

    if (isHash) {
      return (
        <a
          href={href}
          onClick={(e) => handleHashClick(e, href)}
          className={`${baseClasses} ${isActive ? activeClasses : inactiveClasses}`}
        >
          {label}
        </a>
      );
    }

    return (
      <Link
        href={href}
        className={`${baseClasses} ${isActive ? activeClasses : inactiveClasses}`}
      >
        {label}
      </Link>
    );
  };

  return (
    <nav className="sticky top-0 z-50 bg-[#0a0a0f]/95 backdrop-blur-sm border-b border-slate-800 shadow-lg">
      <div className="max-w-7xl mx-auto px-6">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <div className="flex items-center gap-3">
            <Link href={isAuthenticated ? "/home" : "/"} className="text-xl font-bold text-white hover:text-orange-500 transition-colors">
              StrideIQ
            </Link>
            {isAuthenticated && user && (
              <span className="hidden sm:inline text-sm text-slate-500">
                {user.display_name}
              </span>
            )}
          </div>
          
          {/* Desktop Navigation */}
          <div className="hidden md:flex items-center gap-1">
            {isLoading ? (
              <div className="text-slate-500 text-sm">Loading...</div>
            ) : isAuthenticated ? (
              /* === AUTHENTICATED NAV === */
              <>
                {/* Primary nav items */}
                {primaryNavItems.map((item) => (
                  <NavLink 
                    key={item.href} 
                    href={item.href} 
                    label={item.label}
                  />
                ))}
                
                {/* Divider */}
                <div className="w-px h-4 bg-slate-700 mx-1" />
                
                {/* Secondary nav items - smaller */}
                {secondaryNavItems.map((item) => (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
                      pathname === item.href
                        ? 'bg-slate-800 text-white'
                        : 'text-slate-500 hover:text-slate-300'
                    }`}
                  >
                    {item.label}
                  </Link>
                ))}
                
                {/* Settings */}
                <Link
                  href="/settings"
                  className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
                    pathname === '/settings'
                      ? 'bg-slate-800 text-white'
                      : 'text-slate-500 hover:text-slate-300'
                  }`}
                >
                  Settings
                </Link>

                {/* Admin link (if applicable) */}
                {(user?.role === 'admin' || user?.role === 'owner') && (
                  <Link
                    href="/admin"
                    className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
                      pathname === '/admin'
                        ? 'bg-slate-800 text-white'
                        : 'text-slate-500 hover:text-slate-300'
                    }`}
                  >
                    Admin
                  </Link>
                )}

                {/* Logout */}
                <button
                  onClick={logout}
                  className="px-3 py-1.5 rounded text-xs font-medium text-slate-500 hover:text-slate-300 transition-colors"
                >
                  Logout
                </button>
              </>
            ) : (
              /* === PUBLIC NAV === */
              <>
                {publicNavItems.map((item) => (
                  <NavLink 
                    key={item.href} 
                    href={item.href} 
                    label={item.label}
                    isHash={item.href.includes('#')}
                  />
                ))}
                <Link
                  href="/login"
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    pathname === '/login'
                      ? 'bg-slate-800 text-white'
                      : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                  }`}
                >
                  Login
                </Link>
                <Link
                  href="/register"
                  className="px-4 py-2 rounded-lg text-sm font-semibold bg-orange-600 hover:bg-orange-700 text-white transition-all hover:shadow-lg hover:shadow-orange-600/30"
                >
                  Get Started
                </Link>
              </>
            )}
          </div>

          {/* Mobile Menu Button */}
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="md:hidden text-slate-300 hover:text-white focus:outline-none focus:text-white"
            aria-label="Toggle menu"
          >
            <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              {mobileMenuOpen ? (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              )}
            </svg>
          </button>
        </div>

        {/* Mobile Navigation Menu */}
        {mobileMenuOpen && (
          <div className="md:hidden pb-4 safe-area-bottom">
            <div className="flex flex-col gap-1 mt-4 max-h-[calc(100vh-8rem)] overflow-y-auto">
              {isAuthenticated ? (
                /* === MOBILE AUTHENTICATED NAV === */
                <>
                  {authNavItems.map((item) => (
                      <Link
                        key={item.href}
                        href={item.href}
                        onClick={() => setMobileMenuOpen(false)}
                        className={`px-4 py-3 rounded-lg text-base font-medium transition-colors ${
                          pathname === item.href
                            ? 'bg-slate-800 text-white'
                            : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                        }`}
                      >
                        <span className="mr-2">{item.icon}</span>
                        {item.label}
                      </Link>
                  ))}
                  <Link
                    href="/settings"
                    onClick={() => setMobileMenuOpen(false)}
                    className={`px-4 py-3 rounded-lg text-base font-medium transition-colors ${
                      pathname === '/settings'
                        ? 'bg-slate-800 text-white'
                        : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                    }`}
                  >
                    ⚙️ Settings
                  </Link>
                  <button
                    onClick={() => {
                      logout();
                      setMobileMenuOpen(false);
                    }}
                    className="px-4 py-3 rounded-lg text-base font-medium text-slate-400 hover:bg-slate-800 hover:text-white transition-colors text-left"
                  >
                    🚪 Logout
                  </button>
                </>
              ) : (
                /* === MOBILE PUBLIC NAV === */
                <>
                  {publicNavItems.map((item) => (
                    item.href.includes('#') ? (
                      <a
                        key={item.href}
                        href={item.href}
                        onClick={(e) => {
                          handleHashClick(e, item.href);
                          setMobileMenuOpen(false);
                        }}
                        className="px-4 py-3 rounded-lg text-base font-medium text-slate-300 hover:bg-slate-800 hover:text-white transition-colors"
                      >
                        {item.label}
                      </a>
                    ) : (
                      <Link
                        key={item.href}
                        href={item.href}
                        onClick={() => setMobileMenuOpen(false)}
                        className={`px-4 py-3 rounded-lg text-base font-medium transition-colors ${
                          pathname === item.href
                            ? 'bg-slate-800 text-white'
                            : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                        }`}
                      >
                        {item.label}
                      </Link>
                    )
                  ))}
                  <Link
                    href="/login"
                    onClick={() => setMobileMenuOpen(false)}
                    className="px-4 py-3 rounded-lg text-base font-medium text-slate-300 hover:bg-slate-800 hover:text-white transition-colors"
                  >
                    Login
                  </Link>
                  <Link
                    href="/register"
                    onClick={() => setMobileMenuOpen(false)}
                    className="px-4 py-3 rounded-lg text-base font-semibold bg-orange-600 hover:bg-orange-700 text-white transition-colors text-center"
                  >
                    Get Started
                  </Link>
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </nav>
  );
}
