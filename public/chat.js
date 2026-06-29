/* ═══════════════════════════════════════════════════════
   GeoVision AI Chat — Client Logic
   ═══════════════════════════════════════════════════════ */

(function () {
    'use strict';

    // ─── Theme Toggle ───
    const themeToggle = document.getElementById('theme-toggle');
    const savedTheme = localStorage.getItem('geovision-theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);

    function setThemeIcon(theme) {
        if (!themeToggle) return;
        themeToggle.innerHTML = theme === 'light'
            ? '<i data-lucide="moon"></i>'
            : '<i data-lucide="sun"></i>';
        if (window.lucide) lucide.createIcons();
    }
    setThemeIcon(savedTheme);

    if (themeToggle) {
        themeToggle.addEventListener('click', function () {
            const current = document.documentElement.getAttribute('data-theme');
            const next = current === 'dark' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', next);
            localStorage.setItem('geovision-theme', next);
            setThemeIcon(next);
        });
    }

    // ─── DOM References ───
    const form = document.getElementById('chat-form');
    const input = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');
    const messagesContainer = document.getElementById('messages-container');
    const messagesInner = document.getElementById('messages-inner');
    const chipsRow = document.getElementById('chips-row');
    const welcomeHero = document.getElementById('welcome-hero');

    // ─── State ───
    let mapCounter = 0;
    let isWaiting = false;
    let chatHistory = [];

    // ─── Land Cover Color Map ───
    const LC_COLORS = {
        'Water':       '#1565c0',
        'Forest':      '#2e7d32',
        'Bare Land':   '#a1887f',
        'Agriculture': '#f9a825',
        'Urban':       '#c62828',
    };

    function getLCColor(name) {
        return LC_COLORS[name] || '#6366f1';
    }

    // ═══════════════════════════════════════════════════
    // Textarea Auto-resize & Send Button State
    // ═══════════════════════════════════════════════════
    input.addEventListener('input', function () {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 120) + 'px';
        sendBtn.disabled = !this.value.trim();
    });

    // ═══════════════════════════════════════════════════
    // Keyboard Handling
    // ═══════════════════════════════════════════════════
    input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (this.value.trim() && !isWaiting) {
                form.dispatchEvent(new Event('submit', { cancelable: true }));
            }
        }
    });

    // ═══════════════════════════════════════════════════
    // Chip Clicks
    // ═══════════════════════════════════════════════════
    chipsRow.addEventListener('click', function (e) {
        const chip = e.target.closest('.chip');
        if (!chip || isWaiting) return;
        const prompt = chip.getAttribute('data-prompt');
        if (prompt) {
            input.value = prompt;
            input.style.height = 'auto';
            input.style.height = Math.min(input.scrollHeight, 120) + 'px';
            sendBtn.disabled = false;
            form.dispatchEvent(new Event('submit', { cancelable: true }));
        }
    });

    // ─── Pipeline Step Labels ───
    const STEP_LABELS = {
        resolve_location: 'Resolving Location',
        fetch_aoi: 'Fetching Area of Interest',
        build_composite_before: 'Building Before Composite',
        build_composite_after: 'Building After Composite',
        detect_changes: 'Detecting Changes',
        compute_stats: 'Computing Statistics',
    };

    // ═══════════════════════════════════════════════════
    // Form Submit — SSE Stream
    // ═══════════════════════════════════════════════════
    form.addEventListener('submit', async function (e) {
        e.preventDefault();
        const message = input.value.trim();
        if (!message || isWaiting) return;

        isWaiting = true;
        sendBtn.disabled = true;

        // Hide welcome + chips on first message
        if (welcomeHero) {
            welcomeHero.style.display = 'none';
        }
        chipsRow.style.display = 'none';

        // Add user bubble
        appendUserMessage(message);
        chatHistory.push({ role: 'user', content: message });

        // Clear input
        input.value = '';
        input.style.height = 'auto';

        // Show progress panel (replaces typing indicator)
        const progressEl = appendProgressPanel();
        scrollToBottom();

        try {
            const response = await fetch('/api/chat/stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message, history: chatHistory }),
            });

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let result = null;

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
                            const titleEl = progressEl.querySelector('.chat-progress-title');
                            const detailEl = progressEl.querySelector('.chat-progress-detail');
                            const barEl = progressEl.querySelector('.chat-progress-bar-fill');
                            const stepEl = progressEl.querySelector('.chat-progress-step');
                            if (titleEl) titleEl.textContent = STEP_LABELS[payload.step] || payload.step;
                            if (detailEl) detailEl.textContent = payload.detail;
                            if (barEl) barEl.style.width = pct + '%';
                            if (stepEl) stepEl.textContent = 'Step ' + payload.step_num + ' of ' + payload.total_steps;
                            scrollToBottom();
                        } else if (eventType === 'result') {
                            result = payload;
                            const barEl = progressEl.querySelector('.chat-progress-bar-fill');
                            if (barEl) barEl.style.width = '100%';
                            progressEl.classList.add('complete');
                        } else if (eventType === 'error') {
                            throw new Error(payload.error || 'Request failed');
                        }
                    } catch (parseErr) {
                        if (parseErr.message && !parseErr.message.includes('position')) throw parseErr;
                        console.warn('Failed to parse SSE event:', parseErr);
                    }
                }
            }

            // Remove progress panel
            progressEl.remove();

            if (result && result.success) {
                appendAIMessage(result);
                if (result.parsed) {
                    chatHistory.push({ role: 'assistant', content: JSON.stringify(result.parsed) });
                } else if (result.explanation) {
                    chatHistory.push({ role: 'assistant', content: result.explanation });
                }
            } else if (result && result.error) {
                appendErrorMessage(result.error);
            }
        } catch (err) {
            progressEl.remove();
            appendErrorMessage(err.message || 'Network error. Please check your connection.');
        }

        isWaiting = false;
        sendBtn.disabled = !input.value.trim();
        scrollToBottom();
    });

    // ═══════════════════════════════════════════════════
    // Message Builders
    // ═══════════════════════════════════════════════════

    function appendUserMessage(text) {
        const row = createElement('div', 'message-row user');
        const bubble = createElement('div', 'message-bubble user-bubble');
        bubble.textContent = text;
        row.appendChild(bubble);
        messagesInner.appendChild(row);
        scrollToBottom();
    }

    function appendProgressPanel() {
        const row = createElement('div', 'message-row ai');
        row.id = 'progress-row';

        const panel = createElement('div', 'chat-progress');
        panel.innerHTML = `
            <div class="chat-progress-spinner"></div>
            <div class="chat-progress-info">
                <div class="chat-progress-title">Analyzing…</div>
                <div class="chat-progress-detail">Initializing</div>
                <div class="chat-progress-bar-track">
                    <div class="chat-progress-bar-fill"></div>
                </div>
                <div class="chat-progress-step">Step 0 of 6</div>
            </div>
        `;

        row.appendChild(panel);
        messagesInner.appendChild(row);
        if (window.lucide) lucide.createIcons();
        return panel;
    }

    function appendAIMessage(data) {
        const { parsed, config, explanation } = data;

        const row = createElement('div', 'message-row ai');
        const bubble = createElement('div', 'message-bubble ai-bubble');
        const inner = createElement('div', 'ai-bubble-inner');

        // ── Avatar Row ──
        inner.appendChild(buildAvatarRow());

        // ── Parsed Params Pills ──
        if (parsed) {
            inner.appendChild(buildParsedPills(parsed));
        }

        // ── Map Section ──
        if (config) {
            const mapSection = buildMapSection(config);
            inner.appendChild(mapSection);
        }

        // ── Stats Section ──
        if (config && config.land_cover_stats && config.land_cover_stats.classes) {
            inner.appendChild(buildStatsSection(config.land_cover_stats.classes));
        }

        // ── Explanation ──
        if (explanation) {
            inner.appendChild(buildExplanation(explanation));
        }

        bubble.appendChild(inner);
        row.appendChild(bubble);
        messagesInner.appendChild(row);

        // Initialize map after DOM insertion
        if (config) {
            requestAnimationFrame(() => {
                setTimeout(() => {
                    initMap(config);
                    scrollToBottom();
                }, 80);
            });
        }
        
        if (window.lucide) lucide.createIcons();
    }

    function appendErrorMessage(errorText) {
        const row = createElement('div', 'message-row ai');
        const bubble = createElement('div', 'message-bubble ai-bubble');
        const inner = createElement('div', 'ai-bubble-inner');

        inner.appendChild(buildAvatarRow());

        const errDiv = createElement('div', 'error-content');
        errDiv.innerHTML = `
            <i data-lucide="triangle-alert"></i>
            <span>${escapeHtml(errorText)}</span>
        `;
        inner.appendChild(errDiv);

        bubble.appendChild(inner);
        row.appendChild(bubble);
        messagesInner.appendChild(row);
        
        if (window.lucide) lucide.createIcons();
    }

    // ═══════════════════════════════════════════════════
    // Component Builders
    // ═══════════════════════════════════════════════════

    function buildAvatarRow() {
        const div = createElement('div', 'ai-avatar-row');
        div.innerHTML = `
            <div class="ai-avatar">
                <i data-lucide="bot"></i>
            </div>
            <span class="ai-avatar-label">GeoVision AI</span>
        `;
        return div;
    }

    function buildParsedPills(parsed) {
        const container = createElement('div', 'parsed-params');

        if (parsed.location) {
            container.appendChild(makePill('<i data-lucide="map-pin"></i>', parsed.location));
        }
        if (parsed.city) {
            container.appendChild(makePill('<i data-lucide="building-2"></i>', parsed.city));
        }
        if (parsed.before_date) {
            container.appendChild(makePill('<i data-lucide="calendar"></i>', 'Before: ' + parsed.before_date));
        }
        if (parsed.after_date) {
            container.appendChild(makePill('<i data-lucide="calendar"></i>', 'After: ' + parsed.after_date));
        }

        return container;
    }

    function makePill(iconHtml, text) {
        const pill = createElement('span', 'param-pill');
        pill.innerHTML = `${iconHtml}${escapeHtml(text)}`;
        return pill;
    }

    function buildMapSection(config) {
        mapCounter++;
        const beforeMapId = 'chat-map-before-' + mapCounter;
        const afterMapId = 'chat-map-after-' + mapCounter;

        const section = createElement('div', 'map-section');
        const grid = createElement('div', 'map-grid');

        // ── Before Panel ──
        const beforePanel = createElement('div', 'map-panel');
        const beforeLabel = createElement('div', 'map-panel-label');
        beforeLabel.innerHTML = '<span class="map-panel-dot before"></span>Before' +
            (config.before_label ? ' <span class="map-panel-date">' + escapeHtml(config.before_label) + '</span>' : '');
        const beforeFrame = createElement('div', 'map-frame');
        const beforeDiv = createElement('div', 'map-instance');
        beforeDiv.id = beforeMapId;
        beforeFrame.appendChild(beforeDiv);
        beforePanel.appendChild(beforeLabel);
        beforePanel.appendChild(beforeFrame);

        // ── After Panel ──
        const afterPanel = createElement('div', 'map-panel');
        const afterLabelEl = createElement('div', 'map-panel-label');
        afterLabelEl.innerHTML = '<span class="map-panel-dot after"></span>After' +
            (config.after_label ? ' <span class="map-panel-date">' + escapeHtml(config.after_label) + '</span>' : '');
        const afterFrame = createElement('div', 'map-frame');
        const afterDiv = createElement('div', 'map-instance');
        afterDiv.id = afterMapId;
        afterFrame.appendChild(afterDiv);
        afterPanel.appendChild(afterLabelEl);
        afterPanel.appendChild(afterFrame);

        grid.appendChild(beforePanel);
        grid.appendChild(afterPanel);
        section.appendChild(grid);

        return section;
    }

    function initMap(config) {
        const beforeMapId = 'chat-map-before-' + mapCounter;
        const afterMapId = 'chat-map-after-' + mapCounter;
        const beforeEl = document.getElementById(beforeMapId);
        const afterEl = document.getElementById(afterMapId);
        if (!beforeEl || !afterEl) return;

        const center = config.center || [20, 78];
        const mapOpts = { center: center, zoom: 11, zoomControl: true, attributionControl: false };

        const beforeMap = L.map(beforeMapId, mapOpts);
        const afterMap = L.map(afterMapId, mapOpts);

        // ── Satellite basemap on both ──
        const esriUrl = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}';
        L.tileLayer(esriUrl, { maxZoom: 18 }).addTo(beforeMap);
        L.tileLayer(esriUrl, { maxZoom: 18 }).addTo(afterMap);

        // ── Before Map Layers ──
        if (config.before_tiles) {
            L.tileLayer(config.before_tiles, { maxZoom: 19, opacity: 0.9 }).addTo(beforeMap);
        }
        const beforeOverlays = {};
        if (config.change_mask_tiles) {
            const changeMaskBefore = L.tileLayer(config.change_mask_tiles, { maxZoom: 19, opacity: 0.7 });
            beforeOverlays['Change Mask'] = changeMaskBefore;
        }
        if (config.land_cover_before_tiles) {
            const lcBefore = L.tileLayer(config.land_cover_before_tiles, { maxZoom: 19, opacity: 0.8 });
            beforeOverlays['Land Cover'] = lcBefore;
        }
        if (Object.keys(beforeOverlays).length > 0) {
            L.control.layers(null, beforeOverlays, { collapsed: true, position: 'topright' }).addTo(beforeMap);
        }

        // ── After Map Layers ──
        if (config.after_tiles) {
            L.tileLayer(config.after_tiles, { maxZoom: 19, opacity: 0.9 }).addTo(afterMap);
        }
        const afterOverlays = {};
        if (config.change_mask_tiles) {
            const changeMaskAfter = L.tileLayer(config.change_mask_tiles, { maxZoom: 19, opacity: 0.7 });
            afterOverlays['Change Mask'] = changeMaskAfter;
        }
        if (config.land_cover_after_tiles) {
            const lcAfter = L.tileLayer(config.land_cover_after_tiles, { maxZoom: 19, opacity: 0.8 });
            afterOverlays['Land Cover'] = lcAfter;
        }
        if (Object.keys(afterOverlays).length > 0) {
            L.control.layers(null, afterOverlays, { collapsed: true, position: 'topright' }).addTo(afterMap);
        }

        // ── AOI Polygon on both maps ──
        const aoiStyle = {
            color: '#6366f1', weight: 2, opacity: 0.8,
            fillColor: '#6366f1', fillOpacity: 0.05, dashArray: '6 4',
        };
        if (config.aoi) {
            try {
                const aoiBefore = L.geoJSON(config.aoi, { style: aoiStyle });
                const aoiAfter = L.geoJSON(config.aoi, { style: aoiStyle });
                aoiBefore.addTo(beforeMap);
                aoiAfter.addTo(afterMap);
                beforeMap.fitBounds(aoiBefore.getBounds(), { padding: [20, 20] });
                afterMap.fitBounds(aoiAfter.getBounds(), { padding: [20, 20] });
            } catch (e) {
                beforeMap.setView(center, 11);
                afterMap.setView(center, 11);
            }
        }

        // ── Sync zoom & pan between the two maps ──
        let syncing = false;
        function syncMap(source, target) {
            source.on('move', function () {
                if (syncing) return;
                syncing = true;
                target.setView(source.getCenter(), source.getZoom(), { animate: false });
                syncing = false;
            });
        }
        syncMap(beforeMap, afterMap);
        syncMap(afterMap, beforeMap);

        // ── Sync overlays between the two maps ──
        let syncingOverlays = false;
        function syncOverlays(source, target, sourceOverlays, targetOverlays) {
            source.on('overlayadd', function(e) {
                if (syncingOverlays) return;
                const name = e.name;
                if (targetOverlays[name] && !target.hasLayer(targetOverlays[name])) {
                    syncingOverlays = true;
                    targetOverlays[name].addTo(target);
                    syncingOverlays = false;
                }
            });
            source.on('overlayremove', function(e) {
                if (syncingOverlays) return;
                const name = e.name;
                if (targetOverlays[name] && target.hasLayer(targetOverlays[name])) {
                    syncingOverlays = true;
                    target.removeLayer(targetOverlays[name]);
                    syncingOverlays = false;
                }
            });
        }
        syncOverlays(beforeMap, afterMap, beforeOverlays, afterOverlays);
        syncOverlays(afterMap, beforeMap, afterOverlays, beforeOverlays);

        // ── Invalidate sizes ──
        setTimeout(function () {
            beforeMap.invalidateSize();
            afterMap.invalidateSize();
        }, 200);

        const observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    beforeMap.invalidateSize();
                    afterMap.invalidateSize();
                }
            });
        });
        observer.observe(beforeEl);
    }

    function buildStatsSection(classes) {
        const section = createElement('div', 'stats-section');

        const header = createElement('div', 'stats-title');
        header.textContent = 'Land Cover Changes';
        section.appendChild(header);

        const grid = createElement('div', 'stats-grid');

        // Find max value for bar scaling
        const maxVal = Math.max(...classes.map(c => Math.max(c.before || 0, c.after || 0)), 1);

        classes.forEach(function (cls) {
            const row = createElement('div', 'stat-row');
            const color = getLCColor(cls.name);

            const beforePct = ((cls.before || 0) / maxVal) * 100;
            const afterPct = ((cls.after || 0) / maxVal) * 100;
            const delta = cls.delta || 0;

            let deltaClass = 'neutral';
            let deltaText = '0%';
            if (delta > 0) {
                deltaClass = 'delta-pos';
                deltaText = '+' + delta + '%';
            } else if (delta < 0) {
                deltaClass = 'delta-neg';
                deltaText = delta + '%';
            }

            row.innerHTML = `
                <div class="stat-label">
                    <span class="stat-color-dot" style="background:${color}"></span>
                    ${escapeHtml(cls.name)}
                </div>
                <div class="stat-bar-container">
                    <div class="stat-bar-wrap">
                        <div class="stat-bar-before" style="width:${beforePct}%;background:${color}"></div>
                        <div class="stat-bar-after" style="width:${afterPct}%;background:${color}"></div>
                    </div>
                </div>
                <div class="stat-value">${cls.before ?? '-'}%</div>
                <div class="stat-value">${cls.after ?? '-'}%</div>
                <div class="stat-delta ${deltaClass}">${deltaText}</div>
            `;

            grid.appendChild(row);
        });

        // Column labels
        const labels = createElement('div', 'stat-row stat-header-row');
        labels.innerHTML = `
            <div></div>
            <div></div>
            <div class="stat-value" style="font-size:10px;">Before</div>
            <div class="stat-value" style="font-size:10px;">After</div>
            <div class="stat-delta" style="font-size:10px;color:var(--text-tertiary)">Δ</div>
        `;
        grid.insertBefore(labels, grid.firstChild);

        section.appendChild(grid);
        return section;
    }

    function buildExplanation(text) {
        const section = createElement('div', 'explanation-section');
        section.innerHTML = marked.parse(text);
        return section;
    }

    // ═══════════════════════════════════════════════════
    // Helpers
    // ═══════════════════════════════════════════════════

    function createElement(tag, className) {
        const el = document.createElement(tag);
        if (className) el.className = className;
        return el;
    }

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.appendChild(document.createTextNode(str));
        return div.innerHTML;
    }

    function scrollToBottom() {
        requestAnimationFrame(function () {
            messagesContainer.scrollTo({
                top: messagesContainer.scrollHeight,
                behavior: 'smooth'
            });
        });
    }

})();
