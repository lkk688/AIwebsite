'use client';
import { useLanguage } from '@/contexts/LanguageContext';
import { PenTool, Factory, ShieldCheck } from 'lucide-react';

export default function Services() {
  const { t } = useLanguage();

  // @ts-ignore
  const serviceKeys = Object.keys(t.services.items || {});
  
  const serviceIcons: Record<string, any> = {
    custom: PenTool,
    oem: Factory,
    quality: ShieldCheck,
  };

  const defaultIcon = PenTool;

  const services = serviceKeys.map(key => {
    // @ts-ignore
    const serviceData = t.services.items[key] || { title: key, desc: '' };
    
    return {
      key,
      icon: serviceIcons[key] || defaultIcon,
      title: serviceData.title,
      desc: serviceData.desc,
    };
  });

  return (
    <section id="services" className="py-24 bg-gray-50">
      <div className="container mx-auto px-4">
        <div className="text-center mb-16">
          <h2 className="text-4xl font-bold mb-4 text-gray-900">{t.services.title}</h2>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto">{t.services.subtitle}</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {services.map((service) => (
            <div key={service.key} className="bg-white p-10 rounded-2xl shadow-sm hover:shadow-xl transition-shadow duration-300 border border-gray-100 flex flex-col items-center text-center group">
              <div className="w-16 h-16 bg-blue-50 rounded-2xl flex items-center justify-center text-blue-600 mb-8 group-hover:bg-blue-600 group-hover:text-white transition-colors duration-300">
                <service.icon size={32} />
              </div>
              <h3 className="text-2xl font-bold mb-4 text-gray-900">{service.title}</h3>
              <p className="text-gray-600 leading-relaxed text-lg">
                {service.desc}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
