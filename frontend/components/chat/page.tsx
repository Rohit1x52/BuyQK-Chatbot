// frontend/app/chat/page.tsx
//
// BuyQK AI Shopping Assistant.
//
// This page is intentionally thin.
// Chat state and API communication remain inside:
// - chatStore.ts
// - chat.ts
//
// The page is responsible for:
// - Initializing the MVP user
// - Rendering the ChatWindow


"use client";

import {
  useEffect,
} from "react";

import ChatWindow from "../../components/chat/ChatWindow";

import {
  useChatStore,
} from "../../store/chatStore";


// ============================================================
// MVP User
// ============================================================
//
// Authentication is not part of the current MVP.
// We use a temporary user ID so the frontend can communicate
// with the existing backend /chat contract.
//
// Replace this later with the authenticated user's ID.


const MVP_USER_ID = 1;


// ============================================================
// Chat Page
// ============================================================

export default function ChatPage() {

  const setUserId =
    useChatStore(
      (state) => state.setUserId
    );


  // ==========================================================
  // Initialize MVP User
  // ==========================================================

  useEffect(() => {

    setUserId(
      MVP_USER_ID
    );

  }, [setUserId]);


  // ==========================================================
  // Render
  // ==========================================================

  return (
    <main className="min-h-screen bg-gray-50 px-4 py-6">

      <div className="mx-auto h-[calc(100vh-3rem)] max-w-5xl">

        <ChatWindow />

      </div>

    </main>
  );
}