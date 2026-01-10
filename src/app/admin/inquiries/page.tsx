'use client';

import React, { useState, useEffect } from 'react';
import { Database, Search, ArrowLeft, Mail, AlertCircle, CheckCircle, Clock } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import Link from 'next/link';

const API_BASE_URL = 'http://localhost:8000/api';

interface Inquiry {
  id: number;
  created_at_utc: string;
  source: string;
  locale: string;
  name: string;
  email: string;
  message: string;
  status: string;
  error?: string;
}

export default function AdminInquiriesPage() {
  const { token, logout } = useAuth();
  const [inquiries, setInquiries] = useState<Inquiry[]>([]);
  const [filteredInquiries, setFilteredInquiries] = useState<Inquiry[]>([]);
  const [selectedInquiry, setSelectedInquiry] = useState<Inquiry | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (token) {
      fetchInquiries();
    }
  }, [token]);

  useEffect(() => {
    if (searchQuery) {
      const lower = searchQuery.toLowerCase();
      setFilteredInquiries(inquiries.filter(item => 
        item.name.toLowerCase().includes(lower) || 
        item.email.toLowerCase().includes(lower) ||
        item.message.toLowerCase().includes(lower)
      ));
    } else {
      setFilteredInquiries(inquiries);
    }
  }, [searchQuery, inquiries]);

  const fetchInquiries = async () => {
    try {
      setIsLoading(true);
      const res = await fetch(`${API_BASE_URL}/admin/inquiries?limit=100`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      
      if (res.status === 401) {
        logout();
        return;
      }
      
      if (!res.ok) {
        throw new Error('Failed to fetch inquiries');
      }

      const data = await res.json();
      setInquiries(data);
      setFilteredInquiries(data);
      if (data.length > 0) {
        setSelectedInquiry(data[0]);
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString();
  };

  const formatRelativeTime = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    
    // Less than 24 hours
    if (diff < 24 * 60 * 60 * 1000) {
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
    // Less than 7 days
    if (diff < 7 * 24 * 60 * 60 * 1000) {
      return date.toLocaleDateString([], { weekday: 'short' });
    }
    return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
  };

  return (
    <div className="min-h-screen bg-gray-50 pt-32 pb-12">
      <div className="container mx-auto px-4 max-w-7xl h-[85vh] flex flex-col">
        {/* Header */}
        <div className="flex justify-between items-center mb-6">
          <div className="flex items-center gap-4">
            <Link href="/admin" className="p-2 hover:bg-gray-200 rounded-lg transition-colors flex items-center gap-2 text-gray-600 hover:text-gray-900">
              <ArrowLeft size={24} />
            </Link>
            <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
              <Database className="text-purple-600" size={32} />
              User Inquiries
            </h1>
          </div>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
            <input
              type="text"
              placeholder="Search inquiries..."
              className="pl-10 pr-4 py-2.5 rounded-xl bg-white border border-gray-200 text-gray-900 placeholder-gray-400 focus:ring-2 focus:ring-purple-500 outline-none w-72 shadow-sm"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
        </div>

        {/* Content Card (Split View) */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 flex-1 overflow-hidden flex">
          
          {/* Sidebar List */}
          <div className="w-1/3 border-r border-gray-100 flex flex-col bg-white">
            {isLoading ? (
               <div className="flex-1 flex items-center justify-center text-gray-500">Loading...</div>
            ) : error ? (
               <div className="p-4 text-red-500 text-sm">{error}</div>
            ) : (
              <div className="flex-1 overflow-y-auto">
                {filteredInquiries.map((inquiry) => (
                  <div 
                    key={inquiry.id}
                    onClick={() => setSelectedInquiry(inquiry)}
                    className={`p-4 border-b border-gray-50 cursor-pointer transition-colors hover:bg-gray-50 ${
                      selectedInquiry?.id === inquiry.id ? 'bg-purple-50 border-l-4 border-l-purple-600' : 'border-l-4 border-l-transparent'
                    }`}
                  >
                    <div className="flex justify-between items-baseline mb-1">
                      <span className={`text-sm font-semibold truncate ${selectedInquiry?.id === inquiry.id ? 'text-purple-900' : 'text-gray-900'}`}>
                        {inquiry.name}
                      </span>
                      <span className="text-xs text-gray-400 whitespace-nowrap ml-2">
                        {formatRelativeTime(inquiry.created_at_utc)}
                      </span>
                    </div>
                    <div className="text-sm font-medium text-gray-800 mb-1 truncate">
                       {/* Subject heuristic: first few words or 'Inquiry' */}
                       Inquiry from {inquiry.source}
                    </div>
                    <div className="text-xs text-gray-500 line-clamp-2">
                      {inquiry.message}
                    </div>
                  </div>
                ))}
                {filteredInquiries.length === 0 && (
                  <div className="p-8 text-center text-gray-500 text-sm">No inquiries found</div>
                )}
              </div>
            )}
            <div className="p-3 bg-gray-50 border-t border-gray-100 text-xs text-gray-500 text-center">
              {filteredInquiries.length} messages
            </div>
          </div>

          {/* Main Detail View */}
          <div className="flex-1 flex flex-col bg-white overflow-hidden">
            {selectedInquiry ? (
              <div className="flex-1 flex flex-col overflow-y-auto">
                {/* Message Header */}
                <div className="p-8 border-b border-gray-100">
                  <div className="flex justify-between items-start mb-6">
                    <h2 className="text-2xl font-bold text-gray-900">
                      Inquiry from {selectedInquiry.name}
                    </h2>
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${
                          selectedInquiry.status === 'sent' 
                            ? 'bg-green-50 text-green-700 border-green-100' 
                            : selectedInquiry.status === 'failed' 
                            ? 'bg-red-50 text-red-700 border-red-100' 
                            : 'bg-yellow-50 text-yellow-700 border-yellow-100'
                        }`}>
                      {selectedInquiry.status === 'sent' && <CheckCircle size={12} className="mr-1" />}
                      {selectedInquiry.status}
                    </span>
                  </div>

                  <div className="flex items-center gap-4 mb-6">
                    <div className="w-12 h-12 rounded-full bg-purple-100 flex items-center justify-center text-purple-600 font-bold text-lg">
                      {selectedInquiry.name.charAt(0).toUpperCase()}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-baseline gap-2">
                        <span className="font-semibold text-gray-900">{selectedInquiry.name}</span>
                        <span className="text-sm text-gray-500">&lt;{selectedInquiry.email}&gt;</span>
                      </div>
                      <div className="text-xs text-gray-400 mt-0.5">
                        {formatDate(selectedInquiry.created_at_utc)} via {selectedInquiry.source}
                      </div>
                    </div>
                    
                    <a 
                      href={`mailto:${selectedInquiry.email}`}
                      className="px-4 py-2 bg-white border border-gray-200 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-50 transition-colors flex items-center gap-2"
                    >
                      <Mail size={16} />
                      Reply
                    </a>
                  </div>
                </div>

                {/* Message Body */}
                <div className="p-8 flex-1">
                  <div className="prose max-w-none text-gray-800 whitespace-pre-wrap leading-relaxed">
                    {selectedInquiry.message}
                  </div>
                  
                  {selectedInquiry.error && (
                    <div className="mt-8 p-4 bg-red-50 border border-red-100 rounded-lg text-sm text-red-700 flex items-start gap-2">
                      <AlertCircle size={16} className="mt-0.5 shrink-0" />
                      <div>
                        <span className="font-semibold block mb-1">Delivery Error:</span>
                        {selectedInquiry.error}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center text-gray-400">
                <Mail size={64} className="mb-4 opacity-20" />
                <p>Select an inquiry to view details</p>
              </div>
            )}
          </div>

        </div>
      </div>
    </div>
  );
}
