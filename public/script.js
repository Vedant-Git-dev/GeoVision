document.addEventListener('DOMContentLoaded', () => {
    flatpickr("#before_date", {
        dateFormat: "Y-m-d",
        altInput: true,
        altFormat: "F j, Y",
        animate: true
    });

    flatpickr("#after_date", {
        dateFormat: "Y-m-d",
        altInput: true,
        altFormat: "F j, Y",
        animate: true
    });

    const form = document.getElementById('control-form');
    const btnGenerate = document.getElementById('generate-btn');
    const mapOverlay = document.getElementById('map-overlay');
    const iframe = document.getElementById('map-frame');
    const answerBox = document.getElementById('answer-box');

    // Progress panel elements
    const progressPanel = document.getElementById('progress-panel');
    const progressBar = document.getElementById('progress-bar-fill');
    const progressTitle = document.getElementById('progress-title');
    const progressDetail = document.getElementById('progress-detail');
    const progressStepLabel = document.getElementById('progress-step-label');

    const STEP_LABELS = {
        resolve_location: 'Resolving Location',
        fetch_aoi: 'Fetching Area of Interest',
        build_composite_before: 'Building Before Composite',
        build_composite_after: 'Building After Composite',
        detect_changes: 'Detecting Changes',
        compute_stats: 'Computing Statistics',
    };

    function resetProgress() {
        progressPanel.className = 'progress-panel';
        progressBar.style.width = '0%';
        progressTitle.textContent = 'Processing Data';
        progressDetail.textContent = 'Initializing…';
        progressStepLabel.textContent = 'Step 0 of 6';
    }

    function updateProgress(payload) {
        const pct = Math.round((payload.step_num / payload.total_steps) * 100);
        progressBar.style.width = pct + '%';
        progressTitle.textContent = STEP_LABELS[payload.step] || payload.step;
        progressDetail.textContent = payload.detail;
        progressStepLabel.textContent = `Step ${payload.step_num} of ${payload.total_steps}`;
    }

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        btnGenerate.classList.add('loading');
        mapOverlay.classList.add('active');
        btnGenerate.disabled = true;
        answerBox.textContent = '';
        resetProgress();

        const data = {
            location: document.getElementById('location').value,
            before_date: document.getElementById('before_date').value,
            after_date: document.getElementById('after_date').value,
            question: document.getElementById('question').value.trim()
        };

        try {
            const response = await fetch('/generate/stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
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
                buffer = parts.pop(); // keep incomplete tail

                for (const part of parts) {
                    let eventType = 'message';
                    let eventData = '';

                    for (const line of part.split('\n')) {
                        if (line.startsWith('event: ')) {
                            eventType = line.slice(7);
                        } else if (line.startsWith('data: ')) {
                            eventData = line.slice(6);
                        }
                    }

                    if (!eventData) continue;

                    try {
                        const payload = JSON.parse(eventData);

                        if (eventType === 'progress') {
                            updateProgress(payload);
                        } else if (eventType === 'result') {
                            result = payload;
                            progressBar.style.width = '100%';
                            progressPanel.classList.add('complete');
                            progressTitle.textContent = 'Complete';
                        } else if (eventType === 'error') {
                            throw new Error(payload.error || 'Pipeline failed');
                        }
                    } catch (parseErr) {
                        if (parseErr.message !== 'Pipeline failed' && !parseErr.message.includes('Pipeline')) {
                            console.warn('Failed to parse SSE event:', parseErr);
                        } else {
                            throw parseErr;
                        }
                    }
                }
            }

            if (result && result.success && result.map_url) {
                if (result.config) {
                    result.config._timestamp = Date.now();
                    localStorage.setItem('geovision_map_config', JSON.stringify(result.config));
                }

                iframe.src = 'about:blank';
                setTimeout(() => { iframe.src = result.map_url; }, 50);

                if (result.explanation) {
                    answerBox.textContent = result.explanation;
                    answerBox.style.color = '#333';
                }

                iframe.onload = () => {
                    mapOverlay.classList.remove('active');
                    btnGenerate.classList.remove('loading');
                    btnGenerate.disabled = false;
                };
            } else if (result && !result.success) {
                throw new Error(result.error || 'Unknown error');
            }
        } catch (error) {
            progressPanel.classList.add('error');
            progressTitle.textContent = 'Error';
            progressDetail.textContent = error.message;
            answerBox.textContent = 'Error: ' + error.message;
            answerBox.style.color = '#c00';
            setTimeout(() => {
                mapOverlay.classList.remove('active');
                btnGenerate.classList.remove('loading');
                btnGenerate.disabled = false;
            }, 3000);
        }
    });
});