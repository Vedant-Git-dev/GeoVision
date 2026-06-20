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

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        btnGenerate.classList.add('loading');
        mapOverlay.classList.add('active');
        btnGenerate.disabled = true;

        const data = {
            location: document.getElementById('location').value,
            before_date: document.getElementById('before_date').value,
            after_date: document.getElementById('after_date').value
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

                iframe.onload = () => {
                    console.log('Iframe loaded');
                    mapOverlay.classList.remove('active');
                    btnGenerate.classList.remove('loading');
                    btnGenerate.disabled = false;
                };
            } else {
                alert("Error: " + (result.error || "Unknown error"));
                mapOverlay.classList.remove('active');
                btnGenerate.classList.remove('loading');
                btnGenerate.disabled = false;
            }
        } catch (error) {
            console.error("Failed:", error);
            alert("Could not connect to the backend server.");
            mapOverlay.classList.remove('active');
            btnGenerate.classList.remove('loading');
            btnGenerate.disabled = false;
        }
    });
});