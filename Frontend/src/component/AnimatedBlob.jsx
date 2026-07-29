import React, { useRef, useMemo, useState, useEffect } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, PerspectiveCamera } from '@react-three/drei';
import * as THREE from 'three';

// --- GLSL SHADER SOURCE ---
const noiseFunctions = `
    vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
    vec4 mod289(vec4 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
    vec4 permute(vec4 x) { return mod289(((x*34.0)+1.0)*x); }
    vec4 taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }
    float snoise(vec3 v) {
        const vec2 C = vec2(1.0/6.0, 1.0/3.0);
        const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);
        vec3 i = floor(v + dot(v, C.yyy));
        vec3 x0 = v - i + dot(i, C.xxx);
        vec3 g = step(x0.yzx, x0.xyz);
        vec3 l = 1.0 - g;
        vec3 i1 = min(g.xyz, l.zxy);
        vec3 i2 = max(g.xyz, l.zxy);
        vec3 x1 = x0 - i1 + C.xxx;
        vec3 x2 = x0 - i2 + C.yyy;
        vec3 x3 = x0 - D.yyy;
        i = mod289(i);
        vec4 p = permute(permute(permute(i.z + vec4(0.0, i1.z, i2.z, 1.0)) + i.y + vec4(0.0, i1.y, i2.y, 1.0)) + i.x + vec4(0.0, i1.x, i2.x, 1.0));
        float n_ = 0.142857142857;
        vec3 ns = n_ * D.wyz - D.xzx;
        vec4 j = p - 49.0 * floor(p * ns.z * ns.z);
        vec4 x_ = floor(j * ns.z);
        vec4 y_ = floor(j - 7.0 * x_);
        vec4 x = x_ * ns.x + ns.yyyy;
        vec4 y = y_ * ns.x + ns.yyyy;
        vec4 h = 1.0 - abs(x) - abs(y);
        vec4 b0 = vec4(x.xy, y.xy);
        vec4 b1 = vec4(x.zw, y.zw);
        vec4 s0 = floor(b0)*2.0 + 1.0;
        vec4 s1 = floor(b1)*2.0 + 1.0;
        vec4 sh = -step(h, vec4(0.0));
        vec4 a0 = b0.xzyw + s0.xzyw*sh.xxyy;
        vec4 a1 = b1.xzyw + s1.xzyw*sh.zzww;
        vec3 p0 = vec3(a0.xy,h.x); vec3 p1 = vec3(a0.zw,h.y); vec3 p2 = vec3(a1.xy,h.z); vec3 p3 = vec3(a1.zw,h.w);
        vec4 norm = taylorInvSqrt(vec4(dot(p0,p0), dot(p1,p1), dot(p2, p2), dot(p3,p3)));
        p0 *= norm.x; p1 *= norm.y; p2 *= norm.z; p3 *= norm.w;
        vec4 m = max(0.6 - vec4(dot(x0,x0), dot(x1,x1), dot(x2,x2), dot(x3,x3)), 0.0);
        m = m * m;
        return 42.0 * dot(m*m, vec4(dot(p0,x0), dot(p1,x1), dot(p2,x2), dot(p3,x3)));
    }
    float fbm(vec3 p) {
        float total = 0.0; float amp = 0.5; float freq = 1.0;
        for (int i = 0; i < 3; i++) {
            total += snoise(p * freq) * amp;
            amp *= 0.5; freq *= 2.0;
        }
        return total;
    }
`;

const PlasmaOrb = ({ analyzer, colorTheme, sensitivity = 1.2 }) => {
  const meshRef = useRef();
  const materialRef = useRef();
  const dataArray = useMemo(() => (analyzer ? new Uint8Array(analyzer.frequencyBinCount) : null), [analyzer]);

  const uniforms = useMemo(() => ({
    uTime: { value: 0 },
    uAudioIntensity: { value: 0.0 },
    uThreshold: { value: 0.09 },
    uColorDeep: { value: new THREE.Color(0x001433) },
    uColorMid: { value: new THREE.Color(colorTheme || 0x0084ff) },
    uColorBright: { value: new THREE.Color(0xffffff) }
  }), []);

  // Update color dynamically when settings change
  useEffect(() => {
    if (materialRef.current && colorTheme) {
      materialRef.current.uniforms.uColorMid.value.set(colorTheme);
    }
  }, [colorTheme]);

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    if (materialRef.current) {
      materialRef.current.uniforms.uTime.value = t;
    }

    if (analyzer && dataArray && meshRef.current) {
      analyzer.getByteFrequencyData(dataArray);
      let sum = 0;
      for (let i = 0; i < dataArray.length; i++) sum += dataArray[i];
      const avg = sum / dataArray.length / 255;

      // Use sensitivity to control reactivity
      const targetScale = 1.0 + (avg * sensitivity);
      meshRef.current.scale.lerp(new THREE.Vector3(targetScale, targetScale, targetScale), 0.15);

      if (materialRef.current) {
        materialRef.current.uniforms.uAudioIntensity.value = avg;
        materialRef.current.uniforms.uThreshold.value = THREE.MathUtils.lerp(0.1, 0.01, avg);
      }
    }

    if (meshRef.current) {
      meshRef.current.rotation.y += 0.003;
      meshRef.current.rotation.z += 0.001;
    }
  });

  return (
    <mesh ref={meshRef}>
      <sphereGeometry args={[1, 128, 128]} />
      <shaderMaterial
        ref={materialRef}
        transparent
        blending={THREE.AdditiveBlending}
        side={THREE.DoubleSide}
        depthWrite={false}
        uniforms={uniforms}
        vertexShader={`
          varying vec3 vPosition;
          void main() {
            vPosition = position;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
          }
        `}
        fragmentShader={`
          uniform float uTime;
          uniform float uAudioIntensity;
          uniform float uThreshold;
          uniform vec3 uColorDeep;
          uniform vec3 uColorMid;
          uniform vec3 uColorBright;
          varying vec3 vPosition;
          ${noiseFunctions}
          void main() {
            vec3 p = vPosition * (0.2 + uAudioIntensity * 0.1);
            vec3 q = vec3(
              fbm(p + vec3(0.0, uTime * 0.1, 0.0)),
              fbm(p + vec3(5.2, 1.3, 2.8) + uTime * 0.1),
              fbm(p + vec3(2.2, 8.4, 0.5) - uTime * 0.05)
            );
            float density = fbm(p + 2.0 * q);
            float t = (density + 0.4) * 0.8;
            float alpha = smoothstep(uThreshold, 0.7, t);
            vec3 color = mix(uColorDeep, uColorMid, smoothstep(uThreshold, 0.5, t));
            color = mix(color, uColorBright, smoothstep(0.5, 0.8, t));
            gl_FragColor = vec4(color * (1.2 + uAudioIntensity * 2.0), alpha);
          }
        `}
      />
    </mesh>
  );
};

export default function AnimatedBlob({ blobSettings, setBlobSettings }) {
  const [analyzer, setAnalyzer] = useState(null);
  const [windowSize, setWindowSize] = useState({
    width: typeof window !== 'undefined' ? window.innerWidth : 320,
    height: typeof window !== 'undefined' ? window.innerHeight : 600
  });
  const dragRef = useRef({ isDragging: false, startX: 0, startY: 0 });

  // Responsive size based on screen width
  const getBlobSize = () => {
    const width = windowSize.width;
    if (width < 380) return 220;
    if (width < 480) return 260;
    if (width < 640) return 300;
    if (width < 768) return 350;
    if (width < 1024) return 400;
    return 450;
  };

  // Auto-activate microphone on component mount
  useEffect(() => {
    const initAudio = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const context = new (window.AudioContext || window.webkitAudioContext)();
        const source = context.createMediaStreamSource(stream);
        const analyzerNode = context.createAnalyser();
        analyzerNode.fftSize = 256;
        source.connect(analyzerNode);
        setAnalyzer(analyzerNode);
      } catch (err) {
        console.error("Microphone access denied or error:", err);
      }
    };

    initAudio();

    const handleResize = () => {
      setWindowSize({
        width: window.innerWidth,
        height: window.innerHeight
      });
      if (blobSettings && !blobSettings.isDragging && setBlobSettings) {
        setBlobSettings(prev => ({
          ...prev,
          position: { x: window.innerWidth / 2, y: window.innerHeight / 2 }
        }));
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const blobSize = getBlobSize();
  const isDragMode = blobSettings?.isDragging;
  const sensitivity = blobSettings?.sensitivity || 1.2;

  const handlePointerDown = (e) => {
    if (!isDragMode) return;
    dragRef.current.isDragging = true;
    const currentPos = blobSettings?.position || { x: windowSize.width / 2, y: windowSize.height / 2 };
    dragRef.current.startX = e.clientX - currentPos.x;
    dragRef.current.startY = e.clientY - currentPos.y;
    e.target.setPointerCapture(e.pointerId);
  };

  const handlePointerMove = (e) => {
    if (!dragRef.current.isDragging || !isDragMode || !setBlobSettings) return;
    setBlobSettings(prev => ({
      ...prev,
      position: {
        x: e.clientX - dragRef.current.startX,
        y: e.clientY - dragRef.current.startY
      }
    }));
  };

  const handlePointerUp = (e) => {
    dragRef.current.isDragging = false;
    e.target.releasePointerCapture(e.pointerId);
  };

  return (
    <div
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      className={`absolute z-10 transition-all duration-300 rounded-full ${isDragMode
        ? 'border-2 border-emerald-500 border-dashed shadow-[0_0_30px_rgba(16,185,129,0.3)] bg-emerald-500/5 cursor-grab active:cursor-grabbing'
        : 'border border-transparent'
        }`}
      style={{
        width: `${blobSize}px`,
        height: `${blobSize}px`,
        left: blobSettings?.position?.x ?? windowSize.width / 2,
        top: blobSettings?.position?.y ?? windowSize.height / 2,
        transform: 'translate(-50%, -50%)',
        touchAction: 'none'
      }}
    >
      <Canvas dpr={[1, 1.5]} style={{ pointerEvents: isDragMode ? 'none' : 'auto', borderRadius: '50%' }}>
        <PerspectiveCamera makeDefault position={[0, 0, 3.5]} />
        <OrbitControls enableZoom={false} enablePan={false} enableRotate={!isDragMode} />
        <PlasmaOrb analyzer={analyzer} colorTheme={blobSettings?.color} sensitivity={sensitivity} />
      </Canvas>
    </div>
  );
}