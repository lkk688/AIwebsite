'use client';
import { useLanguage } from '@/contexts/LanguageContext';
import { Mail, MapPin, Phone, Printer, Smartphone, Globe, MessageCircle, ExternalLink } from 'lucide-react';
import { useState, useEffect, FormEvent } from 'react';

export default function Contact() {
  const { t, locale } = useLanguage();
  const [isClient, setIsClient] = useState(false);
  const [formState, setFormState] = useState({ name: '', email: '', message: '' });
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');

  useEffect(() => {
    setIsClient(true);
  }, []);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setStatus('loading');

    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL || ''}/api/send-email`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formState),
      });

      if (!response.ok) {
        throw new Error('Failed to send email');
      }

      setStatus('success');
      setFormState({ name: '', email: '', message: '' });
      setTimeout(() => setStatus('idle'), 3000);
    } catch (error) {
      console.error('Error sending email:', error);
      setStatus('error');
    }
  };

  return (
    <section id="contact" className="py-24 bg-white">
      <div className="container mx-auto px-4">
        <h2 className="text-4xl font-bold mb-6 text-gray-900 text-center">{t.contact.title}</h2>
        <p className="text-xl text-gray-600 mb-12 text-center">{t.contact.subtitle}</p>

        <div className="flex flex-col lg:flex-row gap-16">
          
          {/* Left Column: Contact Info & Form */}
          <div className="w-full lg:w-1/2 flex flex-col gap-12">
             {/* Contact Details */}
            <div className="space-y-6 bg-gray-50 p-8 rounded-2xl border border-gray-100">
              {/* Address */}
              <div className="flex items-start gap-4">
                <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center text-blue-600 shrink-0">
                  <MapPin size={20} />
                </div>
                <div>
                  {/* @ts-ignore */}
                  <h4 className="text-base font-bold text-gray-900 mb-0.5">{t.contact.info.addressLabel || 'Address'}</h4>
                  <p className="text-gray-600 text-sm">{t.contact.info.address}</p>
                </div>
              </div>
              
              {/* Phone & Fax */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="flex items-start gap-4">
                  <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center text-blue-600 shrink-0">
                    <Phone size={20} />
                  </div>
                  <div>
                    {/* @ts-ignore */}
                    <h4 className="text-base font-bold text-gray-900 mb-0.5">{t.contact.info.phoneLabel || 'Phone'}</h4>
                    {/* @ts-ignore */}
                    <p className="text-gray-600 text-sm">{t.contact.info.phone}</p>
                  </div>
                </div>
                <div className="flex items-start gap-4">
                  <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center text-blue-600 shrink-0">
                    <Printer size={20} />
                  </div>
                  <div>
                    {/* @ts-ignore */}
                    <h4 className="text-base font-bold text-gray-900 mb-0.5">{t.contact.info.faxLabel || 'Fax'}</h4>
                    {/* @ts-ignore */}
                    <p className="text-gray-600 text-sm">{t.contact.info.fax}</p>
                  </div>
                </div>
              </div>

              {/* Mobile & QQ */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="flex items-start gap-4">
                  <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center text-blue-600 shrink-0">
                    <Smartphone size={20} />
                  </div>
                  <div>
                    {/* @ts-ignore */}
                    <h4 className="text-base font-bold text-gray-900 mb-0.5">{t.contact.info.mobileLabel || 'Mobile / WeChat'}</h4>
                    {/* @ts-ignore */}
                    <p className="text-gray-600 text-sm">{t.contact.info.mobile}</p>
                  </div>
                </div>
                <div className="flex items-start gap-4">
                  <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center text-blue-600 shrink-0">
                    <MessageCircle size={20} />
                  </div>
                  <div>
                    {/* @ts-ignore */}
                    <h4 className="text-base font-bold text-gray-900 mb-0.5">{t.contact.info.qqLabel || 'QQ'}</h4>
                    {/* @ts-ignore */}
                    <p className="text-gray-600 text-sm">{t.contact.info.qq}</p>
                  </div>
                </div>
              </div>

              {/* Email & Website */}
              <div className="grid grid-cols-1 gap-6">
                 <div className="flex items-start gap-4">
                  <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center text-blue-600 shrink-0">
                    <Mail size={20} />
                  </div>
                  <div>
                    {/* @ts-ignore */}
                    <h4 className="text-base font-bold text-gray-900 mb-0.5">{t.contact.info.emailLabel || 'Email'}</h4>
                    {/* @ts-ignore */}
                    <p className="text-gray-600 text-sm">{t.contact.info.email}</p>
                  </div>
                </div>
                <div className="flex items-start gap-4">
                  <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center text-blue-600 shrink-0">
                    <Globe size={20} />
                  </div>
                  <div>
                    {/* @ts-ignore */}
                    <h4 className="text-base font-bold text-gray-900 mb-0.5">{t.contact.info.websiteLabel || 'Website'}</h4>
                    {/* @ts-ignore */}
                    <p className="text-gray-600 text-sm">{t.contact.info.website}</p>
                  </div>
                </div>
              </div>

            </div>

            {/* Form */}
            <div className="bg-white">
              <h3 className="text-2xl font-bold mb-6">Send us a Message</h3>
              <form onSubmit={handleSubmit} className="space-y-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">{t.contact.form.name}</label>
                  <input 
                    type="text" 
                    required
                    value={formState.name}
                    onChange={(e) => setFormState({...formState, name: e.target.value})}
                    className="w-full px-4 py-3 rounded-lg border border-gray-300 focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all" 
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">{t.contact.form.email}</label>
                  <input 
                    type="email" 
                    required
                    value={formState.email}
                    onChange={(e) => setFormState({...formState, email: e.target.value})}
                    className="w-full px-4 py-3 rounded-lg border border-gray-300 focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all" 
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">{t.contact.form.message}</label>
                  <textarea 
                    rows={4} 
                    required
                    value={formState.message}
                    onChange={(e) => setFormState({...formState, message: e.target.value})}
                    className="w-full px-4 py-3 rounded-lg border border-gray-300 focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all" 
                  />
                </div>
                <button 
                  type="submit" 
                  disabled={status === 'loading'}
                  className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-4 rounded-lg transition-colors shadow-lg shadow-blue-600/30 disabled:opacity-70 disabled:cursor-not-allowed flex justify-center items-center"
                >
                  {status === 'loading' ? (
                    <span className="w-6 h-6 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  ) : status === 'success' ? (
                    'Message Sent!'
                  ) : status === 'error' ? (
                    'Error Sending Message'
                  ) : (
                    t.contact.form.submit
                  )}
                </button>
              </form>
            </div>
          </div>

          {/* Right Column: Map */}
          <div className="w-full lg:w-1/2 h-[600px] lg:h-auto rounded-3xl overflow-hidden shadow-2xl relative bg-gray-200">
            {isClient && locale === 'en' ? (
              // Google Map for English / International Users
              <iframe
                width="100%"
                height="100%"
                frameBorder="0"
                style={{ border: 0, minHeight: '600px' }}
                // @ts-ignore
                src={t.contact.map.googleMapSrc}
                allowFullScreen
                title="Google Map Location"
              ></iframe>
            ) : (
              // Baidu Map Placeholder/Link for Chinese Users (Simulated/Static for robustness)
              <div className="w-full h-full flex flex-col items-center justify-center bg-gray-100 text-center p-8 relative">
                 {/* Static Background Image (Simulated Map View) */}
                 {/* @ts-ignore */}
                 <div className="absolute inset-0 opacity-30 bg-cover bg-center" style={{ backgroundImage: `url('${t.contact.map.baiduStaticImage}')` }} />
                 
                 <div className="relative z-10 bg-white p-8 rounded-2xl shadow-xl max-w-md">
                   <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center text-red-600 mb-6 mx-auto">
                     <MapPin size={32} />
                   </div>
                   {/* @ts-ignore */}
                   <h3 className="text-2xl font-bold text-gray-900 mb-2">{t.contact.map.baiduAddressTitle}</h3>
                   <p className="text-gray-600 mb-6">
                     {/* @ts-ignore */}
                     {t.contact.map.baiduAddressDesc}
                   </p>
                   <a 
                     // @ts-ignore
                     href={t.contact.map.baiduMapUrl} 
                     target="_blank" 
                     rel="noopener noreferrer"
                     className="inline-flex items-center px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-lg transition-colors"
                   >
                     {/* @ts-ignore */}
                     {t.contact.map.baiduButtonText} <ExternalLink size={18} className="ml-2" />
                   </a>
                 </div>
              </div>
            )}

            <div className="absolute bottom-6 left-6 bg-white/90 backdrop-blur-sm p-4 rounded-xl shadow-lg max-w-xs z-20">
              {/* @ts-ignore */}
              <h4 className="font-bold text-gray-900 mb-1">{t.contact.map.overlayTitle}</h4>
              <p className="text-sm text-gray-600">
                {/* @ts-ignore */}
                {t.contact.map.overlayDesc}
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
