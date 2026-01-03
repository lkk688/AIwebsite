'use client';

import React, { createContext, useContext, useState, ReactNode } from 'react';

type ChatContextType = {
  isOpen: boolean;
  message: string;
  setIsOpen: (isOpen: boolean) => void;
  setMessage: (message: string) => void;
  openChatWithContext: (contextMessage: string) => void;
};

const ChatContext = createContext<ChatContextType | undefined>(undefined);

export function ChatProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  const [message, setMessage] = useState('');

  const openChatWithContext = (contextMessage: string) => {
    setMessage(contextMessage);
    setIsOpen(true);
  };

  return (
    <ChatContext.Provider value={{ isOpen, message, setIsOpen, setMessage, openChatWithContext }}>
      {children}
    </ChatContext.Provider>
  );
}

export function useChat() {
  const context = useContext(ChatContext);
  if (context === undefined) {
    throw new Error('useChat must be used within a ChatProvider');
  }
  return context;
}
