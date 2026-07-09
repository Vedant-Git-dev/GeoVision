import React, { useState } from 'react';
import LandingPage from './components/LandingPage';
import ChatUI from './components/ChatUI';

function App() {
  const [showChat, setShowChat] = useState(false);

  return (
    <>
      {!showChat ? (
        <LandingPage onStart={() => setShowChat(true)} />
      ) : (
        <ChatUI />
      )}
    </>
  );
}

export default App;
