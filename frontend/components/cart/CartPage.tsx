"use client";

import { useEffect } from "react";

import Cart from "./Cart";
import SiteHeader from "../SiteHeader";
import { useChatStore } from "../../store/chatStore";

export default function CartPage() {
  const userId = useChatStore((state) => state.userId);
  const refreshCart = useChatStore((state) => state.refreshCart);
  const error = useChatStore((state) => state.error);

  useEffect(() => {
    if (userId !== null) {
      void refreshCart();
    }
  }, [userId, refreshCart]);

  return (
    <main>
      <SiteHeader />

      <div
        style={{
          maxWidth: "960px",
          margin: "0 auto",
          padding: "32px 20px 48px",
        }}
      >
        <h1
          style={{
            margin: "0 0 20px",
            fontSize: "2rem",
            fontWeight: 700,
          }}
        >
          Your Cart
        </h1>

        {error && (
          <div
            role="alert"
            style={{
              marginBottom: "16px",
              padding: "12px 16px",
              borderRadius: "8px",
              background: "#fff1f2",
              color: "#be123c",
              border: "1px solid #fecdd3",
            }}
          >
            {error}
          </div>
        )}

        <Cart />
      </div>
    </main>
  );
}
