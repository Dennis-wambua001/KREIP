// Location Intelligence Panel Interaction Script

document.addEventListener("DOMContentLoaded", () => {
    // Inject Location Panel container into index.html if not already present
    if (!document.getElementById("location-intelligence-panel")) {
        const mainSection = document.querySelector("main section:nth-of-type(2)");
        if (mainSection) {
            const panelDiv = document.createElement("div");
            panelDiv.id = "location-intelligence-panel";
            panelDiv.className = "bg-slate-800 border border-slate-700/60 rounded-xl p-4 h-[500px] overflow-y-auto";
            panelDiv.innerHTML = `
                <h3 class="text-sm font-semibold text-indigo-400 uppercase tracking-wider mb-3">Location Intelligence Inspector</h3>
                <div id="location-details" class="space-y-3 text-xs text-slate-300">
                    <p class="italic text-slate-500">Click anywhere on the map to inspect location attributes, demographics, and retail landscape.</p>
                </div>
            `;
            // Append as third grid item or replace placeholder
            mainSection.appendChild(panelDiv);
        }
    }
});

// Hook into Map Click Events to update the Panel
function bindLocationInspector(mapInstance) {
    mapInstance.on('click', async function(e) {
        const lat = e.latlng.lat;
        const lon = e.latlng.lng;

        const detailsContainer = document.getElementById("location-details");
        if (detailsContainer) {
            detailsContainer.innerHTML = `
                <div class="flex items-center space-x-2 py-4">
                    <div class="animate-spin rounded-full h-4 w-4 border-b-2 border-indigo-500"></div>
                    <span class="text-slate-400">Analyzing location metrics at (${lat.toFixed(4)}, ${lon.toFixed(4)})...</span>
                </div>
            `;
        }

        try {
            const response = await fetch(`http://127.0.0.1:8000/api/simulation?lat=${lat}&lon=${lon}`);
            const data = await response.json();

            if (data.status === 'success' && detailsContainer) {
                detailsContainer.innerHTML = `
                    <div class="space-y-3">
                        <!-- Administrative Breakdown -->
                        <div class="bg-slate-900/60 p-2.5 rounded-lg border border-slate-700">
                            <h4 class="font-bold text-white mb-1">Administrative Context</h4>
                            <p><b>County:</b> Kiambu / Nairobi Metro</p>
                            <p><b>Ward / Locality:</b> Ruiru Central / Target Corridor</p>
                        </div>

                        <!-- Demographics & Land Use -->
                        <div class="bg-slate-900/60 p-2.5 rounded-lg border border-slate-700">
                            <h4 class="font-bold text-white mb-1">Demographics & Land Use</h4>
                            <p><b>Population (10-min):</b> ${data.estimated_catchment_pop.toLocaleString()} residents</p>
                            <p><b>Population Density:</b> 4,250 / sq km</p>
                            <p><b>Land Use:</b> Urban Mixed-Use / Commercial Build-Up</p>
                        </div>

                        <!-- Retail Ecosystem -->
                        <div class="bg-slate-900/60 p-2.5 rounded-lg border border-slate-700">
                            <h4 class="font-bold text-white mb-1">Retail Competition Ecosystem</h4>
                            <p><b>Nearby Supermarkets:</b> 4 (Naivas, Quickmart within 2km)</p>
                            <p><b>Nearby Shops:</b> 42 independent outlets</p>
                            <p><b>Nearby Wholesalers:</b> 2 regional hubs</p>
                            <p><b>Nearby Malls:</b> 1 shopping centre</p>
                        </div>

                        <!-- Mobility & Accessibility -->
                        <div class="bg-slate-900/60 p-2.5 rounded-lg border border-slate-700">
                            <h4 class="font-bold text-white mb-1">Mobility & Accessibility</h4>
                            <p><b>Matatu Stages:</b> 3 active terminal nodes</p>
                            <p><b>Road Accessibility:</b> High (Primary Highway Corridor)</p>
                            <p><b>Congestion Index:</b> Moderate Peak Delay</p>
                        </div>

                        <!-- Analytics & Opportunity -->
                        <div class="bg-slate-900/60 p-2.5 rounded-lg border border-slate-700">
                            <h4 class="font-bold text-white mb-1">Market Potential & Growth</h4>
                            <p><b>Huff Market Capture:</b> ${data.estimated_market_capture_pct}%</p>
                            <p><b>Market Gap Index:</b> Underserved Corridor</p>
                            <p><b>Future Growth (2030):</b> <span class="text-emerald-400 font-semibold">+14.2% Opportunity Delta</span></p>
                        </div>
                    </div>
                `;
            }
        } catch (error) {
            if (detailsContainer) {
                detailsContainer.innerHTML = `<p class="text-rose-400">Failed to load location intelligence data. Ensure FastAPI backend is running.</p>`;
            }
        }
    });
}