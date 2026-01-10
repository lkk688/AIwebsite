'use client';
import { AuthProvider, useAuth } from '@/contexts/AuthContext';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

function AdminGuard({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, token } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [isChecking, setIsChecking] = useState(true);

  useEffect(() => {
    // Small delay to allow localStorage to load
    const timer = setTimeout(() => {
      if (!isAuthenticated && pathname !== '/admin/login') {
        router.push('/admin/login');
      }
      setIsChecking(false);
    }, 100);
    return () => clearTimeout(timer);
  }, [isAuthenticated, pathname, router]);

  if (isChecking) {
    return <div className="min-h-screen flex items-center justify-center">Loading...</div>;
  }

  return <>{children}</>;
}

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <AdminGuard>
        {children}
      </AdminGuard>
    </AuthProvider>
  );
}
