'use client';

import { useState, useEffect, useRef } from 'react';
import { useChat } from '@/contexts/ChatContext';
import { useLanguage } from '@/contexts/LanguageContext';
import { Bot, MessageCircle, Minus, Send, Sparkles, User, X } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import { config } from '@/config';

// Add custom styles for markdown content if Tailwind typography isn't working perfectly
const markdownStyles = `
.markdown-content ul { list-style-type: disc; padding-left: 1.5em; margin-bottom: 0.5em; }
.markdown-content ol { list-style-type: decimal; padding-left: 1.5em; margin-bottom: 0.5em; }
.markdown-content p { margin-bottom: 0.5em; }
.markdown-content strong { font-weight: 600; }
.markdown-content a { color: #2563eb; text-decoration: underline; }
`;

export default function ChatWidget() {
  const { isOpen, setIsOpen, message, setMessage } = useChat();
  const { t } = useLanguage();
  const [chatHistory, setChatHistory] = useState<{ role: 'user' | 'bot'; text: string }[]>([
    // @ts-ignore
    { role: 'bot', text: t.chat?.greeting || 'Hello! How can I help you today?' }
  ]);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Contact Info State
  const [contactInfo, setContactInfo] = useState({ email: '', phone: '' });
  const [showContactForm, setShowContactForm] = useState(false);

  useEffect(() => {
    // Reset chat history when language changes (optional, but good for consistency)
    setChatHistory(prev => {
      // Only update the first message if it's the initial greeting
      if (prev.length === 1 && prev[0].role === 'bot') {
         // @ts-ignore
         return [{ role: 'bot', text: t.chat?.greeting || 'Hello! How can I help you today?' }];
      }
      return prev;
    });
  }, [t]);

  useEffect(() => {
    if (message && isOpen) {
       // Pre-fill logic if needed
    }
  }, [isOpen, message]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [chatHistory, isOpen, showContactForm, isLoading]);

  const sendMessageToBackend = async (msg: string, history: typeof chatHistory) => {
    setIsLoading(true);
    try {
      // Add a placeholder message for the bot's response
      setChatHistory(prev => [...prev, { role: 'bot', text: '' }]);
      
      const response = await fetch(`${config.apiBaseUrl}${config.endpoints.chatStream}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          messages: [...history, { role: 'user', text: msg }],
          // @ts-ignore
          locale: t.nav?.home === '首页' ? 'zh' : 'en',
          allow_actions: true, // Enable actions for stream endpoint if supported or needed
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to fetch response');
      }

      if (!response.body) return;

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let done = false;
      let fullResponse = '';

      while (!done) {
        const { value, done: doneReading } = await reader.read();
        done = doneReading;
        const chunkValue = decoder.decode(value, { stream: true });
        
        // Parse SSE format: "data: {...}"
        const lines = chunkValue.split('\n');
        for (const line of lines) {
            if (line.startsWith('data: ')) {
                const dataStr = line.replace('data: ', '').trim();
                if (dataStr === '[DONE]') break;
                
                try {
                    const data = JSON.parse(dataStr);
                    if (data.type === 'delta' && data.text) {
                        fullResponse += data.text;
                        setChatHistory(prev => {
                            const newHistory = [...prev];
                            const lastMsg = newHistory[newHistory.length - 1];
                            if (lastMsg.role === 'bot') {
                                lastMsg.text = fullResponse;
                            }
                            return newHistory;
                        });
                    } else if (data.type === 'final' && data.text) {
                        // "final" event contains the final confirmation text from tool execution
                        // We should append this to the chat history or replace the last message
                        // Since 'delta' might have streamed partial text, but 'final' from tool execution often comes AFTER all deltas
                        // or REPLACES them (e.g. "Sent to our team...").
                        
                        // If it's a tool execution result, we usually want to show it.
                        // Let's append it to fullResponse if it's new, or replace if fullResponse was empty.
                        if (data.text !== fullResponse) {
                             fullResponse = data.text; // Replace or Append? Usually replace for tool outputs
                             setChatHistory(prev => {
                                const newHistory = [...prev];
                                const lastMsg = newHistory[newHistory.length - 1];
                                if (lastMsg.role === 'bot') {
                                    lastMsg.text = fullResponse;
                                }
                                return newHistory;
                            });
                        }
                    } else if (data.type === 'tool_call') {
                        // For tool_call in SSE, we might receive it but the actual result comes later or in a 'done' event?
                        // If your backend streaming logic sends "done" with final tool execution result, handle it there.
                        console.log("Tool call detected:", data.name);
                    } else if (data.type === 'action') {
                        // Handle final action result from backend (if you add this to your backend streaming response)
                        // Currently backend 'chat_stream' might NOT be returning 'action' events properly yet.
                        // You need to update backend/app/app.py to yield action events.
                        console.log("Action received:", data.action, data.data);
                    } else if (data.type === 'error') {
                         const errorMsg = data.message || "Unknown error occurred";
                         console.error("Backend SSE Error:", errorMsg);
                         fullResponse = `(Error: ${errorMsg})`;
                         setChatHistory(prev => {
                            const newHistory = [...prev];
                            const lastMsg = newHistory[newHistory.length - 1];
                            if (lastMsg.role === 'bot') {
                                lastMsg.text = fullResponse;
                            }
                            return newHistory;
                        });
                    }
                } catch (e) {
                    console.error("Error parsing SSE data:", e);
                }
            }
        }
      }
      
      // Handle actions if backend sends them in a specific format at the end of stream
      // This part depends on how your streaming API returns actions (e.g., as a special event or appended JSON)
      // If action parsing is complex with streaming, you might need a more robust parser.

    } catch (error) {
      console.error('Chat Error:', error);
      // Remove the empty bot message if it exists
      setChatHistory(prev => prev.filter(msg => msg.text !== ''));
      setChatHistory(prev => [...prev, { 
        role: 'bot', 
        text: `Sorry, I am having trouble connecting to the server. Error: ${error instanceof Error ? error.message : String(error)}` 
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSendMessage = (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!message.trim() || isLoading) return;

    const userMsg = message;
    // Add user message immediately
    setChatHistory(prev => [...prev, { role: 'user', text: userMsg }]);
    setMessage('');
    
    // Send to backend
    sendMessageToBackend(userMsg, chatHistory);
  };

  const handleContactSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setShowContactForm(false);
    
    const infoMsg = `Contact Info - Email: ${contactInfo.email}, Phone: ${contactInfo.phone}`;
    
    setChatHistory(prev => [...prev, { 
        role: 'user', 
        text: infoMsg
    }]);
    
    // Send to backend
    sendMessageToBackend(infoMsg, chatHistory);
  };

  return (
    <>
      <style>{markdownStyles}</style>
      {/* Trigger Button (only visible when chat is closed) */}
      <AnimatePresence>
        {!isOpen && (
          <motion.button
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0, opacity: 0 }}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => setIsOpen(true)}
            className="fixed bottom-6 right-6 z-50 w-16 h-16 bg-gradient-to-br from-blue-600 via-indigo-600 to-purple-600 text-white rounded-full shadow-[0_4px_20px_rgba(79,70,229,0.4)] flex items-center justify-center transition-all border border-white/20 group"
          >
            <div className="relative">
              <Bot size={28} className="transition-transform group-hover:rotate-12" />
              <Sparkles size={16} className="absolute -top-2 -right-3 text-yellow-300 animate-pulse" />
            </div>
          </motion.button>
        )}
      </AnimatePresence>

      {/* Chat Window */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ y: 20, opacity: 0, scale: 0.95 }}
            animate={{ y: 0, opacity: 1, scale: 1 }}
            exit={{ y: 20, opacity: 0, scale: 0.95 }}
            transition={{ duration: 0.2 }}
            className="fixed bottom-6 right-6 z-50 w-[90vw] md:w-[400px] h-[550px] bg-white rounded-2xl shadow-2xl flex flex-col overflow-hidden border border-gray-100"
          >
            {/* Header */}
            <div className="bg-blue-600 text-white p-4 flex justify-between items-center">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
                {/* @ts-ignore */}
                <h3 className="font-bold">{t.chat?.title || 'JWL Support'}</h3>
              </div>
              <div className="flex gap-2">
                 <button onClick={() => setIsOpen(false)} className="p-1 hover:bg-white/20 rounded transition-colors">
                  <Minus size={20} />
                </button>
              </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50">
              {chatHistory.map((msg, index) => (
                <div
                  key={index}
                  className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[80%] p-3 rounded-2xl text-sm ${
                      msg.role === 'user'
                        ? 'bg-blue-600 text-white rounded-br-none'
                        : 'bg-white text-gray-800 border border-gray-200 rounded-bl-none shadow-sm'
                    }`}
                  >
                    {msg.role === 'user' ? (
                        msg.text
                    ) : (
                        <div className="markdown-content text-sm">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                {msg.text}
                            </ReactMarkdown>
                        </div>
                    )}
                  </div>
                </div>
              ))}
              
              {/* Contact Form Section */}
              {showContactForm && (
                 <motion.div 
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="bg-white p-4 rounded-xl shadow-sm border border-gray-100"
                 >
                    <div className="flex items-center gap-2 mb-3 text-gray-700 font-semibold text-sm">
                        <User size={16} />
                        {/* @ts-ignore */}
                        {t.chat?.form?.title || 'Your Contact Details'}
                    </div>
                    <form onSubmit={handleContactSubmit} className="space-y-3">
                        <input 
                            type="email" 
                            required
                            // @ts-ignore
                            placeholder={t.chat?.form?.emailPlaceholder || 'Email Address'}
                            className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                            value={contactInfo.email}
                            onChange={(e) => setContactInfo({...contactInfo, email: e.target.value})}
                        />
                        <input 
                            type="tel" 
                            required
                            // @ts-ignore
                            placeholder={t.chat?.form?.phonePlaceholder || 'Phone Number'}
                            className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                            value={contactInfo.phone}
                            onChange={(e) => setContactInfo({...contactInfo, phone: e.target.value})}
                        />
                        <button 
                            type="submit" 
                            className="w-full py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors"
                        >
                            {/* @ts-ignore */}
                            {t.chat?.form?.submitButton || 'Submit Info'}
                        </button>
                    </form>
                 </motion.div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <form onSubmit={handleSendMessage} className="p-4 bg-white border-t border-gray-100 flex gap-2">
              <input
                type="text"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                // @ts-ignore
                placeholder={t.chat?.inputPlaceholder || 'Type your message...'}
                className="flex-1 px-4 py-2 bg-gray-100 rounded-full border-none focus:ring-2 focus:ring-blue-500 outline-none text-sm text-gray-900"
                disabled={showContactForm}
              />
              <button
                type="submit"
                disabled={!message.trim() || showContactForm}
                className="p-2 bg-blue-600 text-white rounded-full hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                <Send size={20} />
              </button>
            </form>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
