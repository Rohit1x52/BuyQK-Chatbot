"use client";

import Link from "next/link";

export default function SiteHeader() {
  return (
    <header className="navbar">
      <div className="navbar-inner">
        <Link href="/" className="nav-brand">
          BuyQK
        </Link>

        <nav
          className="nav-links"
          aria-label="Primary navigation"
        >
          <Link href="/orders" className="nav-link">
            Orders
          </Link>

          <Link href="/cart" className="nav-link">
            Cart
          </Link>

          <Link href="/chat" className="nav-link">
            AI Assistant
          </Link>
        </nav>
      </div>
    </header>
  );
}
