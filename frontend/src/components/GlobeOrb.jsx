import React, { useMemo, useRef, useEffect } from 'react';
import { Canvas, useFrame, extend } from '@react-three/fiber';
import { MathUtils, Vector3, Color } from 'three';
import * as THREE from 'three';

extend({ IcosahedronGeometry: THREE.IcosahedronGeometry });

const vertexShader = `
uniform float u_intensity;
uniform float u_time;

varying vec2 vUv;
varying float vDisplacement;

vec4 permute(vec4 x) { return mod(((x*34.0)+1.0)*x, 289.0); }
vec4 taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }
vec3 fade(vec3 t) { return t*t*t*(t*(t*6.0-15.0)+10.0); }

float cnoise(vec3 P) {
    vec3 Pi0 = floor(P); vec3 Pi1 = Pi0 + vec3(1.0);
    Pi0 = mod(Pi0, 289.0); Pi1 = mod(Pi1, 289.0);
    vec3 Pf0 = fract(P); vec3 Pf1 = Pf0 - vec3(1.0);
    vec4 ix = vec4(Pi0.x, Pi1.x, Pi0.x, Pi1.x);
    vec4 iy = vec4(Pi0.yy, Pi1.yy);
    vec4 iz0 = Pi0.zzzz; vec4 iz1 = Pi1.zzzz;

    vec4 ixy = permute(permute(ix) + iy);
    vec4 ixy0 = permute(ixy + iz0); vec4 ixy1 = permute(ixy + iz1);

    vec4 gx0 = ixy0 / 7.0; vec4 gy0 = fract(floor(gx0) / 7.0) - 0.5;
    gx0 = fract(gx0); vec4 gz0 = vec4(0.5) - abs(gx0) - abs(gy0);
    vec4 sz0 = step(gz0, vec4(0.0));
    gx0 -= sz0 * (step(0.0, gx0) - 0.5); gy0 -= sz0 * (step(0.0, gy0) - 0.5);

    vec4 gx1 = ixy1 / 7.0; vec4 gy1 = fract(floor(gx1) / 7.0) - 0.5;
    gx1 = fract(gx1); vec4 gz1 = vec4(0.5) - abs(gx1) - abs(gy1);
    vec4 sz1 = step(gz1, vec4(0.0));
    gx1 -= sz1 * (step(0.0, gx1) - 0.5); gy1 -= sz1 * (step(0.0, gy1) - 0.5);

    vec3 g000 = vec3(gx0.x,gy0.x,gz0.x); vec3 g100 = vec3(gx0.y,gy0.y,gz0.y);
    vec3 g010 = vec3(gx0.z,gy0.z,gz0.z); vec3 g110 = vec3(gx0.w,gy0.w,gz0.w);
    vec3 g001 = vec3(gx1.x,gy1.x,gz1.x); vec3 g101 = vec3(gx1.y,gy1.y,gz1.y);
    vec3 g011 = vec3(gx1.z,gy1.z,gz1.z); vec3 g111 = vec3(gx1.w,gy1.w,gz1.w);

    vec4 norm0 = taylorInvSqrt(vec4(dot(g000, g000), dot(g010, g010), dot(g100, g100), dot(g110, g110)));
    g000 *= norm0.x; g010 *= norm0.y; g100 *= norm0.z; g110 *= norm0.w;
    vec4 norm1 = taylorInvSqrt(vec4(dot(g001, g001), dot(g011, g011), dot(g101, g101), dot(g111, g111)));
    g001 *= norm1.x; g011 *= norm1.y; g101 *= norm1.z; g111 *= norm1.w;

    float n000 = dot(g000, Pf0); float n100 = dot(g100, vec3(Pf1.x, Pf0.yz));
    float n010 = dot(g010, vec3(Pf0.x, Pf1.y, Pf0.z)); float n110 = dot(g110, vec3(Pf1.xy, Pf0.z));
    float n001 = dot(g001, vec3(Pf0.xy, Pf1.z)); float n101 = dot(g101, vec3(Pf1.x, Pf0.y, Pf1.z));
    float n011 = dot(g011, vec3(Pf0.x, Pf1.yz)); float n111 = dot(g111, Pf1);

    vec3 fade_xyz = fade(Pf0);
    vec4 n_z = mix(vec4(n000, n100, n010, n110), vec4(n001, n101, n011, n111), fade_xyz.z);
    vec2 n_yz = mix(n_z.xy, n_z.zw, fade_xyz.y);
    float n_xyz = mix(n_yz.x, n_yz.y, fade_xyz.x); 
    return 2.2 * n_xyz;
}

void main() {
    vUv = uv;
    vDisplacement = cnoise(position + vec3(2.0 * u_time));
    vec3 newPosition = position + normal * (u_intensity * vDisplacement);
    vec4 modelPosition = modelMatrix * vec4(newPosition, 1.0);
    vec4 viewPosition = viewMatrix * modelPosition;
    vec4 projectedPosition = projectionMatrix * viewPosition;
    gl_Position = projectedPosition;
}
`;

const fragmentShader = `
uniform float u_intensity;
uniform float u_time;
uniform vec3 u_color;

varying vec2 vUv;
varying float vDisplacement;

void main() {
    float distort = 2.0 * vDisplacement * u_intensity * sin(vUv.y * 10.0 + u_time);
    vec3 color = mix(u_color, vec3(1.0, 1.0, 1.0), distort);
    gl_FragColor = vec4(color, 1.0);
}
`;

function Blob({ scrollProgress }) {
  const mesh = useRef(null);
  const targetPosition = useRef(new Vector3(0, 0, 0));
  const currentPosition = useRef(new Vector3(0, 0, 0));
  
  // Track mouse globally since canvas pointer-events are none
  const mousePos = useRef({ x: 0, y: 0 });

  useEffect(() => {
    const handleMouseMove = (e) => {
      // Normalize to -1 to 1
      mousePos.current.x = (e.clientX / window.innerWidth) * 2 - 1;
      mousePos.current.y = -(e.clientY / window.innerHeight) * 2 + 1;
    };
    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  const uniforms = useMemo(
    () => ({
      u_time: { value: 0 },
      u_intensity: { value: 0.1 }, // Starts dormant
      u_color: { value: new Color(0x222222) }, // Starts dark
    }),
    []
  );

  const activeColor = useMemo(() => new Color(0xffffff), []); // Orange/hot color when active

  useFrame((state) => {
    const { clock } = state;
    if (mesh.current) {
      const material = mesh.current.material;
      material.uniforms.u_time.value = 0.4 * clock.getElapsedTime();

      // Tie intensity to scroll progress
      const p = scrollProgress.current || 0;
      const targetIntensity = p > 0.05 ? 0.7 : 0.4; // Brighter dormant state
      
      // Interpolate color from warm dark orange to hot orange
      material.uniforms.u_color.value.lerpColors(
        new Color(0x222222), // Visible, deep red/orange instead of near black
        activeColor, 
        Math.min(1, p * 4) 
      );

      material.uniforms.u_intensity.value = MathUtils.lerp(
        material.uniforms.u_intensity.value,
        targetIntensity,
        0.05
      );

      // Follow mouse
      targetPosition.current.set(mousePos.current.x * 0.8, mousePos.current.y * 0.8, 0);
      currentPosition.current.lerp(targetPosition.current, 0.05);
      mesh.current.position.copy(currentPosition.current);
    }
  });

  return (
    <mesh ref={mesh} scale={1.8}>
      <icosahedronGeometry args={[2, 64]} />
      <shaderMaterial
        vertexShader={vertexShader}
        fragmentShader={fragmentShader}
        uniforms={uniforms}
        wireframe={false}
      />
    </mesh>
  );
}

export default function GlobeOrb({ scrollProgress }) {
  // If scrollProgress isn't provided, use a dummy ref
  const fallbackRef = useRef(0);
  const progress = scrollProgress || fallbackRef;

  return (
    <Canvas 
      camera={{ position: [0.0, 0.0, 18.0] }}
      gl={{ antialias: true, alpha: true }}
    >
      <Blob scrollProgress={progress} />
    </Canvas>
  );
}
