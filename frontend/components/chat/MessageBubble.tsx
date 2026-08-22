// ============================================================
// BuyQK Message Bubble
// ============================================================
//
// Responsibility:
// - Render one conversational message
// - Keep message rendering separate from structured UI
//
// This component does NOT:
// - call APIs
// - modify Zustand state
// - modify Cart state
// - render the Cart itself
// - calculate product/cart/order values
//
// Structured UI such as Cart, address selection, payment selection,
// and bill rendering remains the responsibility of ChatWindow and
// its dedicated components.
//
// ============================================================

"use client";

import type {
  ChatMessage,
} from "../../types/chat";


// ============================================================
// Props
// ============================================================

interface MessageBubbleProps {
  message: ChatMessage;
}


// ============================================================
// Message Bubble
// ============================================================

export default function MessageBubble({
  message,
}: MessageBubbleProps) {

  const isUser =
    message.role === "user";

  const content =
    typeof message.content === "string"
      ? message.content.trim()
      : "";

  // ----------------------------------------------------------
  // Empty structured messages
  // ----------------------------------------------------------
  //
  // Do not render an empty text bubble.
  //
  // Structured UI such as:
  // - Cart
  // - address selection
  // - payment selection
  // - bill
  //
  // is rendered by ChatWindow / dedicated components.
  //
  if (!content) {
    return null;
  }

  return (
    <div
      className={`message-row ${
        isUser
          ? "user"
          : "assistant"
      }`}
    >

      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: isUser
            ? "flex-end"
            : "flex-start",
          maxWidth: "100%",
        }}
      >

        {/* ==================================================
            Message Content
        ================================================== */}

        <div
          className="bubble"
          role="article"
          aria-label={
            isUser
              ? "Your message"
              : "BuyQK AI message"
          }
        >
          {content}
        </div>


        {/* ==================================================
            Timestamp
        ================================================== */}

        {message.created_at && (

          <div
            className="bubble-time"
            aria-label="Message time"
          >
            {formatMessageTime(
              message.created_at,
            )}
          </div>

        )}

      </div>

    </div>
  );
}


// ============================================================
// Format Message Time
// ============================================================

function formatMessageTime(
  timestamp: string,
): string {

  if (
    typeof timestamp !== "string" ||
    !timestamp.trim()
  ) {
    return "";
  }

  const date =
    new Date(timestamp);

  if (
    Number.isNaN(
      date.getTime(),
    )
  ) {
    return "";
  }

  try {

    return date.toLocaleTimeString(
      [],
      {
        hour: "2-digit",
        minute: "2-digit",
      },
    );

  } catch {

    return "";
  }
}