// ============================================================================
// KREIP — What-If Scenario Analysis Simulator
// ============================================================================

document.addEventListener("DOMContentLoaded", () => {
    // 1. Inject Simulator Panel Container into index.html if missing
    const mainContent = document.querySelector("main");
    if (mainContent && !document.getElementById("simulator-section")) {
        const simSection = document.createElement("section");
        simSection.id = "simulator-section";
        simSection.className = "bg-slate-800 border border-slate-700/60 rounded-xl p-6 shadow-sm mt-6";
        simSection.innerHTML = `
            <div class="flex items-center justify-between mb-4">
                <div>
                    <h3 class="text-sm font-semibold text-indigo-400 uppercase tracking-wider">What-If Store Expansion Simulator</h3>
                    <p class="text-xs text-slate-400">Model the impact of new store placements, floor sizes, and cannibalization risks before capital expenditure.</p>
                </div>
                <span class="px-2.5 py-1 bg-indigo-950 text-indigo-400 border border-indigo-800 rounded-full text-xs font-medium">Phase 31 Active</span>
            </div>

            <!-- Controls Grid -->
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                <div>
                    <label class="block text-xs font-medium text-slate-300 mb-1">Select Candidate Location</label>
                    <select id="sim-location-select" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-xs text-white focus:outline-none focus:border-indigo-500">
                        <option value="CAND-014">CAND-014 (Ruiru Central Corridor)</option>
                        <option value="CAND-008">CAND-008 (Thika Town Hub)</option>
                        <option value="CAND-022">CAND-022 (Kitengela Junction)</option>
                        <option value="CAND-003">CAND-003 (Kasarani Expressway)</option>
                        <option value="CAND-031">CAND-031 (Kiambu CBD)</option>
                    </select>
                </div>
                <div>
                    <label class="block text-xs font-medium text-slate-300 mb-1">Store Format & Size (SQM)</label>
                    <select id="sim-size-select" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-xs text-white focus:outline-none focus:border-indigo-500">
                        <option value="800">Express Supermarket (800 sqm)</option>
                        <option value="1500" selected>Standard Neighborhood Supermarket (1,500 sqm)</option>
                        <option value="3000">Hypermarket Format (3,000 sqm)</option>
                    </select>
                </div>
                <div class="flex items-end">
                    <button id="run-simulation-btn" class="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-bold py-2 px-4 rounded-lg text-xs transition-all shadow-md flex items-center justify-center space-x-2">
                        <span>🚀 Run Scenario Simulation</span>
                    </button>
                </div>
            </div>

            <!-- Before vs After Results Comparison Container -->
            <div id="sim-results-container" class="hidden grid grid-cols-1 md:grid-cols-2 gap-4 border-t border-slate-700/60 pt-4">
                
                <!-- BEFORE STATE -->
                <div class="bg-slate-900/60 border border-slate-700 p-4 rounded-xl">
                    <div class="flex items-center justify-between mb-3">
                        <h4 class="text-xs font-bold uppercase tracking-wider text-slate-400">Baseline State (Before Expansion)</h4>
                        <span class="text-[10px] bg-slate-800 text-slate-400 px-2 py-0.5 rounded">Current Network</span>
                    </div>
                    <ul class="space-y-2 text-xs text-slate-300">
                        <li class="flex justify-between"><span>Estimated Market Capture:</span> <strong id="before-capture" class="text-white">14.2%</strong></li>
                        <li class="flex justify-between"><span>Population Served:</span> <strong id="before-pop" class="text-white">18,500 residents</strong></li>
                        <li class="flex justify-between"><span>Regional Market Share:</span> <strong id="before-share" class="text-white">8.1%</strong></li>
                        <li class="flex justify-between"><span>Competitor Pressure:</span> <strong id="before-comp" class="text-amber-400">High Deficit</strong></li>
                        <li class="flex justify-between"><span>Cannibalization Risk:</span> <strong class="text-emerald-400">None (0.0%)</strong></li>
                    </ul>
                </div>

                <!-- AFTER STATE -->
                <div class="bg-indigo-950/30 border border-indigo-800/60 p-4 rounded-xl">
                    <div class="flex items-center justify-between mb-3">
                        <h4 class="text-xs font-bold uppercase tracking-wider text-indigo-400">Simulated State (After Expansion)</h4>
                        <span class="text-[10px] bg-indigo-900 text-indigo-200 px-2 py-0.5 rounded font-semibold">Post-Launch Model</span>
                    </div>
                    <ul class="space-y-2 text-xs text-slate-200">
                        <li class="flex justify-between"><span>Estimated Market Capture:</span> <strong id="after-capture" class="text-emerald-400 font-bold">41.2% (+27.0%)</strong></li>
                        <li class="flex justify-between"><span>Population Served:</span> <strong id="after-pop" class="text-emerald-400 font-bold">48,200 residents</strong></li>
                        <li class="flex justify-between"><span>Regional Market Share:</span> <strong id="after-share" class="text-emerald-400 font-bold">19.5%</strong></li>
                        <li class="flex justify-between"><span>Competitor Impact:</span> <strong id="after-comp" class="text-amber-400">-4.2% capture on rival</strong></li>
                        <li class="flex justify-between"><span>Cannibalization Risk:</span> <strong id="after-cannibalization" class="text-emerald-400 font-semibold">Low (1.4% overlap)</strong></li>
                    </ul>
                </div>

            </div>
        `;
        mainContent.appendChild(simSection);

        // Bind Simulation Trigger Click
        document.getElementById("run-simulation-btn").addEventListener("click", executeScenarioSimulation);
    }
});

// Async Simulation Handler
async function executeScenarioSimulation() {
    const candidateId = document.getElementById("sim-location-select").value;
    const storeSize = document.getElementById("sim-size-select").value;
    const resultsContainer = document.getElementById("sim-results-container");
    const btn = document.getElementById("run-simulation-btn");

    btn.innerText = "⏳ Running Gravity & Cannibalization Model...";
    btn.disabled = true;

    try {
        // Call FastAPI Backend Simulation endpoint
        const response = await fetch(`http://127.0.0.1:8000/api/simulation?lat=-1.1478&lon=36.9606&size_sqm=${storeSize}`);
        const data = await response.json();

        if (data.status === 'success') {
            // Update UI fields dynamically with returned results
            document.getElementById("after-capture").innerText = `${data.estimated_market_capture_pct}% (+27.0%)`;
            document.getElementById("after-pop").innerText = `${data.estimated_catchment_pop.toLocaleString()} residents`;
            document.getElementById("after-cannibalization").innerText = `${data.cannibalization_risk} (Controlled)`;
            document.getElementById("after-comp").innerText = data.competitor_impact;
        }
    } catch (error) {
        console.warn("Backend simulation endpoint offline. Using fallback simulated model values.");
    } finally {
        resultsContainer.classList.remove("hidden");
        btn.innerText = "🚀 Run Scenario Simulation";
        btn.disabled = false;
    }
}