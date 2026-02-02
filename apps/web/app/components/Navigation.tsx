"use client";

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState, useEffect, useRef } from 'react';
import { useAuth } from '@/lib/hooks/useAuth';

export default function Navigation() {
  const pathname = usePathname();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [moreMenuOpen, setMoreMenuOpen] = useState(false);
  const moreMenuRef = useRef<HTMLDivElement | null>(null);
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
    { href: '/about', label: 'About' },
    { href: '/mission', label: 'Mission' },
    { href: '/support', label: 'Support' },
  ];

  // Authenticated navigation items (for logged-in users)
  // Primary: Home, Calendar, Analytics, Coach
  // Secondary: everything else
  const primaryNavItems = [
    { href: '/home', label: 'Home', icon: '🏠' },
    { href: '/calendar', label: 'Calendar', icon: '📅' },
    { href: '/analytics', label: 'Analytics', icon: '📊' },
    { href: '/insights', label: 'Insights', icon: '🧠' },
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
  ];
  
  // Legacy - keeping for mobile menu only
  const authNavItems = [
    ...primaryNavItems,
    ...secondaryNavItems,
  ];

  const isMoreActive =
    pathname === '/settings' || secondaryNavItems.some((item) => item.href === pathname);

  // Public routes - always show public nav regardless of auth status
  // These are marketing/info pages that should look the same for all visitors
  // Note: /tools is intentionally NOT here - it adapts navbar based on auth state
  const PUBLIC_ROUTES = [
    '/',           // Landing page
    '/about',      // About page
    '/mission',    // Mission page
    '/privacy',    // Privacy policy
    '/terms',      // Terms of service
    '/support',    // Support page
    '/login',      // Login page
    '/register',   // Registration page
  ];
  
  const isPublicRoute = PUBLIC_ROUTES.some(route => 
    pathname === route || pathname?.startsWith(`${route}/`)
  );
  
  // Only show authenticated nav on non-public routes when logged in
  const showAuthenticatedNav = isAuthenticated && !isPublicRoute;

  // Close menus on route change
  useEffect(() => {
    setMobileMenuOpen(false);
    setMoreMenuOpen(false);
  }, [pathname]);

  // Close "More" menu when clicking outside / pressing Escape
  useEffect(() => {
    if (!moreMenuOpen) return;

    const onPointerDown = (e: MouseEvent | TouchEvent) => {
      const target = e.target as Node | null;
      if (!target) return;
      if (moreMenuRef.current && !moreMenuRef.current.contains(target)) {
        setMoreMenuOpen(false);
      }
    };

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMoreMenuOpen(false);
    };

    document.addEventListener('mousedown', onPointerDown);
    document.addEventListener('touchstart', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      document.removeEventListener('touchstart', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [moreMenuOpen]);

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
    <nav className="sticky top-0 z-50 bg-slate-900/95 backdrop-blur-sm border-b border-slate-800 shadow-lg">
      <div className="max-w-7xl mx-auto px-6">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <div className="flex items-center gap-3">
            <Link href={showAuthenticatedNav ? "/home" : "/"} className="text-xl font-bold text-white hover:text-orange-500 transition-colors">
              StrideIQ
            </Link>
            {showAuthenticatedNav && user && (
              <span className="hidden sm:inline text-sm text-slate-500">
                {user.display_name}
              </span>
            )}
          </div>
          
          {/* Desktop Navigation */}
          <div className="hidden md:flex items-center gap-1">
            {isLoading && !isPublicRoute ? (
              <div className="text-slate-500 text-sm">Loading...</div>
            ) : showAuthenticatedNav ? (
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
                
                {/* More menu (secondary nav + settings) */}
                <div className="relative" ref={moreMenuRef}>
                  <button
                    type="button"
                    onClick={() => setMoreMenuOpen((v) => !v)}
                    className={`inline-flex items-center gap-2 px-3.5 py-2 rounded-lg text-sm font-semibold transition-colors border ${
                      moreMenuOpen || isMoreActive
                        ? 'bg-slate-800 text-white border-slate-600'
                        : 'bg-slate-900/40 text-slate-200 border-slate-800 hover:bg-slate-800/70'
                    }`}
                    aria-haspopup="menu"
                    aria-expanded={moreMenuOpen}
                  >
                    <span>More</span>
                    <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-slate-800/70 border border-slate-700 text-slate-200">
                      {secondaryNavItems.length + 1}
                    </span>
                    <svg
                      className={`h-4 w-4 text-slate-300 transition-transform ${moreMenuOpen ? 'rotate-180' : ''}`}
                      viewBox="0 0 20 20"
                      fill="currentColor"
                      aria-hidden="true"
                    >
                      <path
                        fillRule="evenodd"
                        d="M5.23 7.21a.75.75 0 011.06.02L10 10.94l3.71-3.71a.75.75 0 111.06 1.06l-4.24 4.24a.75.75 0 01-1.06 0L5.21 8.29a.75.75 0 01.02-1.08z"
                        clipRule="evenodd"
                      />
                    </svg>
                  </button>

                  {moreMenuOpen && (
                    <div
                      role="menu"
                      className="absolute right-0 mt-2 w-56 rounded-lg border border-slate-700/60 bg-slate-900/95 backdrop-blur-md shadow-xl overflow-hidden"
                    >
                      <div className="py-2">
                        {secondaryNavItems.map((item) => (
                          <Link
                            key={item.href}
                            href={item.href}
                            onClick={() => setMoreMenuOpen(false)}
                            className={`flex items-center justify-between px-4 py-2 text-sm transition-colors ${
                              pathname === item.href
                                ? 'bg-slate-800 text-white'
                                : 'text-slate-200 hover:bg-slate-800/70'
                            }`}
                            role="menuitem"
                          >
                            <span>{item.label}</span>
                            <span className="text-slate-500">{item.icon}</span>
                          </Link>
                        ))}

                        <div className="my-2 border-t border-slate-800" />

                        <Link
                          href="/settings"
                          onClick={() => setMoreMenuOpen(false)}
                          className={`flex items-center justify-between px-4 py-2 text-sm transition-colors ${
                            pathname === '/settings'
                              ? 'bg-slate-800 text-white'
                              : 'text-slate-200 hover:bg-slate-800/70'
                          }`}
                          role="menuitem"
                        >
                          <span>Settings</span>
                          <span className="text-slate-500">⚙️</span>
                        </Link>
                      </div>
                    </div>
                  )}
                </div>

                {/* Admin link (if applicable) */}
                {(user?.role === 'admin' || user?.role === 'owner') && (
                  <Link
                    href="/admin"
                    className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
                      pathname?.startsWith('/admin')
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
              {showAuthenticatedNav ? (
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
