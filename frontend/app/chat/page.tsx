"use client";

import { useEffect } from "react";
import Link from "next/link";
import ChatWindow from "../../components/chat/ChatWindow";
import { useChatStore } from "../../store/chatStore";

const MVP_USER_ID = 1;

export default function ChatPage() {
  const setUserId = useChatStore((state) => state.setUserId);

  useEffect(() => {
    setUserId(MVP_USER_ID);
  }, [setUserId]);

  return (
    <main>
      <nav className="navbar">
        <div className="navbar-inner">
          <Link href="/" className="nav-brand">
            BuyQK
          </Link>
          <div className="nav-links">
            <Link href="/orders" className="nav-link">
              Orders
            </Link>
          </div>
        </div>
      </nav>

      <div className="chat-page">
        <ChatWindow />
      </div>
    </main>
  );
}
