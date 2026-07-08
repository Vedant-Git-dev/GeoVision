import React, { useState, useEffect, useRef, Suspense } from 'react';
import { motion, useScroll } from 'framer-motion';
import { ArrowUpRight, Sparkles, Copyright } from 'lucide-react';
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
        orbWrapperRef.current.style.transform = `translate3d(${x}px, ${y}px, 0) scale(${scale})`;
        orbWrapperRef.current.style.opacity = isExiting ? 0 : opacity;
      }
    });

    function raf(time) {
      lenis.raf(time);
      requestAnimationFrame(raf);
    }
    requestAnimationFrame(raf);
    return () => lenis.destroy();
  }, [isExiting]);

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
          transform: 'translate3d(0px, -150px, 0) scale(1)', // Initial state matches Hero start
          transition: 'opacity 0.5s ease', // REMOVED transform transition to fix scroll judder/inconsistency
        }}
      >
        <Suspense fallback={null}>
          <GlobeOrb scrollProgress={scrollProgressRef} />
        </Suspense>
      </div>

      {/* ═══ Main Scrollable Content ═══ */}
      <motion.div
        className="relative min-h-screen text-[#ededed] overflow-x-hidden selection:bg-white/20 selection:text-white"
        animate={isExiting ? { opacity: 0, y: -40 } : { opacity: 1, y: 0 }}
        transition={{ duration: 1, ease: [0.16, 1, 0.3, 1] }}
        style={{ background: 'transparent' }}
      >
        <div className="film-grain" />

        {/* Micro-copy */}
        <div className="fixed left-6 top-1/2 -translate-y-1/2 -rotate-90 text-[9px] text-white/15 tracking-[0.35em] font-medium z-40 hidden md:block uppercase select-none">
          Sys.Init // V.2.0 // 37.7749°N 122.4194°W
        </div>
        <div className="fixed right-6 bottom-8 text-[9px] text-white/15 tracking-[0.2em] font-medium z-40 hidden md:block uppercase select-none">
          GeoVision Engine // Active
        </div>

        {/* ═══ Nav ═══ */}
        <motion.nav
          className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-8 py-6 mix-blend-difference"
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.3 }}
        >
          <div className="flex items-center gap-3">
            <div className="w-2 h-2 rounded-full bg-[#ffffff] animate-pulse" />
            <span className="text-white font-bold tracking-[0.25em] text-[11px] uppercase">GEOVISION</span>
          </div>
          <motion.button
            onClick={handleStart}
            className="px-6 py-2.5 border border-white/20 rounded-full text-[11px] font-semibold tracking-[0.15em] text-white hover:bg-white hover:text-black transition-all duration-500 flex items-center gap-2 uppercase"
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
          >
            Initialize <ArrowUpRight size={13} />
          </motion.button>
        </motion.nav>

        {/* ═══ HERO (Text at bottom) ═══ */}
        <section className="relative h-screen flex flex-col justify-end pb-24 z-10">
          <motion.div
            className="relative w-full px-8 md:px-24 flex flex-col md:flex-row items-end justify-between mix-blend-difference"
            initial="hidden"
            animate="visible"
            variants={staggerContainer}
          >
            <div className="max-w-4xl">
              <motion.h1
                className="font-serif-italic text-6xl md:text-[5.5rem] lg:text-[7rem] font-medium leading-[1.0] tracking-[-0.03em] text-white mb-6"
                variants={fadeUp}
                custom={0}
              >
                GeoVision doesn't just reply
                <br />— it resonates.
              </motion.h1>
            </div>
            
            <div className="max-w-sm text-right flex flex-col items-end pb-4">
              <motion.p
                className="text-sm md:text-base font-light text-white/50 mb-8 leading-relaxed"
                variants={fadeUp}
                custom={1}
              >
                Most tools are built to output maps. GeoVision is built to relate.
                Through adaptive spatial recognition, it transforms geography into something profound.
              </motion.p>
              <motion.button
                onClick={() => {
                  const el = document.getElementById('section-earth');
                  if (el) el.scrollIntoView({ behavior: 'smooth' });
                }}
                className="inline-flex items-center justify-center w-12 h-12 border border-white/20 rounded-full text-white hover:bg-white hover:text-black transition-all duration-300"
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
            className="relative px-8 md:px-24 max-w-2xl mix-blend-difference"
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: "-200px" }}
            variants={staggerContainer}
          >
            <motion.div className="text-[11px] text-white/40 tracking-[0.3em] uppercase font-medium mb-6" variants={fadeUp}>
              01 — Core Engine
            </motion.div>
            <motion.h2
              className="font-serif text-5xl md:text-7xl font-normal leading-[1.05] tracking-[-0.03em] mb-8 text-white"
              variants={fadeUp}
              custom={1}
            >
              Earth-Aware<br />Engine
            </motion.h2>
            <motion.p
              className="text-lg md:text-xl text-white/60 font-light leading-relaxed"
              variants={fadeUp}
              custom={2}
            >
              GeoVision hears more than words. It reads terrain, tempo, and
              geography — offering contextually aligned responses that feel
              naturally intelligent.
            </motion.p>
          </motion.div>
        </section>

        {/* ═══ FEATURE 2 ═══ */}
        <section className="relative min-h-[130vh] flex items-center justify-end z-10">
          <motion.div
            className="relative px-8 md:px-24 max-w-2xl text-right mix-blend-difference"
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: "-200px" }}
            variants={staggerContainer}
          >
            <motion.div className="text-[11px] text-white/40 tracking-[0.3em] uppercase font-medium mb-6" variants={fadeUp}>
              02 — Personality
            </motion.div>
            <motion.h2
              className="font-serif text-5xl md:text-7xl font-normal leading-[1.05] tracking-[-0.03em] mb-8 text-white"
              variants={fadeUp}
              custom={1}
            >
              Spatial<br />Personality
            </motion.h2>
            <motion.p
              className="text-lg md:text-xl text-white/60 font-light leading-relaxed"
              variants={fadeUp}
              custom={2}
            >
              You define who GeoVision is — analytical and precise, bold and expansive,
              or somewhere in between. Style, voice, and depth are fluid.
            </motion.p>
          </motion.div>
        </section>

        {/* ═══ STATEMENT ═══ */}
        <section className="relative min-h-[100vh] flex items-center justify-center z-10">
          <motion.div
            className="relative text-center max-w-4xl mx-auto px-6 mix-blend-difference"
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: "-200px" }}
            variants={staggerContainer}
          >
            <motion.h2
              className="font-serif-italic text-5xl md:text-7xl lg:text-8xl font-medium leading-[1.05] tracking-[-0.03em] mb-8 text-white"
              variants={fadeUp}
            >
              We gave GeoVision a shape
              <br />to make its presence felt.
            </motion.h2>
            <motion.p
              className="text-base md:text-lg text-white/60 font-light max-w-2xl mx-auto leading-relaxed"
              variants={fadeUp}
              custom={1}
            >
              Intelligence should be more than invisible lines of code. With GeoVision,
              the experience feels physical. Its organic design mirrors its core:
              adaptable, intuitive, and always evolving.
            </motion.p>
          </motion.div>
        </section>

        {/* ═══ BENTO CARDS ═══ */}
        <section className="relative py-40 px-8 md:px-24 z-20" style={{ background: '#030303' }}>
          <div className="absolute top-0 left-0 right-0 h-60 bg-gradient-to-b from-transparent to-[#030303] pointer-events-none -mt-60" />

          <motion.div
            className="max-w-6xl mx-auto relative z-10"
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: "-100px" }}
            variants={staggerContainer}
          >
            {/* Top Row */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mb-5">
              <motion.div
                className="bento-card bg-gradient-to-br from-[#8a4a1c] via-[#5a2d0e] to-[#1a0a00] text-white p-10 md:p-12 rounded-[28px] flex flex-col justify-between min-h-[400px]"
                variants={scaleIn}
                custom={0}
              >
                <div className="self-end">
                  <Sparkles size={36} strokeWidth={1} className="text-white/70" />
                </div>
                <div>
                  <h3 className="font-serif-italic text-3xl md:text-4xl font-normal leading-tight mb-3">
                    Spatial Analysis
                  </h3>
                  <p className="text-base text-white/50 font-light">
                    for researchers that<br />care how they map
                  </p>
                </div>
              </motion.div>

              <motion.div className="flex items-center justify-center p-8 min-h-[400px]" variants={fadeUp} custom={1}>
                <h3 className="font-serif text-3xl md:text-[2.2rem] font-normal leading-snug text-center text-white/80">
                  Environmental Bots that
                  <br />understand climate nuance
                </h3>
              </motion.div>

              <motion.div
                className="bento-card bg-[#0c0c0c] text-white p-10 md:p-12 rounded-[28px] flex flex-col items-center justify-center min-h-[400px] border border-white/[0.06]"
                variants={scaleIn}
                custom={2}
              >
                <div className="border border-white/15 rounded-[80px] px-8 py-5">
                  <h3 className="font-serif-italic text-2xl md:text-[1.7rem] font-normal leading-tight text-center">
                    AI Agents that flex
                    <br />to each user's pace
                  </h3>
                </div>
              </motion.div>
            </div>

            {/* Bottom Row */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
              <motion.div
                className="bento-card bg-[#e6e2db] text-[#0a0a0a] p-10 md:p-12 rounded-[28px] flex flex-col justify-end min-h-[380px]"
                variants={scaleIn}
                custom={3}
              >
                <div className="text-4xl mb-6">☺</div>
                <h3 className="font-serif text-3xl font-normal tracking-tight leading-tight">
                  Digital explorers
                </h3>
                <p className="text-lg text-[#0a0a0a]/50 font-light mt-2 leading-tight">
                  that feel more like analysts<br />than dashboards
                </p>
              </motion.div>

              <div className="hidden md:block" />

              <motion.div
                className="bento-card overflow-hidden bg-gradient-to-br from-[#2a1200] to-[#0d0500] text-white p-10 md:p-12 rounded-[28px] flex flex-col justify-end min-h-[380px] border border-white/[0.04] relative"
                variants={scaleIn}
                custom={4}
              >
                <h3 className="font-serif text-3xl md:text-4xl font-normal tracking-tight leading-tight mb-3 relative z-10">
                  Satellite Assistants
                </h3>
                <p className="text-lg font-light text-white/50 relative z-10">
                  that talk like humans,<br />not scripts
                </p>
                <div className="absolute bottom-0 left-0 right-0 h-16 bg-gradient-to-t from-[#cc5500]/60 to-transparent" />
              </motion.div>
            </div>
          </motion.div>
        </section>

        {/* ═══ BOTTOM CTA ═══ */}
        <section className="relative py-40 px-8 md:px-24 z-20 warm-glow-bg" style={{ background: '#030303' }}>
          <motion.div
            className="max-w-5xl mx-auto"
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: "-100px" }}
            variants={staggerContainer}
          >
            <motion.h2
              className="font-serif-italic text-5xl md:text-7xl font-normal leading-[1.05] tracking-[-0.02em] mb-10 text-white"
              variants={fadeUp}
            >
              GeoVision's intelligence lives in an artificial world but
              its voice comes to life here — in the chat.
            </motion.h2>
            <motion.p
              className="text-sm md:text-base text-white/40 font-light mb-14 max-w-xl leading-relaxed"
              variants={fadeUp}
              custom={1}
            >
              The interface is intentionally quiet. No distraction. No clutter.
              Just conversation that breathes. It's not about looking smart —
              it's about feeling present.
            </motion.p>
            <motion.button
              onClick={handleStart}
              className="inline-flex items-center gap-3 px-10 py-4 bg-white text-black rounded-full font-bold tracking-[0.15em] text-[11px] uppercase hover:scale-105 transition-all duration-500"
              variants={fadeUp}
              custom={2}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
            >
              Launch System <ArrowUpRight size={14} />
            </motion.button>
          </motion.div>
        </section>

        {/* ═══ Footer ═══ */}
        <footer className="relative z-20 border-t border-white/[0.06] py-10 px-8 md:px-24" style={{ background: '#030303' }}>
          <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-center gap-6">
            <div className="flex items-center gap-2 text-white/25 text-[10px] font-medium tracking-[0.15em] uppercase">
              <Copyright size={12} /> 2026 GeoVision Engine
            </div>
            <div className="flex gap-10 text-white/25 text-[10px] font-medium tracking-[0.15em] uppercase">
              <a href="#" className="hover:text-white/60 transition-colors duration-300">Privacy</a>
              <a href="#" className="hover:text-white/60 transition-colors duration-300">Terms</a>
              <a href="#" className="hover:text-white/60 transition-colors duration-300">Architecture</a>
              <a href="#" className="hover:text-white/60 transition-colors duration-300">GitHub</a>
            </div>
          </div>
        </footer>
      </motion.div>
    </>
  );
}