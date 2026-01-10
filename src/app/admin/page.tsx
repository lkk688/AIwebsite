'use client';
import Link from 'next/link';
import { Image as ImageIcon, Settings, LogOut, LayoutDashboard, Database } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';

export default function AdminDashboard() {
  const { logout } = useAuth();

  const menuItems = [
    {
      title: 'Image Manager',
      desc: 'Update website images, heroes, and facilities',
      icon: ImageIcon,
      href: '/admin/images',
      color: 'bg-blue-500',
    },
    {
      title: 'Database',
      desc: 'View user inquiries and system logs',
      icon: Database,
      href: '/admin/inquiries',
      color: 'bg-purple-500',
    },
    {
      title: 'Settings',
      desc: 'Configure website settings and SEO',
      icon: Settings,
      href: '/admin/settings',
      color: 'bg-gray-500',
    },
  ];

  return (
    <div className="min-h-screen bg-gray-50 pt-32 pb-12">
      <div className="container mx-auto px-4 max-w-6xl">
        
        {/* Header */}
        <div className="flex justify-between items-center mb-12">
          <div>
            <h1 className="text-4xl font-bold text-gray-900 flex items-center gap-3">
              <LayoutDashboard className="text-blue-600" size={40} />
              Admin Dashboard
            </h1>
            <p className="text-gray-500 mt-2 text-lg">Welcome back, Admin</p>
          </div>
          <button
            onClick={logout}
            className="flex items-center gap-2 px-6 py-3 bg-white border border-gray-200 text-red-600 rounded-xl font-semibold hover:bg-red-50 transition-all shadow-sm"
          >
            <LogOut size={20} />
            Sign Out
          </button>
        </div>

        {/* Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {menuItems.map((item) => (
            <Link
              key={item.title}
              href={item.href}
              className="group bg-white p-8 rounded-2xl shadow-sm hover:shadow-xl transition-all duration-300 border border-gray-100 flex flex-col relative overflow-hidden"
            >
              <div className={`w-14 h-14 ${item.color} rounded-xl flex items-center justify-center text-white mb-6 shadow-lg group-hover:scale-110 transition-transform duration-300`}>
                <item.icon size={28} />
              </div>
              <h3 className="text-2xl font-bold text-gray-900 mb-3">{item.title}</h3>
              <p className="text-gray-500 leading-relaxed mb-8">{item.desc}</p>
              
              <div className="mt-auto flex items-center text-blue-600 font-semibold group-hover:translate-x-2 transition-transform">
                Access Tool →
              </div>
            </Link>
          ))}
        </div>

        {/* Recent Activity or Stats (Placeholder) */}
        <div className="mt-12 bg-white rounded-2xl shadow-sm border border-gray-100 p-8">
          <h3 className="text-xl font-bold text-gray-900 mb-6">System Status</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="p-4 bg-green-50 rounded-xl border border-green-100">
              <div className="text-sm text-green-600 font-medium mb-1">Backend API</div>
              <div className="text-2xl font-bold text-green-700">Online</div>
            </div>
            <div className="p-4 bg-blue-50 rounded-xl border border-blue-100">
              <div className="text-sm text-blue-600 font-medium mb-1">Last Backup</div>
              <div className="text-2xl font-bold text-blue-700">Today, 09:00</div>
            </div>
            <div className="p-4 bg-amber-50 rounded-xl border border-amber-100">
              <div className="text-sm text-amber-600 font-medium mb-1">Pending Inquiries</div>
              <div className="text-2xl font-bold text-amber-700">0</div>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
