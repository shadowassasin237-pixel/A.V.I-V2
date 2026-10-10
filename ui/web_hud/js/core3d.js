/**
 * A.V.I. 3D Holographic Reactor Core
 * Matches reference designs (Images 1 & 5):
 * - Dense concentric horizontal latitude filament sphere (armillary energy sphere)
 * - Two major vertical perpendicular orbital halos (XY and ZY planes) with tick markers
 * - Concentric technological segmented HUD rings with counter-rotations and tick marks
 * - Brilliant white-hot fusion heart with multi-layer additive glow bloom
 * - Horizontal equatorial energy beam / flare disc
 * - Smooth floating glowing particle dust (soft glowing circular points)
 * - Deep crimson, scarlet, ember-orange, and incandescent white-hot palette
 */

window.ReactorCore = (function () {
    let container, renderer, scene, camera;
    let coreGroup, sphereFilamentGroup, outerHudGroup;
    let centralStar, glowSprite, equatorialBeam;
    let latitudeRings = [];
    let verticalHalo1, verticalHalo2;
    let techRing1, techRing2, techRing3;
    let particlePoints;

    let currentState = 'idle';
    let targetState = 'idle';
    let voiceLevel = 0.08;
    let smoothedVoiceLevel = 0.08;

    let animationId;
    let clock;
    let glowCanvas, glowCtx;

    const stateParams = {
        idle: { speed: 0.8, pulseSpeed: 1.2, intensity: 0.7, ringRot: 0.6, particleSpread: 2.2 },
        listening: { speed: 1.5, pulseSpeed: 2.5, intensity: 1.1, ringRot: 1.8, particleSpread: 1.9 },
        thinking: { speed: 2.8, pulseSpeed: 4.0, intensity: 0.9, ringRot: 3.5, particleSpread: 2.4 },
        speaking: { speed: 1.4, pulseSpeed: 2.8, intensity: 1.3, ringRot: 1.6, particleSpread: 2.8 }
    };

    let currentParams = { ...stateParams.idle };

    // Helper: Create a glowing circular soft particle texture
    function createGlowTexture(size = 128, innerColor = 'rgba(255, 255, 255, 1)', midColor = 'rgba(255, 25, 60, 0.8)', outerColor = 'rgba(255, 15, 45, 0)') {
        const c = document.createElement('canvas');
        c.width = size;
        c.height = size;
        const ctx = c.getContext('2d');
        const cx = size / 2;
        const cy = size / 2;
        const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, size / 2);
        grad.addColorStop(0, innerColor);
        grad.addColorStop(0.2, midColor);
        grad.addColorStop(0.6, 'rgba(200, 15, 40, 0.25)');
        grad.addColorStop(1, outerColor);
        ctx.fillStyle = grad;
        ctx.fillRect(0, 0, size, size);
        return new THREE.CanvasTexture(c);
    }

    // Helper: Create a segmented circular arc
    function createSegmentedArc(radius, startAngle, endAngle, segments = 32) {
        const points = [];
        const delta = (endAngle - startAngle) / segments;
        for (let i = 0; i <= segments; i++) {
            const theta = startAngle + i * delta;
            points.push(new THREE.Vector3(Math.cos(theta) * radius, Math.sin(theta) * radius, 0));
        }
        const geom = new THREE.BufferGeometry().setFromPoints(points);
        return geom;
    }

    function init(containerId) {
        container = document.getElementById(containerId);
        if (!container) {
            console.error('ReactorCore: Container not found', containerId);
            return;
        }

        // Clean container if re-initialized
        while (container.firstChild) {
            container.removeChild(container.firstChild);
        }

        clock = new THREE.Clock();

        // 1. Renderer with WebGL
        renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, powerPreference: 'high-performance' });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        renderer.setSize(container.clientWidth, container.clientHeight);
        renderer.setClearColor(0x000000, 0);

        container.appendChild(renderer.domElement);

        // 2. Scene & Camera
        scene = new THREE.Scene();
        camera = new THREE.PerspectiveCamera(45, container.clientWidth / container.clientHeight, 0.1, 100);
        camera.position.set(0, 0, 5.2);

        // 3. Build the True Holographic Orb
        buildScene();

        // 4. Bloom overlay canvas
        setupGlowCanvas();

        window.addEventListener('resize', resize, false);
        animate();
    }

    function buildScene() {
        coreGroup = new THREE.Group();
        sphereFilamentGroup = new THREE.Group();
        outerHudGroup = new THREE.Group();

        const crimsonRed = 0xff1535;
        const scarlet = 0xff3b5c;
        const emberOrange = 0xff6611;
        const glowAmber = 0xff9922;

        // ========================================================
        // 1. DENSE LATITUDE FILAMENT SPHERE (Matches Image 5)
        // 46 stacked horizontal circular latitude rings from pole to pole
        // ========================================================
        const sphereRadius = 1.15;
        const ringCount = 46;
        latitudeRings = [];

        for (let i = 1; i < ringCount; i++) {
            // y goes from -sphereRadius to +sphereRadius
            const phi = (i / ringCount) * Math.PI - (Math.PI / 2); // -PI/2 to +PI/2
            const y = Math.sin(phi) * sphereRadius;
            const r = Math.cos(phi) * sphereRadius;

            // Generate circular ring points
            const ringPts = [];
            const segs = 64;
            for (let j = 0; j <= segs; j++) {
                const theta = (j / segs) * Math.PI * 2;
                ringPts.push(new THREE.Vector3(Math.cos(theta) * r, y, Math.sin(theta) * r));
            }

            const ringGeo = new THREE.BufferGeometry().setFromPoints(ringPts);
            // Middle rings are brighter; pole rings slightly dimmer
            const factor = Math.cos(phi); // 1.0 at equator, 0 at poles
            const ringMat = new THREE.LineBasicMaterial({
                color: (i % 2 === 0) ? scarlet : crimsonRed,
                transparent: true,
                opacity: 0.35 + factor * 0.45,
                blending: THREE.AdditiveBlending,
                linewidth: 1
            });

            const lineLoop = new THREE.Line(ringGeo, ringMat);
            lineLoop.userData = { baseY: y, baseRadius: r, phi: phi, index: i };
            sphereFilamentGroup.add(lineLoop);
            latitudeRings.push(lineLoop);
        }

        scene.add(sphereFilamentGroup);

        // ========================================================
        // 2. MAJOR VERTICAL GIMBAL / ORBITAL HALOS (Matches Image 5 & 1)
        // Two perpendicular vertical rings (XY and ZY) with tick markers
        // ========================================================
        const haloRadius = 1.25;

        // Halo 1: XY Plane
        const halo1Geo = new THREE.BufferGeometry().setFromPoints(
            Array.from({ length: 96 }, (_, i) => {
                const a = (i / 95) * Math.PI * 2;
                return new THREE.Vector3(Math.cos(a) * haloRadius, Math.sin(a) * haloRadius, 0);
            })
        );
        const haloMat = new THREE.LineBasicMaterial({
            color: 0xff3b5c,
            transparent: true,
            opacity: 0.85,
            blending: THREE.AdditiveBlending
        });
        verticalHalo1 = new THREE.Line(halo1Geo, haloMat);
        scene.add(verticalHalo1);

        // Halo 2: ZY Plane
        const halo2Geo = new THREE.BufferGeometry().setFromPoints(
            Array.from({ length: 96 }, (_, i) => {
                const a = (i / 95) * Math.PI * 2;
                return new THREE.Vector3(0, Math.sin(a) * haloRadius, Math.cos(a) * haloRadius);
            })
        );
        verticalHalo2 = new THREE.Line(halo2Geo, haloMat.clone());
        scene.add(verticalHalo2);

        // Add 4 Cardinal Vertex Points on the Halos (North, South, East, West poles)
        const markerTexture = createGlowTexture(64, 'rgba(255,255,255,1)', 'rgba(255,60,80,0.9)', 'rgba(0,0,0,0)');
        const markerMat = new THREE.SpriteMaterial({ map: markerTexture, blending: THREE.AdditiveBlending });

        const cardinalOffsets = [
            [0, haloRadius, 0], [0, -haloRadius, 0],
            [haloRadius, 0, 0], [-haloRadius, 0, 0],
            [0, 0, haloRadius], [0, 0, -haloRadius]
        ];
        cardinalOffsets.forEach(pos => {
            const spr = new THREE.Sprite(markerMat);
            spr.position.set(pos[0], pos[1], pos[2]);
            spr.scale.set(0.14, 0.14, 0.14);
            scene.add(spr);
        });

        // ========================================================
        // 3. CENTRAL FUSION STAR & GLOW HEART (Image 5)
        // Multi-layer high-intensity core with white-hot center
        // ========================================================
        // Inner white-hot sphere
        const starGeo = new THREE.SphereGeometry(0.24, 32, 32);
        const starMat = new THREE.MeshBasicMaterial({
            color: 0xffffff,
            transparent: true,
            opacity: 0.95
        });
        centralStar = new THREE.Mesh(starGeo, starMat);
        coreGroup.add(centralStar);

        // Multi-layer surrounding energy corona
        const coronaTexture = createGlowTexture(256, 'rgba(255, 255, 255, 1)', 'rgba(255, 30, 60, 0.85)', 'rgba(180, 10, 30, 0)');
        const coronaMat = new THREE.SpriteMaterial({
            map: coronaTexture,
            color: 0xff2244,
            transparent: true,
            opacity: 0.9,
            blending: THREE.AdditiveBlending
        });
        glowSprite = new THREE.Sprite(coronaMat);
        glowSprite.scale.set(1.5, 1.5, 1.5);
        coreGroup.add(glowSprite);

        // Secondary outer amber-red corona
        const outerCoronaMat = new THREE.SpriteMaterial({
            map: coronaTexture,
            color: 0xff5511,
            transparent: true,
            opacity: 0.45,
            blending: THREE.AdditiveBlending
        });
        const outerGlowSprite = new THREE.Sprite(outerCoronaMat);
        outerGlowSprite.scale.set(2.4, 2.4, 2.4);
        coreGroup.add(outerGlowSprite);

        // ========================================================
        // 4. HORIZONTAL EQUATORIAL BEAM & DISC (Image 5)
        // A luminous beam spanning horizontally across the core
        // ========================================================
        const beamPts = [
            new THREE.Vector3(-2.2, 0, 0),
            new THREE.Vector3(2.2, 0, 0)
        ];
        const beamGeo = new THREE.BufferGeometry().setFromPoints(beamPts);
        const beamMat = new THREE.LineBasicMaterial({
            color: 0xffeedd,
            transparent: true,
            opacity: 0.85,
            blending: THREE.AdditiveBlending,
            linewidth: 2
        });
        equatorialBeam = new THREE.Line(beamGeo, beamMat);
        coreGroup.add(equatorialBeam);

        // Horizontal luminous equatorial oval disc flare
        const beamSpriteMat = new THREE.SpriteMaterial({
            map: coronaTexture,
            color: 0xff2244,
            transparent: true,
            opacity: 0.7,
            blending: THREE.AdditiveBlending
        });
        const beamFlare = new THREE.Sprite(beamSpriteMat);
        beamFlare.scale.set(3.2, 0.22, 1.0); // Stretched horizontally
        coreGroup.add(beamFlare);

        scene.add(coreGroup);

        // ========================================================
        // 5. TECHNOLOGICAL SEGMENTED HUD RINGS (Matches Image 1)
        // Concentric circular technical tracks with arcs & tick marks
        // ========================================================
        // Outer Tech Ring 1 (radius 1.5): 4 counter-rotating arcs
        techRing1 = new THREE.Group();
        const arcCount = 4;
        for (let i = 0; i < arcCount; i++) {
            const startA = (i * (Math.PI * 2 / arcCount)) + 0.15;
            const endA = startA + (Math.PI * 2 / arcCount) - 0.3;
            const arcGeo = createSegmentedArc(1.48, startA, endA, 24);
            const arcLine = new THREE.Line(arcGeo, new THREE.LineBasicMaterial({
                color: crimsonRed,
                transparent: true,
                opacity: 0.7,
                blending: THREE.AdditiveBlending
            }));
            techRing1.add(arcLine);
        }
        // Add tick marks to Ring 1
        for (let i = 0; i < 24; i++) {
            const a = (i / 24) * Math.PI * 2;
            const tickGeo = new THREE.BufferGeometry().setFromPoints([
                new THREE.Vector3(Math.cos(a) * 1.44, Math.sin(a) * 1.44, 0),
                new THREE.Vector3(Math.cos(a) * 1.52, Math.sin(a) * 1.52, 0)
            ]);
            const tick = new THREE.Line(tickGeo, new THREE.LineBasicMaterial({
                color: (i % 6 === 0) ? 0xffffff : scarlet,
                transparent: true,
                opacity: 0.6,
                blending: THREE.AdditiveBlending
            }));
            techRing1.add(tick);
        }
        outerHudGroup.add(techRing1);

        // Outer Tech Ring 2 (radius 1.8): Delicate outer calibration boundary
        techRing2 = new THREE.Group();
        for (let i = 0; i < 6; i++) {
            const startA = (i * (Math.PI * 2 / 6)) + 0.1;
            const endA = startA + (Math.PI * 2 / 6) - 0.22;
            const arcGeo = createSegmentedArc(1.78, startA, endA, 20);
            const arcLine = new THREE.Line(arcGeo, new THREE.LineBasicMaterial({
                color: emberOrange,
                transparent: true,
                opacity: 0.55,
                blending: THREE.AdditiveBlending
            }));
            techRing2.add(arcLine);
        }
        outerHudGroup.add(techRing2);

        // Outer Tech Ring 3 (radius 2.05): Tilted orbital ring
        techRing3 = new THREE.Group();
        const outerCircleGeo = new THREE.BufferGeometry().setFromPoints(
            Array.from({ length: 80 }, (_, i) => {
                const a = (i / 80) * Math.PI * 2;
                return new THREE.Vector3(Math.cos(a) * 2.05, Math.sin(a) * 2.05, 0);
            })
        );
        const outerCircleLine = new THREE.Line(outerCircleGeo, new THREE.LineBasicMaterial({
            color: crimsonRed,
            transparent: true,
            opacity: 0.3,
            blending: THREE.AdditiveBlending
        }));
        techRing3.add(outerCircleLine);
        techRing3.rotation.x = 65 * (Math.PI / 180);
        outerHudGroup.add(techRing3);

        scene.add(outerHudGroup);

        // ========================================================
        // 6. FLOATING EMBER PARTICLE CLOUD (Soft Circular Sprites)
        // ========================================================
        const pCount = 180;
        const pGeo = new THREE.BufferGeometry();
        const pPos = new Float32Array(pCount * 3);
        const pCol = new Float32Array(pCount * 3);
        const pCustomData = [];

        for (let i = 0; i < pCount; i++) {
            const u = Math.random();
            const v = Math.random();
            const theta = u * 2.0 * Math.PI;
            const phi = Math.acos(2.0 * v - 1.0);
            const r = 0.8 + Math.random() * 1.8;

            const x = r * Math.sin(phi) * Math.cos(theta);
            const y = r * Math.sin(phi) * Math.sin(theta);
            const z = r * Math.cos(phi);

            pPos[i * 3] = x;
            pPos[i * 3 + 1] = y;
            pPos[i * 3 + 2] = z;

            // Warm gradient: crimson, scarlet, amber
            const isAmber = Math.random() > 0.65;
            pCol[i * 3] = 1.0;
            pCol[i * 3 + 1] = isAmber ? 0.5 : 0.15;
            pCol[i * 3 + 2] = isAmber ? 0.1 : 0.25;

            pCustomData.push({
                baseR: r,
                theta: theta,
                phi: phi,
                orbitSpeed: (Math.random() - 0.5) * 0.4,
                ySpeed: (Math.random() - 0.5) * 0.1
            });
        }

        pGeo.setAttribute('position', new THREE.BufferAttribute(pPos, 3));
        pGeo.setAttribute('color', new THREE.BufferAttribute(pCol, 3));
        pGeo.userData = { pCustomData };

        const pMat = new THREE.PointsMaterial({
            size: 0.08,
            map: markerTexture,
            vertexColors: true,
            transparent: true,
            opacity: 0.8,
            blending: THREE.AdditiveBlending,
            depthWrite: false
        });

        particlePoints = new THREE.Points(pGeo, pMat);
        scene.add(particlePoints);
    }

    // Glow canvas overlay for radial lens bloom
    function setupGlowCanvas() {
        glowCanvas = document.createElement('canvas');
        glowCanvas.style.position = 'absolute';
        glowCanvas.style.top = '0';
        glowCanvas.style.left = '0';
        glowCanvas.style.width = '100%';
        glowCanvas.style.height = '100%';
        glowCanvas.style.pointerEvents = 'none';
        glowCanvas.style.zIndex = '3';
        container.appendChild(glowCanvas);

        glowCtx = glowCanvas.getContext('2d');
        resizeGlowCanvas();
    }

    function resizeGlowCanvas() {
        if (!glowCanvas || !container) return;
        glowCanvas.width = container.clientWidth;
        glowCanvas.height = container.clientHeight;
    }

    function drawBloom(intensity) {
        if (!glowCtx) return;
        const w = glowCanvas.width;
        const h = glowCanvas.height;
        glowCtx.clearRect(0, 0, w, h);

        const cx = w / 2;
        const cy = h / 2;
        const baseRadius = Math.min(w, h) * 0.32;
        const r = baseRadius * (0.9 + intensity * 0.3);

        const grad = glowCtx.createRadialGradient(cx, cy, 0, cx, cy, r);
        grad.addColorStop(0, `rgba(255, 230, 240, ${0.45 * intensity})`);
        grad.addColorStop(0.15, `rgba(255, 30, 60, ${0.35 * intensity})`);
        grad.addColorStop(0.45, `rgba(200, 15, 40, ${0.12 * intensity})`);
        grad.addColorStop(0.8, `rgba(140, 10, 30, ${0.03 * intensity})`);
        grad.addColorStop(1, 'rgba(0, 0, 0, 0)');

        glowCtx.fillStyle = grad;
        glowCtx.fillRect(0, 0, w, h);
    }

    // ========================================================
    // ANIMATION & FRAME LOOP
    // ========================================================
    function animate() {
        animationId = requestAnimationFrame(animate);
        if (!renderer || !scene || !camera) return;

        const delta = clock.getDelta();
        const time = clock.getElapsedTime();

        // Smooth state transition
        const target = stateParams[currentState] || stateParams.idle;
        currentParams.speed += (target.speed - currentParams.speed) * (delta * 3.5);
        currentParams.pulseSpeed += (target.pulseSpeed - currentParams.pulseSpeed) * (delta * 3.5);
        currentParams.intensity += (target.intensity - currentParams.intensity) * (delta * 3.5);
        currentParams.ringRot += (target.ringRot - currentParams.ringRot) * (delta * 3.5);
        currentParams.particleSpread += (target.particleSpread - currentParams.particleSpread) * (delta * 3.5);

        smoothedVoiceLevel += (voiceLevel - smoothedVoiceLevel) * (delta * 8.0);

        const voiceReact = smoothedVoiceLevel * 0.8;
        const corePulse = Math.sin(time * currentParams.pulseSpeed) * 0.08 + (voiceReact * 0.25);
        const dynamicIntensity = currentParams.intensity + (voiceReact * 0.6);

        // 1. Rotate the Dense Latitude Filament Sphere
        if (sphereFilamentGroup) {
            sphereFilamentGroup.rotation.y = time * 0.22 * currentParams.speed;

            // Subtle vertical ripple along the latitude rings
            latitudeRings.forEach((line) => {
                const phi = line.userData.phi;
                const wave = Math.sin(time * 3.0 + phi * 4.0) * (0.015 + voiceReact * 0.03);
                line.position.y = wave;
            });
        }

        // 2. Rotate Vertical Halos (Perpendicular gimbals)
        if (verticalHalo1) {
            verticalHalo1.rotation.z = Math.sin(time * 0.3) * 0.15;
            verticalHalo1.rotation.y = time * 0.18 * currentParams.ringRot;
        }
        if (verticalHalo2) {
            verticalHalo2.rotation.x = Math.cos(time * 0.25) * 0.15;
            verticalHalo2.rotation.y = -time * 0.22 * currentParams.ringRot;
        }

        // 3. Counter-Rotate Technological HUD Rings
        if (techRing1) techRing1.rotation.z = time * 0.35 * currentParams.ringRot;
        if (techRing2) techRing2.rotation.z = -time * 0.25 * currentParams.ringRot;
        if (techRing3) {
            techRing3.rotation.z = time * 0.12 * currentParams.ringRot;
            techRing3.rotation.y = Math.sin(time * 0.2) * 0.2;
        }

        // 4. Pulse Central Star & Coronas
        if (centralStar) {
            const scale = (1.0 + corePulse) * (1.0 + voiceReact * 0.35);
            centralStar.scale.set(scale, scale, scale);
        }
        if (glowSprite) {
            const coronaScale = 1.5 * (1.0 + corePulse * 1.5) * (1.0 + voiceReact * 0.5);
            glowSprite.scale.set(coronaScale, coronaScale, coronaScale);
        }
        if (equatorialBeam) {
            const beamAlpha = 0.75 + Math.sin(time * 6.0) * 0.2 + (voiceReact * 0.3);
            equatorialBeam.material.opacity = Math.min(1.0, beamAlpha);
            const beamScaleX = 1.0 + voiceReact * 0.5;
            equatorialBeam.scale.set(beamScaleX, 1.0, 1.0);
        }

        // 5. Animate Floating Particles
        if (particlePoints) {
            const posAttr = particlePoints.geometry.attributes.position;
            const data = particlePoints.geometry.userData.pCustomData;

            for (let i = 0; i < data.length; i++) {
                const item = data[i];
                item.theta += item.orbitSpeed * delta * currentParams.speed;

                const currentR = item.baseR * (currentParams.particleSpread / 2.2) * (1.0 + voiceReact * 0.3);
                posAttr.array[i * 3] = currentR * Math.sin(item.phi) * Math.cos(item.theta);
                posAttr.array[i * 3 + 1] += item.ySpeed * delta;
                if (Math.abs(posAttr.array[i * 3 + 1]) > 2.0) item.ySpeed *= -1;
                posAttr.array[i * 3 + 2] = currentR * Math.cos(item.phi);
            }
            posAttr.needsUpdate = true;
        }

        // 6. Draw Lens Bloom Overlay
        drawBloom(dynamicIntensity);

        // 7. Subtle interactive camera float
        camera.position.x = Math.sin(time * 0.25) * 0.15;
        camera.position.y = Math.cos(time * 0.3) * 0.1;
        camera.lookAt(0, 0, 0);

        renderer.render(scene, camera);
    }

    // Public API
    function setState(state) {
        if (stateParams[state]) {
            currentState = state;
        }
    }

    function setVoiceLevel(level) {
        voiceLevel = Math.max(0.0, Math.min(1.0, level));
    }

    function resize() {
        if (!camera || !renderer || !container) return;
        camera.aspect = container.clientWidth / container.clientHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(container.clientWidth, container.clientHeight);
        resizeGlowCanvas();
    }

    function dispose() {
        if (animationId) cancelAnimationFrame(animationId);
        window.removeEventListener('resize', resize);
        if (renderer && renderer.domElement && container.contains(renderer.domElement)) {
            container.removeChild(renderer.domElement);
        }
        if (glowCanvas && container.contains(glowCanvas)) {
            container.removeChild(glowCanvas);
        }
        scene = null;
        camera = null;
        renderer = null;
    }

    return {
        init,
        setState,
        setVoiceLevel,
        resize,
        dispose
    };
})();
