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

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        btnGenerate.classList.add('loading');
        mapOverlay.classList.add('active');
        btnGenerate.disabled = true;
        answerBox.textContent = ''; // clear previous answer

        const data = {
            location: document.getElementById('location').value,
            before_date: document.getElementById('before_date').value,
            after_date: document.getElementById('after_date').value,
            question: document.getElementById('question').value.trim()
        };

        try {
            const response = await fetch('/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            const result = await response.json();
            console.log('Generate result:', result);

            if (result.success && result.map_url) {
                // Store config FIRST, then navigate iframe
                if (result.config) {
                    // Add timestamp to ensure iframe reads fresh data
                    result.config._timestamp = Date.now();
                    localStorage.setItem('geovision_map_config', JSON.stringify(result.config));
                    console.log('Config stored in localStorage, timestamp:', result.config._timestamp);
                }

                // Reset iframe src to trigger reload with new localStorage
                iframe.src = 'about:blank';
                setTimeout(() => {
                    iframe.src = result.map_url;
                }, 50);

                // Display explanation if present
                if (result.explanation) {
                    answerBox.textContent = result.explanation;
                    answerBox.style.color = '#333';
                }

                iframe.onload = () => {
                    console.log('Iframe loaded');
                    mapOverlay.classList.remove('active');
                    btnGenerate.classList.remove('loading');
                    btnGenerate.disabled = false;
                };
            } else {
                answerBox.textContent = "Error: " + (result.error || "Unknown error");
                answerBox.style.color = '#c00';
                mapOverlay.classList.remove('active');
                btnGenerate.classList.remove('loading');
                btnGenerate.disabled = false;
            }
        } catch (error) {
            console.error("Failed:", error);
            answerBox.textContent = "Could not connect to the backend server.";
            answerBox.style.color = '#c00';
            mapOverlay.classList.remove('active');
            btnGenerate.classList.remove('loading');
            btnGenerate.disabled = false;
        }
    });
});