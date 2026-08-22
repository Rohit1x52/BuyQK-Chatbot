// ============================================================
// BuyQK Chat Input
// ============================================================
//
// Responsibility:
// - Collect the user's natural-language message
// - Submit normal chat messages through the Zustand chat store
//
// This component does NOT:
// - call the backend directly
// - call Cart APIs directly
// - modify Cart state directly
// - perform product/cart/order logic
//
// Flow:
//
// ChatInput
//    ↓
// chatStore.sendMessage()
//    ↓
// POST /chat
//    ↓
// LangGraph
//    ↓
// backend / Cart services
//
// ============================================================

"use client";

import {
  FormEvent,
  useState,
} from "react";

import {
  useChatStore,
} from "../../store/chatStore";


// ============================================================
// Component
// ============================================================

export default function ChatInput() {

  const [
    message,
    setMessage,
  ] = useState("");

  const sendMessage =
    useChatStore(
      (state) => state.sendMessage,
    );

  const isLoading =
    useChatStore(
      (state) => state.isLoading,
    );


  // ==========================================================
  // Submit
  // ==========================================================

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>,
  ) {

    event.preventDefault();

    const trimmedMessage =
      message.trim();

    if (
      !trimmedMessage ||
      isLoading
    ) {
      return;
    }

    // Clear the input immediately so the UI feels responsive.
    // The store owns the actual chat request and error state.
    setMessage("");

    try {

      await sendMessage(
        trimmedMessage,
      );

    } catch {
      // sendMessage is responsible for storing/displaying
      // backend errors in the Zustand store. Do not duplicate
      // error handling or call the API from this component.
    }
  }


  // ==========================================================
  // Keyboard Handling
  // ==========================================================

  function handleKeyDown(
    event: React.KeyboardEvent<HTMLTextAreaElement>,
  ) {

    // Enter submits.
    // Shift + Enter creates a new line.

    if (
      event.key === "Enter" &&
      !event.shiftKey
    ) {

      event.preventDefault();

      const form =
        event.currentTarget.form;

      form?.requestSubmit();
    }
  }


  // ==========================================================
  // Render
  // ==========================================================

  return (
    <form
      onSubmit={handleSubmit}
      className="chat-input-form"
    >

      <textarea
        value={message}
        onChange={(event) =>
          setMessage(
            event.target.value,
          )
        }
        onKeyDown={handleKeyDown}
        placeholder="Type a message..."
        disabled={isLoading}
        rows={1}
        className="chat-input"
        aria-label="Chat message"
      />

      <button
        type="submit"
        disabled={
          isLoading ||
          !message.trim()
        }
        className="btn btn-primary"
        aria-label="Send message"
      >
        {isLoading
          ? "..."
          : "Send"}
      </button>

    </form>
  );
}