import { useEffect, useRef, useState } from 'react';

export const useAudioAnalyzer = (stream, isActive) => {
  const [volume, setVolume] = useState(0);
  const audioContextRef = useRef(null);
  const analyzerRef = useRef(null);
  const dataArrayRef = useRef(null);
  const animationFrameRef = useRef(null);

  useEffect(() => {
    if (!stream || !isActive) {
      setVolume(0);
      return;
    }

    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const analyzer = audioContext.createAnalyser();
    const source = audioContext.createMediaStreamSource(stream);
    
    source.connect(analyzer);
    analyzer.fftSize = 256;
    const bufferLength = analyzer.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    audioContextRef.current = audioContext;
    analyzerRef.current = analyzer;
    dataArrayRef.current = dataArray;

    const updateVolume = () => {
      if (!analyzerRef.current) return;
      analyzerRef.current.getByteFrequencyData(dataArrayRef.current);
      
      let sum = 0;
      for (let i = 0; i < bufferLength; i++) {
        sum += dataArrayRef.current[i];
      }
      const average = sum / bufferLength;
      setVolume(average);
      
      animationFrameRef.current = requestAnimationFrame(updateVolume);
    };

    updateVolume();

    return () => {
      if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
      if (audioContextRef.current) audioContextRef.current.close();
    };
  }, [stream, isActive]);

  return volume;
};
