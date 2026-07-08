import React, { useState, useRef, useEffect } from 'react';
import { Satellite, LayoutGrid, Globe, CornerDownLeft, Building2, Trees, RadioTower, Waves } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:5000';

export default function ChatUI() {
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isWaiting, setIsWaiting] = useState(false);
  const [mapUrl, setMapUrl] = useState(null);
  const [currentMapConfig, setCurrentMapConfig] = useState(null);
  const iframeRef = useRef(null);
  
  // Progress state
  const [progress, setProgress] = useState({
    active: false,
    step: 'Initializing...',
    detail: 'Starting pipeline',
    percent: 0,
    stepNum: 0,
    totalSteps: 6,
    error: null
  });

  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, progress]);

  const handleSend = async (promptText) => {
    const text = promptText || inputValue;
    if (!text.trim() || isWaiting) return;

    setInputValue('');
    setIsWaiting(true);
    setMapUrl(null);
    setCurrentMapConfig(null);
    setProgress({ active: true, step: 'Initializing', detail: 'Connecting to engine...', percent: 0, stepNum: 0, totalSteps: 6, error: null });

    setMessages(prev => [...prev, { role: 'user', content: text }]);

    const STEP_LABELS = {
      resolve_location: 'Resolving Location',
      fetch_aoi: 'Fetching Area of Interest',
      build_composite_before: 'Building Before Composite',
      build_composite_after: 'Building After Composite',
      detect_changes: 'Detecting Changes',
      compute_stats: 'Computing Statistics',
      Complete: 'Complete'
    };

    try {
      const response = await fetch(`${API_URL}/api/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, history: messages.map(m => ({ role: m.role, content: m.content })) })
      });

      if (!response.ok) throw new Error('Network response was not ok');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let finalResult = null;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop();

        for (const part of parts) {
          let eventType = 'message';
          let eventData = '';

          for (const line of part.split('\n')) {
            if (line.startsWith('event: ')) eventType = line.slice(7);
            else if (line.startsWith('data: ')) eventData = line.slice(6);
          }

          if (!eventData) continue;

          try {
            const payload = JSON.parse(eventData);

            if (eventType === 'progress') {
              const pct = Math.round((payload.step_num / payload.total_steps) * 100);
              const readableStep = STEP_LABELS[payload.step] || payload.step;
              setProgress(prev => ({
                ...prev,
                step: readableStep,
                detail: payload.detail,
                percent: pct,
                stepNum: payload.step_num,
                totalSteps: payload.total_steps
              }));
            } else if (eventType === 'result') {
              finalResult = payload;
              setProgress(prev => ({ ...prev, percent: 100, step: 'Complete' }));
            } else if (eventType === 'error') {
              throw new Error(payload.error || 'Pipeline failed');
            }
          } catch (e) {
            if (e.message !== 'Pipeline failed' && !e.message.includes('Pipeline')) {
              console.warn('Failed to parse event', e);
            } else {
              throw e;
            }
          }
        }
      }

      if (finalResult && finalResult.success) {
        setMessages(prev => [...prev, { 
          role: 'assistant', 
          content: finalResult.explanation || 'Map generated successfully.',
        }]);
        setCurrentMapConfig(finalResult.config);
        setMapUrl(`${API_URL}/maps/default_map.html`);
      } else {
        throw new Error(finalResult?.error || 'Unknown error');
      }

    } catch (error) {
      setProgress(prev => ({ ...prev, error: error.message }));
      setMessages(prev => [...prev, { role: 'assistant', content: `Error: ${error.message}` }]);
    } finally {
      setIsWaiting(false);
      setTimeout(() => setProgress({ active: false, percent: 0 }), 3000);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-screen bg-black text-gray-200">
      {/* Navbar */}
      <nav className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-black/50 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <Satellite className="text-white" size={24} />
          <span className="font-bold text-xl text-white tracking-tight">GeoVision</span>
          <span className="px-2 py-0.5 text-xs font-bold bg-[#1c69d4] text-white rounded-md uppercase tracking-wider">AI</span>
        </div>
      </nav>

      {/* Main Content */}
      <div className="flex flex-1 overflow-hidden">
        
        {/* Left Side: Map / Progress */}
        <div className="flex-1 transition-all duration-500 ease-in-out border-r border-white/10 relative bg-[#030303] flex items-center justify-center">
          {mapUrl ? (
            <iframe 
              ref={iframeRef}
              src={mapUrl}
              onLoad={() => {
                if (iframeRef.current && currentMapConfig) {
                  iframeRef.current.contentWindow.postMessage({
                    type: 'MAP_CONFIG',
                    config: currentMapConfig
                  }, '*');
                }
              }}
              className="w-full h-full border-0"
              title="GeoVision Map"
            />
          ) : progress.active ? (
            <div className="flex flex-col items-center justify-center max-w-md w-full px-8 opacity-100 transition-opacity duration-500">
              <div className="w-full mb-8">
                <div className="flex justify-between items-end mb-4">
                  <span className="font-serif-italic text-3xl text-white">{progress.error ? 'Error' : progress.step}</span>
                  <span className="text-sm font-medium tracking-widest text-[#1c69d4] uppercase mb-1">{progress.percent}%</span>
                </div>
                <div className="h-1 w-full bg-white/10 rounded-full overflow-hidden">
                  <div 
                    className={`h-full transition-all duration-500 ${progress.error ? 'bg-red-500' : 'bg-[#1c69d4]'}`}
                    style={{ width: `${progress.percent}%` }}
                  ></div>
                </div>
                <div className="text-sm text-gray-400 mt-4 font-light tracking-wide">{progress.error || progress.detail}</div>
              </div>
              <div className="flex items-center gap-3 text-xs tracking-[0.2em] uppercase text-white/40">
                <div className="w-1.5 h-1.5 rounded-full bg-[#1c69d4] animate-pulse" />
                Pipeline Active
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center text-white/10 transition-opacity duration-500">
              <Globe size={64} strokeWidth={0.5} className="mb-6 opacity-50" />
              <div className="font-serif text-2xl tracking-tight opacity-50">GeoVision Workspace</div>
              <div className="text-[10px] uppercase tracking-[0.3em] mt-3 opacity-30">Awaiting Input</div>
            </div>
          )}
        </div>

        {/* Right Side: Chat */}
        <div className="flex flex-col w-[450px] bg-[#0a0a0a] relative">
          
          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center opacity-70">
                <Globe size={48} className="text-gray-500 mb-6" strokeWidth={1} />
                <h2 className="text-2xl font-bold text-white mb-2">What would you like to explore?</h2>
                <p className="text-gray-400">Ask about land-use changes anywhere on Earth.</p>
              </div>
            ) : (
              messages.map((msg, i) => (
                <div key={i} className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                  <div className={`max-w-[90%] px-5 py-4 rounded-2xl ${
                    msg.role === 'user' 
                      ? 'bg-[#1c69d4] text-white rounded-br-none' 
                      : 'bg-[#121212] border border-white/10 text-gray-200 rounded-bl-none shadow-lg'
                  }`}>
                    {msg.role === 'user' ? (
                      msg.content
                    ) : (
                      <div className="text-sm font-light leading-relaxed [&>p]:mb-4 last:[&>p]:mb-0 [&>h3]:text-lg [&>h3]:font-serif [&>h3]:mb-2 [&>h3]:text-white [&>ul]:list-disc [&>ul]:pl-5 [&>ul]:mb-4 [&>li]:mb-1 [&>strong]:font-semibold [&>strong]:text-white">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {msg.content}
                        </ReactMarkdown>
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
            
            <div ref={messagesEndRef} />
          </div>

          {/* Input Area */}
          <div className="p-4 bg-[#0a0a0a] border-t border-white/10">
            {messages.length === 0 && (
              <div className="flex gap-2 overflow-x-auto pb-4 scrollbar-hide">
                {["What changed in Mumbai?", "Deforestation in Amazon"].map((prompt, i) => (
                  <button 
                    key={i}
                    onClick={() => handleSend(prompt)}
                    className="flex-shrink-0 px-4 py-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-full text-sm text-gray-300 transition-colors whitespace-nowrap"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            )}
            
            <div className="relative flex items-end bg-white/5 border border-white/20 rounded-xl focus-within:border-[#1c69d4] transition-colors p-1">
              <textarea
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask about land-use changes..."
                className="w-full bg-transparent text-white px-3 py-3 outline-none resize-none max-h-32 text-sm"
                rows={1}
              />
              <button
                onClick={() => handleSend()}
                disabled={!inputValue.trim() || isWaiting}
                className="p-2 mb-1 mr-1 rounded-lg bg-[#1c69d4] text-white disabled:opacity-50 disabled:cursor-not-allowed hover:bg-[#0066b1] transition-colors flex-shrink-0"
              >
                <CornerDownLeft size={18} />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
