import React, { useState } from 'react';
import Preloader from './components/Preloader';
import LandingPage from './components/LandingPage';
import ChatUI from './components/ChatUI';

function App() {
  const [showChat, setShowChat] = useState(false);
  const [preloaderDone, setPreloaderDone] = useState(false);

  return (
    <>
      {!preloaderDone && <Preloader onComplete={() => setPreloaderDone(true)} />}
      {preloaderDone && !showChat && <LandingPage onStart={() => setShowChat(true)} />}
      {showChat && <ChatUI />}
    </>
  );
}

export default App;
