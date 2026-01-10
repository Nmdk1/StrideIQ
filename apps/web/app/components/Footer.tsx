"use client";

import React from 'react';

export default function Footer() {
  const handleHashClick = (e: React.MouseEvent<HTMLAnchorElement>, hash: string) => {
    e.preventDefault();
    const element = document.getElementById(hash);
    if (element) {
      const offset = 80; // Account for sticky nav height
      const elementPosition = element.getBoundingClientRect().top;
      const offsetPosition = elementPosition + window.pageYOffset - offset;
      window.scrollTo({
        top: offsetPosition,
        behavior: 'smooth'
      });
    }
  };

  return (
    <footer className="bg-gray-900 border-t border-gray-800 py-12">
      <div className="max-w-7xl mx-auto px-6">
        <div className="grid md:grid-cols-4 gap-8 mb-8">
          <div>
            <h3 className="text-xl font-bold mb-4">StrideIQ</h3>
            <p className="text-gray-400">
              AI-powered running intelligence. Discover what actually improves your running through data-driven insights.
            </p>
          </div>
          
          <div>
            <h3 className="text-xl font-bold mb-4">Quick Links</h3>
            <ul className="space-y-2 text-gray-400">
              <li><a href="#tools" onClick={(e) => handleHashClick(e, 'tools')} className="hover:text-orange-500 transition-colors">Free Tools</a></li>
              <li><a href="/mission" className="hover:text-orange-500 transition-colors">Mission Statement</a></li>
              <li><a href="#pricing" onClick={(e) => handleHashClick(e, 'pricing')} className="hover:text-orange-500 transition-colors">Pricing</a></li>
            </ul>
          </div>
          
          <div>
            <h3 className="text-xl font-bold mb-4">Legal</h3>
            <ul className="space-y-2 text-gray-400">
              <li><a href="/privacy" className="hover:text-orange-500 transition-colors">Privacy Policy</a></li>
              <li><a href="/terms" className="hover:text-orange-500 transition-colors">Terms of Service</a></li>
            </ul>
          </div>
          
          <div>
            <h3 className="text-xl font-bold mb-4">Contact</h3>
            <p className="text-gray-400">
              Questions? Reach out to learn more about our approach.
            </p>
          </div>
        </div>
        
        <div className="border-t border-gray-800 pt-8 text-center text-gray-500">
          <p>&copy; 2026 StrideIQ. All rights reserved.</p>
        </div>
      </div>
    </footer>
  );
}

