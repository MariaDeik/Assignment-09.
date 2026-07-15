// hero3d.js — genuine WebGL/Three.js enterprise rack scene for the homepage hero.
// Loaded dynamically (see inline bootstrap in the hero markup) only when WebGL
// is available and the hero has scrolled into view. Exposes initHeroScene().

import * as THREE from 'three';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

const ACCENT_GREEN = 0x6fae00;
const ACCENT_GREEN_DARK = 0x2c4600;

export function initHeroScene(opts) {
  const options = opts || {};
  const reduceMotion = !!options.reduceMotion;
  const isMobile = !!options.isMobile;

  const mount = document.getElementById('hero3d');
  const canvas = document.getElementById('hero3d-canvas');
  const tooltip = document.getElementById('hero3d-tooltip');
  if (!mount || !canvas) return;

  // ---------- renderer / scene / camera ----------
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, isMobile ? 1.5 : 2));
  if ('outputColorSpace' in renderer) renderer.outputColorSpace = THREE.SRGBColorSpace;

  const scene = new THREE.Scene();
  scene.background = null; // transparent — the light CSS gradient shows through

  // Soft studio environment map so the metallic materials actually have
  // something to reflect — without this, high-metalness PBR surfaces render
  // almost black no matter how many direct lights are pointed at them.
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;

  const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 100);
  camera.position.set(0.3, 0.9, 7.0);
  camera.lookAt(0, 0.1, 0);

  function sizeToContainer() {
    const w = mount.clientWidth || 1;
    const h = mount.clientHeight || 1;
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h, false);
  }
  sizeToContainer();
  window.addEventListener('resize', sizeToContainer);
  if (window.ResizeObserver) {
    new ResizeObserver(sizeToContainer).observe(mount);
  }

  // ---------- lighting (soft studio, no harsh single source) ----------
  scene.add(new THREE.AmbientLight(0xffffff, 0.7));
  const key = new THREE.DirectionalLight(0xffffff, 1.6);
  key.position.set(4, 6, 5);
  scene.add(key);
  const frontFill = new THREE.DirectionalLight(0xffffff, 0.9);
  frontFill.position.set(0.5, 1.5, 8);
  scene.add(frontFill);
  const fillLight = new THREE.DirectionalLight(0xdfeeff, 0.5);
  fillLight.position.set(-5, 2, -2);
  scene.add(fillLight);
  const rimLight = new THREE.DirectionalLight(0xdfe8f5, 0.22);
  rimLight.position.set(-2, 3, -6);
  scene.add(rimLight);

  // ---------- materials ----------
  const matFrame = new THREE.MeshStandardMaterial({ color: 0x24272d, metalness: 0.6, roughness: 0.4 });
  const matPanel = new THREE.MeshStandardMaterial({ color: 0x181a1f, metalness: 0.55, roughness: 0.45 });
  const matChassis = new THREE.MeshStandardMaterial({ color: 0x2e323a, metalness: 0.55, roughness: 0.4 });
  const matVent = new THREE.MeshStandardMaterial({ color: 0x1c1f24, metalness: 0.45, roughness: 0.55 });
  const matAccentTrim = new THREE.MeshStandardMaterial({ color: ACCENT_GREEN, metalness: 0.3, roughness: 0.4, emissive: ACCENT_GREEN_DARK, emissiveIntensity: 0.18 });
  const matLedGreen = () => new THREE.MeshBasicMaterial({ color: ACCENT_GREEN });
  const matLedWhite = () => new THREE.MeshBasicMaterial({ color: 0xffffff });

  // ---------- rack root ----------
  const rack = new THREE.Group();
  scene.add(rack);

  const leds = []; // {mesh, phase, speed}
  const tooltipTargets = []; // meshes with userData.tooltip

  function tagTooltip(mesh, tip) {
    mesh.userData.tooltip = tip;
    tooltipTargets.push(mesh);
  }

  const TIP_COMPUTE = { title: 'Compute Node', lines: ['8× NVIDIA H200 GPUs', '141 GB HBM3e each'] };
  const TIP_NET = { title: 'Networking', lines: ['NVLink Fabric', '900 GB/s bandwidth'] };
  const TIP_COOL = { title: 'Cooling', lines: ['Liquid cooling', 'Enterprise thermal management'] };
  const TIP_POWER = { title: 'Power', lines: ['Redundant power supplies'] };

  // Rack frame — an OPEN 19"-style frame (side rails + top/bottom caps + a
  // slim rear backing panel), not a solid box. A solid enclosure would hide
  // every component modeled below behind its own front face.
  const cabinetW = 2.3, cabinetH = 4.0, cabinetD = 1.6;
  const railW = 0.14;
  const railGeo = new THREE.BoxGeometry(railW, cabinetH, cabinetD);
  const railL = new THREE.Mesh(railGeo, matFrame);
  railL.position.set(-(cabinetW / 2 - railW / 2), 0, 0);
  rack.add(railL);
  const railR = new THREE.Mesh(railGeo, matFrame);
  railR.position.set(cabinetW / 2 - railW / 2, 0, 0);
  rack.add(railR);
  const capGeo = new THREE.BoxGeometry(cabinetW, railW, cabinetD);
  const capTop = new THREE.Mesh(capGeo, matFrame);
  capTop.position.set(0, cabinetH / 2 - railW / 2, 0);
  rack.add(capTop);
  const capBottom = new THREE.Mesh(capGeo, matFrame);
  capBottom.position.set(0, -(cabinetH / 2 - railW / 2), 0);
  rack.add(capBottom);
  const backPanel = new THREE.Mesh(
    new THREE.BoxGeometry(cabinetW - railW * 2, cabinetH - railW * 2, 0.06),
    matPanel
  );
  backPanel.position.set(0, 0, -(cabinetD / 2 - 0.03));
  rack.add(backPanel);

  // Compute node chassis, stacked
  const NODE_COUNT = 4;
  const nodeH = 0.5;
  const nodeGap = 0.08;
  const nodeTopY = 0.82; // topmost node center; leaves headroom for the switch + cooling unit above
  const nodeGroup = new THREE.Group();
  for (let i = 0; i < NODE_COUNT; i++) {
    const y = nodeTopY - i * (nodeH + nodeGap);
    const node = new THREE.Mesh(new THREE.BoxGeometry(1.94, nodeH, 1.28), matChassis);
    node.position.set(0, y, 0.05);
    tagTooltip(node, TIP_COMPUTE);
    nodeGroup.add(node);

    // GPU trays on the front face
    const trayCount = 4;
    for (let t = 0; t < trayCount; t++) {
      const tray = new THREE.Mesh(new THREE.BoxGeometry(0.4, nodeH * 0.62, 0.04), matPanel);
      tray.position.set(-0.75 + t * 0.5, y, 0.72);
      tagTooltip(tray, TIP_COMPUTE);
      nodeGroup.add(tray);
    }

    // slim accent trim line
    const trim = new THREE.Mesh(new THREE.BoxGeometry(1.94, 0.02, 0.02), matAccentTrim);
    trim.position.set(0, y + nodeH / 2 - 0.03, 0.7);
    nodeGroup.add(trim);

    // vent slats (instanced, static, decorative)
    const slatCount = isMobile ? 4 : 7;
    const slatGeo = new THREE.BoxGeometry(1.7, 0.015, 0.02);
    const slats = new THREE.InstancedMesh(slatGeo, matVent, slatCount);
    const m = new THREE.Matrix4();
    for (let s = 0; s < slatCount; s++) {
      m.setPosition(0, y - nodeH / 2 + 0.05 + s * 0.055, 0.68);
      slats.setMatrixAt(s, m);
    }
    nodeGroup.add(slats);

    // status LED
    const led = new THREE.Mesh(new THREE.SphereGeometry(0.024, 8, 8), i % 3 === 0 ? matLedWhite() : matLedGreen());
    led.position.set(0.9, y, 0.7);
    led.userData.isLed = true;
    led.userData.phase = Math.random() * Math.PI * 2;
    led.userData.speed = 0.35 + Math.random() * 0.5;
    leds.push(led);
    nodeGroup.add(led);
  }
  rack.add(nodeGroup);

  // Network switch (top, sits just above the topmost compute node)
  const netY = nodeTopY + (nodeH + nodeGap);
  const netUnit = new THREE.Mesh(new THREE.BoxGeometry(1.94, 0.32, 1.28), matFrame);
  netUnit.position.set(0, netY, 0.05);
  tagTooltip(netUnit, TIP_NET);
  rack.add(netUnit);
  const portCount = isMobile ? 5 : 8;
  for (let p = 0; p < portCount; p++) {
    const port = new THREE.Mesh(new THREE.SphereGeometry(0.02, 6, 6), p % 2 === 0 ? matLedGreen() : matLedWhite());
    port.position.set(-0.8 + p * (1.6 / (portCount - 1)), netY, 0.72);
    port.userData.isLed = true;
    port.userData.phase = Math.random() * Math.PI * 2;
    port.userData.speed = 0.4 + Math.random() * 0.6;
    leds.push(port);
    rack.add(port);
  }

  // Cooling module (liquid-cooling manifold / CDU) — rear-mounted unit,
  // sized to stay within the cabinet's interior headroom above the switch
  const coolY = netY + 0.28;
  const coolUnit = new THREE.Mesh(new THREE.BoxGeometry(2.0, 0.34, 0.28), matChassis);
  coolUnit.position.set(0, coolY, -0.62);
  tagTooltip(coolUnit, TIP_COOL);
  rack.add(coolUnit);
  for (let c = 0; c < 3; c++) {
    const pipe = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.035, 1.9, 10), matAccentTrim);
    pipe.rotation.z = Math.PI / 2;
    pipe.position.set(0, coolY + (c - 1) * 0.1, -0.62);
    tagTooltip(pipe, TIP_COOL);
    rack.add(pipe);
  }

  // Power modules (bottom)
  const psuY = -1.35;
  for (let pI = 0; pI < 2; pI++) {
    const psu = new THREE.Mesh(new THREE.BoxGeometry(0.94, 0.38, 1.28), matChassis);
    psu.position.set(-0.5 + pI * 1.0, psuY, 0.05);
    tagTooltip(psu, TIP_POWER);
    rack.add(psu);
    const psuLed = new THREE.Mesh(new THREE.SphereGeometry(0.024, 6, 6), matLedGreen());
    psuLed.position.set(-0.5 + pI * 1.0, psuY, 0.72);
    psuLed.userData.isLed = true;
    psuLed.userData.phase = Math.random() * Math.PI * 2;
    psuLed.userData.speed = 0.3 + Math.random() * 0.4;
    leds.push(psuLed);
    rack.add(psuLed);
  }

  // ---------- data-flow particles (NVLink / InfiniBand traffic) ----------
  const flowGroup = new THREE.Group();
  const flowCount = isMobile ? 4 : 8;
  const flowParticles = [];
  const nodeAnchors = [];
  for (let i = 0; i < NODE_COUNT; i++) {
    nodeAnchors.push(new THREE.Vector3(0.9, nodeTopY - i * (nodeH + nodeGap), 0.72));
  }
  const netAnchor = new THREE.Vector3(-0.8, netY, 0.72);
  for (let i = 0; i < flowCount; i++) {
    const dot = new THREE.Mesh(new THREE.SphereGeometry(0.018, 6, 6), matLedGreen());
    const target = nodeAnchors[i % nodeAnchors.length];
    flowParticles.push({
      mesh: dot,
      from: netAnchor,
      to: target,
      t: Math.random(),
      speed: 0.06 + Math.random() * 0.05
    });
    flowGroup.add(dot);
  }
  rack.add(flowGroup);

  // ---------- ground shadow — a single soft blurred disc for grounding,
  // no technical grid / no drifting particle field (kept deliberately quiet
  // so the rack itself stays the only thing that draws the eye) ----------
  const shadowCanvas = document.createElement('canvas');
  shadowCanvas.width = shadowCanvas.height = 128;
  const sctx = shadowCanvas.getContext('2d');
  const grad = sctx.createRadialGradient(64, 64, 0, 64, 64, 64);
  grad.addColorStop(0, 'rgba(0,0,0,.28)');
  grad.addColorStop(1, 'rgba(0,0,0,0)');
  sctx.fillStyle = grad;
  sctx.fillRect(0, 0, 128, 128);
  const shadowTex = new THREE.CanvasTexture(shadowCanvas);
  const shadowMat = new THREE.MeshBasicMaterial({ map: shadowTex, transparent: true, depthWrite: false });
  const shadowMesh = new THREE.Mesh(new THREE.PlaneGeometry(3.6, 3.6), shadowMat);
  shadowMesh.rotation.x = -Math.PI / 2;
  shadowMesh.position.set(0, -2.02, 0);
  scene.add(shadowMesh);

  // ---------- interaction state ----------
  const state = {
    mouseNX: 0,
    mouseNY: 0,
    autoYaw: 0,
    curYaw: 0,
    curPitch: 0,
    floatBase: 0
  };
  const MAX_YAW = 0.2;

  const raycaster = new THREE.Raycaster();
  const pointerNDC = new THREE.Vector2(0, 0);
  let pointerInside = false;

  if (!isMobile && !reduceMotion) {
    mount.addEventListener('pointermove', (e) => {
      const rect = mount.getBoundingClientRect();
      const nx = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      const ny = ((e.clientY - rect.top) / rect.height) * 2 - 1;
      state.mouseNX = Math.max(-1, Math.min(1, nx));
      state.mouseNY = Math.max(-1, Math.min(1, ny));
      pointerNDC.set(state.mouseNX, -state.mouseNY);
      pointerInside = true;
    });
    mount.addEventListener('pointerleave', () => {
      state.mouseNX = 0;
      state.mouseNY = 0;
      pointerInside = false;
      hideTooltip();
    });
    mount.addEventListener('dblclick', () => {
      state.mouseNX = 0;
      state.mouseNY = 0;
      state.autoYaw = 0;
    });
  }

  function showTooltip(tip, clientX, clientY) {
    if (!tooltip) return;
    const rect = mount.getBoundingClientRect();
    const x = Math.max(12, Math.min(rect.width - 12, clientX - rect.left + 14));
    const y = Math.max(12, Math.min(rect.height - 12, clientY - rect.top - 10));
    tooltip.style.left = x + 'px';
    tooltip.style.top = y + 'px';
    tooltip.innerHTML = '<strong>' + tip.title + '</strong>' + tip.lines.map((l) => '<span>' + l + '</span>').join('');
    tooltip.classList.add('visible');
  }
  function hideTooltip() {
    if (tooltip) tooltip.classList.remove('visible');
  }

  let lastClientX = 0, lastClientY = 0;
  if (!isMobile) {
    mount.addEventListener('pointermove', (e) => {
      lastClientX = e.clientX;
      lastClientY = e.clientY;
    });
  }

  // ---------- animation loop ----------
  const clock = new THREE.Clock();
  let rafId = null;

  function frame() {
    rafId = requestAnimationFrame(frame);
    const dt = Math.min(clock.getDelta(), 0.05);
    const elapsed = clock.getElapsedTime();

    // slow, controlled auto rotation + gentle mouse-follow tilt (damped) —
    // deliberately restrained: a posed product shot, not a spinning demo
    state.autoYaw += dt * 0.025;
    const targetYaw = state.autoYaw + state.mouseNX * MAX_YAW;
    const targetPitch = -state.mouseNY * 0.1;
    state.curYaw += (targetYaw - state.curYaw) * 0.04;
    state.curPitch += (targetPitch - state.curPitch) * 0.04;
    state.curPitch = Math.max(-0.18, Math.min(0.18, state.curPitch));
    rack.rotation.y = state.curYaw;
    rack.rotation.x = state.curPitch;

    // very gentle floating motion
    rack.position.y = state.floatBase + Math.sin(elapsed * 0.4) * 0.03;

    // subtle status LEDs (slow, low-amplitude — not a blinking light show)
    for (let i = 0; i < leds.length; i++) {
      const l = leds[i];
      const b = 0.75 + 0.25 * Math.sin(elapsed * l.userData.speed + l.userData.phase);
      l.scale.setScalar(0.85 + b * 0.3);
    }

    // NVLink data-flow particles — slow and understated
    for (let i = 0; i < flowParticles.length; i++) {
      const p = flowParticles[i];
      p.t += dt * p.speed;
      if (p.t > 1) p.t -= 1;
      const arc = Math.sin(p.t * Math.PI) * 0.2;
      p.mesh.position.lerpVectors(p.from, p.to, p.t);
      p.mesh.position.y += arc;
    }

    // hover raycast (only when pointer is over the canvas, desktop only)
    if (pointerInside && tooltipTargets.length) {
      raycaster.setFromCamera(pointerNDC, camera);
      const hits = raycaster.intersectObjects(tooltipTargets, false);
      if (hits.length) {
        showTooltip(hits[0].object.userData.tooltip, lastClientX, lastClientY);
      } else {
        hideTooltip();
      }
    }

    renderer.render(scene, camera);
  }

  function play() {
    if (rafId === null) {
      clock.start();
      rafId = requestAnimationFrame(frame);
    }
  }
  function pause() {
    if (rafId !== null) {
      cancelAnimationFrame(rafId);
      rafId = null;
      clock.stop();
    }
  }

  document.addEventListener('visibilitychange', () => {
    if (document.hidden) pause();
    else if (!reduceMotion) play();
  });

  if (reduceMotion) {
    // one calm, static frame — no ongoing animation, no interaction
    renderer.render(scene, camera);
  } else {
    play();
  }
}
