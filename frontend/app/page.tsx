"use client";

import Link from "next/link";
import SiteHeader from "../components/SiteHeader";

export default function HomePage() {
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
            <Link href="/chat" className="btn btn-primary">
              Open AI Assistant
            </Link>
          </div>
        </div>
      </nav>

      <section className="hero">
        <div className="container">
          <span className="hero-tag">AI-Powered Commerce</span>
          <h1 className="title-main">Shop smarter with BuyQK AI</h1>
          <p className="subtitle">
            Search for products, get help with orders, track deliveries, and interact with your shopping assistant using natural language.
          </p>
          <div className="hero-actions">
            <Link href="/chat" className="btn btn-primary">
              Start Shopping
            </Link>
            <Link href="/orders" className="btn btn-outline">
              View Orders
            </Link>
          </div>
        </div>
      </section>

      <section className="features-section">
        <div className="grid-3">
          <FeatureCard
            title="Product Search"
            description="Tell BuyQK what you need and get relevant products from the available catalog."
          />
          <FeatureCard
            title="Order Assistance"
            description="Check order information and get help with order-related requests through conversation."
          />
          <FeatureCard
            title="AI Support"
            description="Ask questions naturally and get responses powered by the BuyQK AI assistant."
          />
        </div>
      </section>

      <section style={{ padding: '80px 24px' }}>
        <div className="container" style={{ textAlign: 'center' }}>
          <h2 className="title-section">How BuyQK works</h2>
          <p className="subtitle" style={{ marginBottom: '40px' }}>
            A natural-language interface connected to the BuyQK backend.
          </p>
          <div className="grid-3" style={{ textAlign: 'left' }}>
            <StepCard
              number="01"
              title="Ask"
              description="Tell the assistant what you want in natural language."
            />
            <StepCard
              number="02"
              title="Understand"
              description="The AI identifies your intent and extracts the relevant information."
            />
            <StepCard
              number="03"
              title="Act"
              description="BuyQK executes the appropriate backend operation and returns the result."
            />
          </div>
        </div>
      </section>

      <section style={{ backgroundColor: '#111', color: '#fff', padding: '80px 24px', textAlign: 'center' }}>
        <div className="container">
          <h2 style={{ fontSize: '2rem', fontWeight: 600, marginBottom: '16px' }}>Ready to start?</h2>
          <p style={{ color: '#a3a3a3', marginBottom: '32px' }}>
            Start a conversation with BuyQK AI and find what you need.
          </p>
          <Link
            href="/chat"
            className="btn"
            style={{ backgroundColor: '#fff', color: '#000' }}
          >
            Open BuyQK AI
          </Link>
        </div>
      </section>

      <footer style={{ borderTop: '1px solid var(--border-color)', padding: '32px 24px' }}>
        <div className="container" style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
          <p>BuyQK AI</p>
          <Link href="/chat" style={{ color: 'inherit' }}>
            AI Assistant
          </Link>
        </div>
      </footer>
    </main>
  );
}

function FeatureCard({ title, description }: { title: string; description: string }) {
  return (
    <article className="card">
      <h3>{title}</h3>
      <p>{description}</p>
    </article>
  );
}

function StepCard({ number, title, description }: { number: string; title: string; description: string }) {
  return (
    <article className="card">
      <span className="card-step-num">{number}</span>
      <h3>{title}</h3>
      <p>{description}</p>
    </article>
  );
}