'use client';
import { LanguageProvider } from '@/contexts/LanguageContext';
import { ChatProvider } from '@/contexts/ChatContext';
import Navbar from '@/components/Navbar';
import Footer from '@/components/Footer';
import ChatWidget from '@/components/ChatWidget';

export default function ClientLayout({ children }: { children: React.ReactNode }) {
  return (
    <LanguageProvider>
      <ChatProvider>
        <Navbar />
        <main>
          {children}
        </main>
        <Footer />
        <ChatWidget />
      </ChatProvider>
    </LanguageProvider>
  );
}
