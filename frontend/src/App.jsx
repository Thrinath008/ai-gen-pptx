import React, { useState } from 'react';
import { Sparkles, Presentation, GraduationCap, ArrowRight, Download, CheckCircle2, Layout, BookOpen } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

function App() {
  const [prompt, setPrompt] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [step, setStep] = useState('idle'); // idle, planning, rendering, complete

  const handleGenerate = () => {
    if (!prompt) return;
    setIsLoading(true);
    setStep('planning');
    
    // Simulate pipeline
    setTimeout(() => setStep('rendering'), 2000);
    setTimeout(() => {
      setIsLoading(false);
      setStep('complete');
    }, 5000);
  };

  return (
    <div className="app-container">
      <div className="mesh-bg" />
      
      <header className="header">
        <div className="logo">Antigravity PPT</div>
        <div className="nav-links" style={{ display: 'flex', gap: '2rem', color: 'var(--text-dim)' }}>
          <span>Templates</span>
          <span>History</span>
          <button style={{ 
            background: 'rgba(255,255,255,0.05)', 
            border: '1px solid var(--glass-border)',
            color: '#fff',
            padding: '8px 20px',
            borderRadius: '12px',
            cursor: 'pointer'
          }}>Sign In</button>
        </div>
      </header>

      <main>
        <section className="hero">
          <motion.h1 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
          >
            Teach Anything <br /> 
            <span style={{ color: 'var(--primary)' }}>Instantly.</span>
          </motion.h1>
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
          >
            The world's most advanced AI presentation engine for teachers. 
            Generate high-contrast, pedagogically sound lessons in seconds.
          </motion.p>
        </section>

        <section className="input-section">
          <motion.div 
            className="input-container"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.2 }}
          >
            <input 
              type="text" 
              placeholder="e.g. A 20-minute lesson on Quantum Physics for 10th Grade..." 
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleGenerate()}
            />
            <button className="generate-btn" onClick={handleGenerate}>
              Generate <Sparkles size={18} />
            </button>
          </motion.div>
        </section>

        <section className="features">
          <FeatureCard 
            icon={<GraduationCap />} 
            title="Pedagogically Wired" 
            desc="Follows the Universal Lesson Sequence: Hook, Objectives, Core Content, Activity, and Quiz."
          />
          <FeatureCard 
            icon={<Layout />} 
            title="Premium Templates" 
            desc="High-contrast designs optimized for classroom projectors and focused learning."
          />
          <FeatureCard 
            icon={<BookOpen />} 
            title="Teacher's Guide" 
            desc="Automatically generates a detailed script and time-breakdown for your lesson."
          />
        </section>
      </main>

      <AnimatePresence>
        {isLoading && (
          <motion.div 
            className="loading-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <div className="spinner"></div>
            <h2 style={{ marginTop: '2rem' }}>
              {step === 'planning' ? 'Designing your lesson...' : 'Rendering high-contrast slides...'}
            </h2>
            <p style={{ color: 'var(--text-dim)', marginTop: '0.5rem' }}>
              Our agents are researching and designing your PPTX.
            </p>
          </motion.div>
        )}

        {step === 'complete' && (
          <motion.div 
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className="feature-card"
            style={{ 
              position: 'fixed', 
              top: '50%', 
              left: '50%', 
              transform: 'translate(-50%, -50%)',
              zIndex: 1001,
              width: '90%',
              maxWidth: '500px',
              textAlign: 'center',
              boxShadow: '0 20px 50px rgba(0,0,0,0.5)'
            }}
          >
            <div className="icon-box" style={{ margin: '0 auto 1.5rem', background: 'rgba(16, 185, 129, 0.2)' }}>
              <CheckCircle2 size={32} />
            </div>
            <h2>Lesson Ready!</h2>
            <p style={{ margin: '1rem 0 2rem' }}>
              "Photosynthesis for Class 7" has been generated with 14 high-contrast slides.
            </p>
            <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center' }}>
              <button className="generate-btn" onClick={() => setStep('idle')}>
                Download PPTX <Download size={18} />
              </button>
              <button className="generate-btn" style={{ background: 'transparent', border: '1px solid var(--glass-border)', color: '#fff' }} onClick={() => setStep('idle')}>
                View Plan
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <footer style={{ marginTop: '8rem', textAlign: 'center', color: 'var(--text-dim)', paddingBottom: '4rem' }}>
        <p>© 2026 Antigravity AI Presentation Pipeline</p>
      </footer>
    </div>
  );
}

function FeatureCard({ icon, title, desc }) {
  return (
    <div className="feature-card">
      <div className="icon-box">{icon}</div>
      <h3>{title}</h3>
      <p>{desc}</p>
      <div style={{ marginTop: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--primary)', cursor: 'pointer', fontWeight: 600 }}>
        Learn more <ArrowRight size={16} />
      </div>
    </div>
  );
}

export default App;
