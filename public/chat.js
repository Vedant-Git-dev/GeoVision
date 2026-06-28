/* ═══════════════════════════════════════════════════════
   GeoVision AI Chat — Client Logic
   ═══════════════════════════════════════════════════════ */

(function () {
    'use strict';

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

    // ═══════════════════════════════════════════════════
    // Form Submit
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

        // Show typing indicator
        const typingEl = appendTypingIndicator();
        scrollToBottom();

        try {
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message, history: chatHistory }),
            });

            const data = await res.json();

            // Remove typing indicator
            typingEl.remove();

            if (data.success) {
                appendAIMessage(data);
                if (data.parsed) {
                    chatHistory.push({ role: 'assistant', content: JSON.stringify(data.parsed) });
                } else if (data.explanation) {
                    chatHistory.push({ role: 'assistant', content: data.explanation });
                }
            } else {
                appendErrorMessage(data.error || 'Something went wrong. Please try again.');
            }
        } catch (err) {
            typingEl.remove();
            appendErrorMessage('Network error. Please check your connection and try again.');
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

    function appendTypingIndicator() {
        const row = createElement('div', 'message-row ai');
        row.id = 'typing-row';

        row.innerHTML = `
            <div class="typing-indicator">
                <div class="typing-avatar">
                    <i data-lucide="bot"></i>
                </div>
                <div class="typing-dots">
                    <span class="typing-dot"></span>
                    <span class="typing-dot"></span>
                    <span class="typing-dot"></span>
                </div>
            </div>
        `;

        messagesInner.appendChild(row);
        if (window.lucide) lucide.createIcons();
        return row;
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

        // Dark basemap on both
        const basemapUrl = 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png';
        const basemapOpts = { subdomains: 'abcd', maxZoom: 19 };
        L.tileLayer(basemapUrl, basemapOpts).addTo(beforeMap);
        L.tileLayer(basemapUrl, basemapOpts).addTo(afterMap);

        // ── Before Map Layers ──
        if (config.before_tiles) {
            L.tileLayer(config.before_tiles, { maxZoom: 19, opacity: 0.9 }).addTo(beforeMap);
        }
        const beforeOverlays = {};
        if (config.land_cover_before_tiles) {
            beforeOverlays['Land Cover'] = L.tileLayer(config.land_cover_before_tiles, { maxZoom: 19, opacity: 0.8 });
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
            const changeMask = L.tileLayer(config.change_mask_tiles, { maxZoom: 19, opacity: 0.7 });
            afterOverlays['Change Mask'] = changeMask;
            changeMask.addTo(afterMap);
        }
        if (config.land_cover_after_tiles) {
            afterOverlays['Land Cover'] = L.tileLayer(config.land_cover_after_tiles, { maxZoom: 19, opacity: 0.8 });
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
        // Split on double-newline for paragraphs, otherwise single block
        const paragraphs = text.split(/\n\n+/);
        paragraphs.forEach(function (para) {
            const p = document.createElement('p');
            p.textContent = para.trim();
            section.appendChild(p);
        });
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
