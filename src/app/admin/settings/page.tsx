'use client';

import React, { useState } from 'react';
import { Settings, Lock, User, Save, ArrowLeft, CheckCircle, AlertCircle } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import Link from 'next/link';

const API_BASE_URL = 'http://localhost:8000/api';

export default function AdminSettingsPage() {
  const { token, logout } = useAuth();
  const [activeTab, setActiveTab] = useState('password');
  
  // Password Form State
  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);

  const handlePasswordUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    setMessage(null);

    if (newPassword !== confirmPassword) {
      setMessage({ type: 'error', text: 'New passwords do not match' });
      return;
    }

    if (newPassword.length < 6) {
      setMessage({ type: 'error', text: 'Password must be at least 6 characters long' });
      return;
    }

    try {
      setIsLoading(true);
      const res = await fetch(`${API_BASE_URL}/auth/update-password`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          old_password: oldPassword,
          new_password: newPassword
        })
      });

      if (res.status === 401) {
        logout();
        return;
      }

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || 'Failed to update password');
      }

      setMessage({ type: 'success', text: 'Password updated successfully' });
      setOldPassword('');
      setNewPassword('');
      setConfirmPassword('');
      
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 pt-32 pb-12">
      <div className="container mx-auto px-4 max-w-4xl h-[85vh] flex flex-col">
        {/* Header */}
        <div className="flex justify-between items-center mb-6">
          <div className="flex items-center gap-4">
            <Link href="/admin" className="p-2 hover:bg-gray-200 rounded-lg transition-colors flex items-center gap-2 text-gray-600 hover:text-gray-900">
              <ArrowLeft size={24} />
            </Link>
            <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
              <Settings className="text-gray-600" size={32} />
              Admin Settings
            </h1>
          </div>
        </div>

        {/* Content Card */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 flex-1 overflow-hidden flex">
          
          {/* Sidebar */}
          <div className="w-1/4 border-r border-gray-100 bg-gray-50/50 p-4">
            <div className="space-y-2">
              <button
                onClick={() => setActiveTab('password')}
                className={`w-full text-left px-4 py-3 rounded-xl flex items-center gap-3 transition-colors ${
                  activeTab === 'password' 
                    ? 'bg-white text-blue-600 shadow-sm font-medium' 
                    : 'text-gray-600 hover:bg-white/50 hover:text-gray-900'
                }`}
              >
                <Lock size={18} />
                Security
              </button>
              {/* Placeholder for future Profile tab */}
              <button
                disabled
                className="w-full text-left px-4 py-3 rounded-xl flex items-center gap-3 text-gray-400 cursor-not-allowed"
              >
                <User size={18} />
                Profile (Coming Soon)
              </button>
            </div>
          </div>

          {/* Main Content */}
          <div className="flex-1 p-8 overflow-y-auto">
            {activeTab === 'password' && (
              <div className="max-w-md mx-auto">
                <h2 className="text-xl font-bold text-gray-900 mb-6 flex items-center gap-2">
                  <Lock size={20} className="text-blue-500" />
                  Change Password
                </h2>

                {message && (
                  <div className={`mb-6 p-4 rounded-xl flex items-start gap-3 ${
                    message.type === 'success' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
                  }`}>
                    {message.type === 'success' ? <CheckCircle size={20} className="mt-0.5" /> : <AlertCircle size={20} className="mt-0.5" />}
                    <div>{message.text}</div>
                  </div>
                )}

                <form onSubmit={handlePasswordUpdate} className="space-y-6">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Current Password
                    </label>
                    <input
                      type="password"
                      required
                      className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-100 outline-none transition-all"
                      value={oldPassword}
                      onChange={(e) => setOldPassword(e.target.value)}
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      New Password
                    </label>
                    <input
                      type="password"
                      required
                      minLength={6}
                      className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-100 outline-none transition-all"
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                    />
                    <p className="mt-1.5 text-xs text-gray-500">Minimum 6 characters</p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Confirm New Password
                    </label>
                    <input
                      type="password"
                      required
                      className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-100 outline-none transition-all"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={isLoading}
                    className={`w-full py-3 rounded-xl font-semibold text-white flex items-center justify-center gap-2 transition-all shadow-md hover:shadow-lg ${
                      isLoading ? 'bg-gray-400 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-700'
                    }`}
                  >
                    {isLoading ? 'Updating...' : (
                      <>
                        <Save size={18} />
                        Update Password
                      </>
                    )}
                  </button>
                </form>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
