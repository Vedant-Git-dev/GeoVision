import React, { useState, useEffect, useRef, Suspense } from 'react';
import { motion, useScroll } from 'framer-motion';
import { ArrowUpRight, Sparkle, Copyright } from '@phosphor-icons/react';
import GlobeOrb from './GlobeOrb';
import Lenis from 'lenis';

// Animation variants
const fadeUp = {
  hidden: { opacity: 0, y: 50 },
  visible: (i = 0) => ({
    opacity: 1, y: 0,
    transition: { duration: 1, delay: i * 0.15, ease: [0.16, 1, 0.3, 1] }
  })
};

const staggerContainer = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.12 } }
};

const scaleIn = {
  hidden: { opacity: 0, scale: 0.92 },
  visible: (i = 0) => ({
    opacity: 1, scale: 1,
    transition: { duration: 0.9, delay: i * 0.1, ease: [0.16, 1, 0.3, 1] }
  })
};

export default function LandingPage({ onStart }) {
  const [isExiting, setIsExiting] = useState(false);
  
  // Refs for high-performance orb updates outside React render cycle
  const scrollProgressRef = useRef(0);
  const orbWrapperRef = useRef(null);

  // Lenis + manual scroll tracking
  useEffect(() => {
    const lenis = new Lenis({
      duration: 1.5,
      easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
      orientation: 'vertical',
      gestureOrientation: 'vertical',
      smoothWheel: true,
      wheelMultiplier: 0.8,
      touchMultiplier: 1.5,
    });

    lenis.on('scroll', ({ progress }) => {
      if (isExiting) return;
      
      // Clamp p to exactly 0 to 1 to prevent overscroll math glitches
      const p = Math.max(0, Math.min(1, progress));
      scrollProgressRef.current = p; // Pass this to the shader

      let x = 0, y = 0, scale = 1, opacity = 1;
      const w = window.innerWidth;
      const offset = w > 768 ? w * 0.25 : w * 0.3; // Push it ~25% of screen width away from center

      // Choreography matching mathematically calculated section centers
      if (p <= 0.27) {
        // 0 to 0.27: Hero to Feature 1 Center
        const t = p / 0.27; // 0 to 1
        x = t * offset; // 0 to offset (Right)
        y = -150 * (1 - t); // -150 to 0
        scale = 1.0 + (t * 0.3); // 1.0 to 1.3
        opacity = 1;
      } else if (p <= 0.48) {
        // 0.27 to 0.48: Feature 1 Center to Feature 2 Center
        const t = (p - 0.27) / 0.21; // 0 to 1
        x = offset - (t * (offset * 2)); // offset to -offset (Left)
        y = 0;
        scale = 1.3 + (t * 0.2); // 1.3 to 1.5
        opacity = 1;
      } else if (p <= 0.67) {
        // 0.48 to 0.67: Feature 2 Center to Statement Center
        const t = (p - 0.48) / 0.19; // 0 to 1
        x = -offset + (t * offset); // -offset to 0 (Center)
        y = 0;
        scale = 1.5 + (t * 1.3); // 1.5 to 2.8
        opacity = 1;
      } else if (p <= 0.80) {
        // 0.67 to 0.80: Hold in Statement
        x = 0;
        y = 0;
        scale = 2.8;
        opacity = 1;
      } else {
        // > 0.80: Hold for Bento Cards (let the gradient cover it naturally)
        x = 0;
        y = 0;
        scale = 2.8;
        opacity = 1;
      }

      // Apply transform directly to DOM node for max performance
      if (orbWrapperRef.current) {
        orbWrapperRef.current.style.transform = `translate3d(${x}px, ${y}px, 0)`; // Removed CSS scale to fix GPU clipping
        orbWrapperRef.current.style.opacity = isExiting ? 0 : opacity;
      }
    });

    function raf(time) {
      lenis.raf(time);
      requestAnimationFrame(raf);
    }
    requestAnimationFrame(raf);
    const cleanup = () => {
      lenis.destroy();
    };

    // Wake up Render backend
    try {
      const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:5000';
      fetch(`${API_URL}/check-ee`).catch(() => {}); // silent catch
    } catch(e) {}

    return cleanup;
  }, []);

  const handleStart = () => {
    setIsExiting(true);
    if (orbWrapperRef.current) {
      orbWrapperRef.current.style.opacity = 0;
    }
    setTimeout(() => onStart(), 1000);
  };

  return (
    <>
      {/* ═══ FIXED ORB CANVAS ═══ */}
      <div
        ref={orbWrapperRef}
        className="fixed pointer-events-none"
        style={{
          zIndex: 2,
          width: '1400px', /* MASSIVE to prevent canvas clipping */
          height: '1400px',
          left: '50%',
          top: '50%',
          marginLeft: '-700px',
          marginTop: '-700px',
          transform: 'translate3d(0px, -150px, 0)', // Initial state matches Hero start
          transition: 'opacity 0.5s ease', // REMOVED transform transition to fix scroll judder/inconsistency
        }}
      >
        <Suspense fallback={<div className="w-full h-full" />}>
          <GlobeOrb scrollProgress={scrollProgressRef} />
        </Suspense>
      </div>

      {/* ═══ Main Scrollable Content ═══ */}
      <motion.div
        className="relative w-full bg-white text-[#111111] overflow-x-hidden selection:bg-black/10 selection:text-black"
        animate={isExiting ? { opacity: 0, y: -40 } : { opacity: 1, y: 0 }}
        transition={{ duration: 1, ease: [0.16, 1, 0.3, 1] }}
        style={{ background: '#ffffff', minHeight: '100vh' }}
      >
        <div className="film-grain" />

        {/* Micro-copy */}
        <div className="fixed left-6 top-1/2 -translate-y-1/2 -rotate-90 text-[9px] text-black/15 tracking-[0.35em] font-medium z-40 hidden md:block uppercase select-none">
          Earth Engine // Processing // 37.7749°N 122.4194°W
        </div>
        <div className="fixed right-6 bottom-8 text-[9px] text-black/15 tracking-[0.2em] font-medium z-40 hidden md:block uppercase select-none">
          Sentinel 2 // Processing Active
        </div>
        <div className="fixed top-8 left-8 z-50 flex flex-col gap-1 text-[10px] uppercase tracking-[0.2em] font-medium text-black/60">
          <span>Satellite Change Detection</span>
          <span>Powered by Google Earth Engine</span>
        </div>

        {/* Top Right Action */}
        <button 
          onClick={handleStart}
          className="fixed top-8 right-8 z-50 px-6 py-2.5 border border-black/20 rounded-full text-[11px] font-semibold tracking-[0.15em] text-black hover:bg-black hover:text-white transition-all duration-500 flex items-center gap-2 uppercase"
        >
          Analyze Now <ArrowUpRight size={14} />
        </button>

        {/* ═══ HERO (Text at bottom) ═══ */}
        <section className="relative h-screen flex flex-col justify-end pb-24 z-10">
          <motion.div
            className="relative w-full px-8 md:px-24 flex flex-col md:flex-row items-end justify-between"
            initial="hidden"
            animate="visible"
            variants={staggerContainer}
          >
            <div className="max-w-4xl">
              <motion.h1
                className="font-serif-italic text-6xl md:text-[5.5rem] lg:text-[7rem] font-medium leading-[1.0] tracking-[-0.03em] text-black mb-6"
                variants={fadeUp}
                custom={0}
              >
                See the earth
                <br />— as it changes.
              </motion.h1>
            </div>
            
            <div className="max-w-sm text-right flex flex-col items-end pb-4">
              <motion.p
                className="text-sm md:text-base font-light text-black/50 mb-8 leading-relaxed"
                variants={fadeUp}
                custom={1}
              >
                Satellite intelligence that detects land cover transformation with 10-meter precision. From urban sprawl to deforestation. From environmental damage to recovery.
              </motion.p>
              <motion.button
                onClick={() => {
                  const el = document.getElementById('section-earth');
                  if (el) el.scrollIntoView({ behavior: 'smooth' });
                }}
                className="inline-flex items-center justify-center w-12 h-12 border border-black/20 rounded-full text-black hover:bg-black hover:text-white transition-all duration-300"
                variants={fadeUp}
                custom={2}
              >
                ↓
              </motion.button>
            </div>
          </motion.div>
        </section>

        {/* ═══ FEATURE 1 ═══ */}
        <section id="section-earth" className="relative min-h-[130vh] flex items-center z-10">
          <motion.div
            className="relative mx-8 md:mx-24 px-10 py-12 max-w-2xl bg-white/60 backdrop-blur-md rounded-[32px] border border-black/5 shadow-2xl shadow-black/5"
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: "-200px" }}
            variants={staggerContainer}
          >
            <motion.div className="text-[11px] text-black/40 tracking-[0.3em] uppercase font-medium mb-6" variants={fadeUp}>
              01 — Detection Engine
            </motion.div>
            <motion.h2
              className="font-serif text-5xl md:text-7xl font-normal leading-[1.05] tracking-[-0.03em] mb-8 text-black"
              variants={fadeUp}
              custom={1}
            >
              Sentinel 2<br />Precision
            </motion.h2>
            <motion.p
              className="text-lg md:text-xl text-black/60 font-light leading-relaxed"
              variants={fadeUp}
              custom={2}
            >
              Harness multispectral satellite data processed through Google Earth Engine to detect environmental shifts at 10-meter resolution. Forest loss, urban sprawl, agricultural change—captured in every pixel.
            </motion.p>
          </motion.div>
        </section>

        {/* ═══ FEATURE 2 ═══ */}
        <section className="relative min-h-[130vh] flex items-center justify-end z-10">
          <motion.div
            className="relative mx-8 md:mx-24 px-10 py-12 max-w-2xl text-right bg-white/60 backdrop-blur-md rounded-[32px] border border-black/5 shadow-2xl shadow-black/5"
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: "-200px" }}
            variants={staggerContainer}
          >
            <motion.div className="text-[11px] text-black/40 tracking-[0.3em] uppercase font-medium mb-6 flex justify-end" variants={fadeUp}>
              02 — Classification
            </motion.div>
            <motion.h2
              className="font-serif text-5xl md:text-7xl font-normal leading-[1.05] tracking-[-0.03em] mb-8 text-black"
              variants={fadeUp}
              custom={1}
            >
              Dynamic World<br />Classification
            </motion.h2>
            <motion.p
              className="text-lg md:text-xl text-black/60 font-light leading-relaxed text-right"
              variants={fadeUp}
              custom={2}
            >
              Classify every pixel into 9 land cover categories using probability-based analysis. Understand not just what changed, but the ecological and societal implications of that transformation.
            </motion.p>
          </motion.div>
        </section>

        {/* ═══ STATEMENT ═══ */}
        <section className="relative min-h-[100vh] flex items-center justify-center z-10">
          <motion.div
            className="relative text-center max-w-4xl mx-auto px-10 py-16 bg-white/60 backdrop-blur-md rounded-[32px] border border-black/5 shadow-2xl shadow-black/5"
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: "-200px" }}
            variants={staggerContainer}
          >
            <motion.h2
              className="font-serif-italic text-5xl md:text-7xl lg:text-8xl font-medium leading-[1.05] tracking-[-0.03em] mb-8 text-black"
              variants={fadeUp}
            >
              Data speaks louder
              <br />— when spoken clearly.
            </motion.h2>
            <motion.p
              className="text-base md:text-lg text-black/60 font-light max-w-2xl mx-auto leading-relaxed"
              variants={fadeUp}
              custom={1}
            >
              Raw satellite data is overwhelming. GeoVision transforms petabytes of imagery into human-readable insights powered by advanced AI, making environmental change accessible to everyone.
            </motion.p>
          </motion.div>
        </section>

        {/* ═══ The Output (Bento Grid) ═══ */}
        <section className="relative z-10 py-32 px-6 md:px-12 max-w-7xl mx-auto">
          <motion.div
            className="grid grid-cols-1 md:grid-cols-3 gap-5"
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: "-100px" }}
            variants={staggerContainer}
          >
              <div className="col-span-1 md:col-span-1">
                <div className="bento-card bg-white/60 backdrop-blur-md border border-black/5 shadow-2xl shadow-black/5 text-black p-10 md:p-12 rounded-[28px] flex flex-col justify-between min-h-[400px]">
                  <div>
                    <Sparkle size={24} className="text-[#cc5500] mb-6" />
                    <h3 className="font-serif text-3xl mb-4 leading-tight">10-Meter<br />Resolution</h3>
                  </div>
                  <p className="text-black/60 font-medium text-sm leading-relaxed max-w-[280px]">
                    Sentinel 2 multispectral data reveals environmental shifts with unprecedented clarity and precision.
                  </p>
                </div>
              </div>

              {/* Card 2: AI Explanations */}
              <div className="col-span-1 md:grid-cols-2">
                <div className="bento-card bg-white/60 backdrop-blur-md border border-black/5 shadow-2xl shadow-black/5 text-black p-10 md:p-12 rounded-[28px] flex flex-col items-center justify-center min-h-[400px]">
                  <h3 className="font-serif text-4xl md:text-5xl text-center mb-6 leading-tight max-w-lg">
                    "AI that explains<br />why it matters."
                  </h3>
                  <p className="text-black/60 text-center font-medium max-w-md">
                    Powered by Groq's LLM API, GeoVision translates environmental data into clear, actionable natural language insights about what's changing and why.
                  </p>
                </div>
              </div>

              {/* Card 3: Instant Reports */}
              <div className="col-span-1 md:col-span-2">
                <div className="bento-card bg-[#f4f4f4]/60 backdrop-blur-md border border-black/5 shadow-2xl shadow-black/5 text-[#111111] p-10 md:p-12 rounded-[28px] flex flex-col justify-end min-h-[380px]">
                  <h3 className="font-serif text-4xl mb-4">Interactive Reports</h3>
                  <p className="text-black/60 font-medium max-w-md">
                    Generate shareable HTML reports with before/after composites, change detection maps, land cover statistics, and AI explanations.
                  </p>
                </div>
              </div>

              {/* Card 4: Global Scale */}
              <div className="col-span-1 md:col-span-1">
                <div className="bento-card overflow-hidden bg-white/60 backdrop-blur-md text-black p-10 md:p-12 rounded-[28px] flex flex-col justify-end min-h-[380px] border border-black/5 shadow-2xl shadow-black/5 relative">
                  <div className="relative z-10">
                    <h3 className="font-serif text-3xl mb-4">Any Place.<br />Any Date.</h3>
                    <p className="text-black/60 font-medium text-sm">
                      30 years of Sentinel 2 data covering the entire globe.
                    </p>
                  </div>
                  <div className="absolute bottom-0 left-0 right-0 h-16 bg-gradient-to-t from-blue-200/30 to-transparent" />
                </div>
              </div>
          </motion.div>
        </section>

        {/* ═══ BOTTOM CTA ═══ */}
        <section className="relative py-40 px-8 md:px-24 z-20">
          <div className="text-center">
            <h2 className="font-serif text-5xl md:text-7xl mb-8 tracking-tight text-black">Understand environmental change.</h2>
            <button 
              onClick={handleStart}
              className="inline-flex items-center gap-3 px-10 py-4 bg-black text-white rounded-full font-bold tracking-[0.15em] text-[11px] uppercase hover:scale-105 hover:bg-gray-900 transition-all duration-500 shadow-xl"
            >
              Start Analysis <ArrowUpRight size={16} />
            </button>
          </div>

          <div className="mt-32 flex flex-col md:flex-row items-center justify-between text-[10px] uppercase tracking-[0.2em] font-medium text-black/40 gap-4">
            <div className="flex items-center gap-2">
              <Copyright size={14} />
              <span>2026 GeoVision</span>
            </div>
            <div>Satellite Intelligence Evolved</div>
          </div>
        </section>

        {/* ═══ Footer ═══ */}
        <footer className="relative z-20 border-t border-black/5 py-10 px-8 md:px-24">
          <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-center gap-6">
            <div className="flex items-center gap-2 text-black/25 text-[10px] font-medium tracking-[0.15em] uppercase">
              <Copyright size={12} /> 2026 GeoVision
            </div>
            <div className="flex gap-10 text-black/40 text-[10px] font-medium tracking-[0.15em] uppercase">
              <a href="#" className="hover:text-black transition-colors duration-300">Privacy</a>
              <a href="#" className="hover:text-black transition-colors duration-300">Terms</a>
              <a href="#" className="hover:text-black transition-colors duration-300">Architecture</a>
              <a href="#" className="hover:text-black transition-colors duration-300">GitHub</a>
            </div>
          </div>
        </footer>
      </motion.div>
    </>
  );
}