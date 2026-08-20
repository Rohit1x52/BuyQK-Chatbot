"use client";

import Link from "next/link";

export default function OrdersPage() {
  return (
    <main>
      <nav className="navbar">
        <div className="navbar-inner">
          <Link href="/" className="nav-brand">
            BuyQK
          </Link>
          <div className="nav-links">
            <Link href="/chat" className="nav-link">
              AI Assistant
            </Link>
          </div>
        </div>
      </nav>

      <div className="orders-page">
        <Link href="/" className="back-link">
          ← Back to Home
        </Link>
        
        <header style={{ marginBottom: '32px' }}>
          <h1 className="title-section">Your Orders</h1>
          <p className="subtitle">View your recent BuyQK orders and their status.</p>
        </header>

        <section className="orders-container">
          <div className="empty-state">
            <svg
              width="48"
              height="48"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
            >
              <path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4H6Z" />
              <path d="M3 6h18" />
              <path d="M16 10a4 4 0 0 1-8 0" />
            </svg>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--text-primary)', marginTop: '16px' }}>
              No orders yet
            </h2>
            <p style={{ maxWidth: '400px', marginTop: '8px' }}>
              Your completed and active orders will appear here. Start a conversation with BuyQK AI to find products and place your first order.
            </p>
            <Link href="/chat" className="btn btn-primary" style={{ marginTop: '24px' }}>
              Start Shopping
            </Link>
          </div>
        </section>
      </div>
    </main>
  );
}