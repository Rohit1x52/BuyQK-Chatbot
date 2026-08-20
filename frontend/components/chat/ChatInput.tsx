"use client";

import { FormEvent, useState } from "react";
import { useChatStore } from "../../store/chatStore";

export default function ChatInput() {
  const [message, setMessage] = useState("");
  const { sendMessage, isLoading } = useChatStore();

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedMessage = message.trim();

    if (!trimmedMessage || isLoading) return;

    setMessage("");
    await sendMessage(trimmedMessage);
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      const form = event.currentTarget.form;
      form?.requestSubmit();
    }
  }

  return (
    <form onSubmit={handleSubmit} className="chat-input-form">
      <textarea
        value={message}
        onChange={(event) => setMessage(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Type a message..."
        disabled={isLoading}
        rows={1}
        className="chat-input"
        aria-label="Chat message"
      />
      <button
        type="submit"
        disabled={isLoading || !message.trim()}
        className="btn btn-primary"
      >
        {isLoading ? "..." : "Send"}
      </button>
    </form>
  );
}