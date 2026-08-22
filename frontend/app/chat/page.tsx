"use client";

import { useEffect } from "react";
import SiteHeader from "../../components/SiteHeader";
import ChatWindow from "../../components/chat/ChatWindow";
import { useChatStore } from "../../store/chatStore";

const MVP_USER_ID = 1;

export default function ChatPage() {
  const setUserId = useChatStore(
    (state) => state.setUserId,
  );

  useEffect(() => {
    setUserId(MVP_USER_ID);
  }, [setUserId]);

  return (
    <main>
      <SiteHeader />

      <div className="chat-page">
        <ChatWindow />
      </div>
    </main>
  );
}