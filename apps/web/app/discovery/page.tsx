'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function DiscoveryRedirect() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/manual');
  }, [router]);

  return null;
}
