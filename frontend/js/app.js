// ============================================================================
// KREIP — Kenya Retail Expansion Intelligence Platform (Master Application Entry)
// ============================================================================

// Configuration for API base URL with fallback to local development
const API_BASE_URL = window.KREIP_CONFIG?.API_BASE_URL || "http://127.0.0.1:8000";

document.addEventListener("DOMContentLoaded", () => {
    console.log("🟢 KREIP Client Platform Initialized Successfully.");

    // Load Top 50 Candidate Locations into the Intelligence Panel
    loadCandidateRankings();

    // Hook global event listener to synchronize Top 50 selection with Simulator & Report
    document.addEventListener("candidateSelected", (event) => {
        const { candidateId, ward, county, population, score, lat, lon, rawProperties } = event.detail;
        
        // 1. Update Simulator Location Dropdown if present
        const simSelect = document.getElementById("sim-location-select");
        if (simSelect) {
            simSelect.value = candidateId;
        }

        // 2. Fly map view to selected candidate location if map instance exists globally
        if (window.kreipMap && lat && lon) {
            window.kreipMap.flyTo([lat, lon], 14, { animate: true, duration: 1.5 });
        }

        // 3. Generate Automated Decision Intelligence Report using strictly true backend properties
        if (typeof generateDecisionReport === 'function') {
            const props = rawProperties || {};
            
            generateDecisionReport(candidateId, {
                county: county ?? "Not Available",
                ward: ward ?? "Not Available",
                pop: population !== null && population !== undefined ? `${Number(population).toLocaleString()} people` : "Not Available",
                supermarkets: props.supermarket_count !== undefined ? `${props.supermarket_count} Outlets` : "Not Available",
                roads: props.road_corridor ?? "Not Available",
                stages: props.transit_stages_count !== undefined ? `${props.transit_stages_count} transit nodes` : "Not Available",
                huff: props.market_share_gained_pct !== undefined ? `${Number(props.market_share_gained_pct).toFixed(1)}% estimated market share` : "Not Available",
                forecast: props.opportunity_delta_pct !== undefined ? `${Number(props.opportunity_delta_pct) >= 0 ? '+' : ''}${Number(props.opportunity_delta_pct).toFixed(1)}% growth by 2030` : "Not Available",
                risk: props.cannibalization_risk !== undefined ? `${props.cannibalization_risk}` : "Not Available",
                recommendation: props.recommendation_status ?? "CANDIDATE SITE REVIEW"
            });
        }
    });
});

// Fetch and render Top 50 Candidates in the Sidebar Panel with strict null-safety
async function loadCandidateRankings() {
    const container = document.getElementById("candidates-list");
    if (!container) return;

    try {
        const response = await fetch(`${API_BASE_URL}/api/candidates/top50`);
        if (!response.ok) throw new Error("Failed to load candidate rankings.");
        
        const data = await response.json();
        if (data && data.features && data.features.length > 0) {
            container.innerHTML = ""; // Clear placeholder

            data.features.forEach((feature, index) => {
                const props = feature.properties;
                const coords = feature.geometry ? feature.geometry.coordinates : [36.8219, -1.2921];
                const rank = props.rank ?? (index + 1);
                const candidateId = props.candidate_id ?? `SITE_${rank}`;
                
                // Strict fallback selection using nullish coalescing (avoiding falsy 0 traps)
                const score = 
                    props.market_gap_score ??
                    props.future_opportunity ??
                    props.current_opportunity ??
                    null;

                const scoreDisplay = score !== null ? Number(score).toFixed(1) : "N/A";
                const locationLabel = props.ward ?? props.county ?? props.locality ?? "Nairobi Metro Expansion Node";

                const card = document.createElement("div");
                card.className = "bg-slate-900/60 border border-slate-700/60 hover:border-indigo-500 rounded-lg p-3 cursor-pointer transition-all";
                card.innerHTML = `
                    <div class="flex items-center justify-between">
                        <span class="text-xs font-bold text-indigo-400">Rank #${rank} — ${candidateId}</span>
                        <span class="text-xs px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800">Score: ${scoreDisplay}</span>
                    </div>
                    <p class="text-[11px] text-slate-400 mt-1">${locationLabel}</p>
                `;

                card.addEventListener("click", () => {
                    const customEvent = new CustomEvent("candidateSelected", {
                        detail: {
                            candidateId: candidateId,
                            ward: props.ward ?? props.locality,
                            county: props.county,
                            population: props.population_captured ?? props.population ?? null,
                            score: score,
                            lat: coords[1], // GeoJSON format is [lon, lat]
                            lon: coords[0],
                            rawProperties: props
                        }
                    });
                    document.dispatchEvent(customEvent);
                });

                container.appendChild(card);
            });
        } else {
            container.innerHTML = `<div class="text-xs text-slate-400 text-center p-4">No candidate locations returned by API.</div>`;
        }
    } catch (error) {
        console.warn("Could not fetch candidate rankings list:", error);
        container.innerHTML = `<div class="text-xs text-rose-400 text-center p-4">Failed to load candidate sites from API. Check backend connection.</div>`;
    }
}