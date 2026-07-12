import React, { useEffect } from 'react';
import { motion } from 'framer-motion';

export default function Preloader({ onComplete }) {
  useEffect(() => {
    // Preloader duration: 2 seconds
    const timer = setTimeout(() => {
      onComplete();
    }, 2000);

    return () => clearTimeout(timer);
  }, [onComplete]);

  return (
    <>
      {/* Video Background */}
      <video
        className="fixed inset-0 w-full h-full object-cover z-40"
        autoPlay
        loop
        muted
        playsInline
      >
        <source src="/preloader-bg.mp4" type="video/mp4" />
      </video>

      {/* Black Overlay with Expanding Circle Cutout */}
      <motion.div
        className="fixed inset-0 z-50 bg-black"
        initial={{ opacity: 0 }}
        animate={{
          opacity: [0, 1, 1, 0],
          clipPath: [
            'circle(8% at 50% 50%)',
            'circle(8% at 50% 50%)',
            'circle(150% at 50% 50%)',
            'circle(150% at 50% 50%)',
          ],
        }}
        transition={{
          opacity: { duration: 2, times: [0, 0.15, 0.8, 1] },
          clipPath: { duration: 1.5, times: [0, 0.15, 0.8, 1], ease: 'easeInOut' },
        }}
        pointerEvents="none"
      />
    </>
  );
}

