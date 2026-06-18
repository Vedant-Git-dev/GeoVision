document.addEventListener('DOMContentLoaded', () => {
    // Initialize sleek, animated date pickers
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
            if (result.success && result.map_url) {
                iframe.src = result.map_url;
                iframe.onload = () => {
                    mapOverlay.classList.remove('active');
                    btnGenerate.classList.remove('loading');
                    btnGenerate.disabled = false;
                };
            } else {
                alert("Error generating map: " + (result.error || "Unknown error"));
                mapOverlay.classList.remove('active');
                btnGenerate.classList.remove('loading');
                btnGenerate.disabled = false;
            }
        } catch (error) {
            console.error("Failed to fetch map:", error);
            // Fallback if not running through flask
            alert("Could not connect to the backend server.\n\nMake sure you have started the application using 'python app.py' instead of just opening the HTML file directly.");
            mapOverlay.classList.remove('active');
            btnGenerate.classList.remove('loading');
            btnGenerate.disabled = false;
        }
    });
});
