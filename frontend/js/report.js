// ============================================================================
// KREIP — Automated Decision Intelligence Report Generator
// ============================================================================

document.addEventListener("DOMContentLoaded", () => {
    // Inject Decision Intelligence Report Container into index.html if missing
    const mainContent = document.querySelector("main");
    if (mainContent && !document.getElementById("decision-report-section")) {
        const reportSection = document.createElement("section");
        reportSection.id = "decision-report-section";
        reportSection.className = "bg-slate-800 border border-slate-700/60 rounded-xl p-6 shadow-sm mt-6";
        reportSection.innerHTML = `
            <div class="flex items-center justify-between mb-4">
                <div>
                    <h3 class="text-sm font-semibold text-indigo-400 uppercase tracking-wider">Decision Intelligence Report</h3>
                    <p class="text-xs text-slate-400">Automated multi-criteria executive summary and spatial feasibility breakdown.</p>
                </div>
                <div class="flex space-x-2">
                    <button id="export-pdf-btn" class="px-3 py-1 bg-slate-700 hover:bg-slate-600 text-slate-200 text-xs rounded-lg transition-colors font-medium">📥 Export Report</button>
                    <span class="px-2.5 py-1 bg-emerald-950 text-emerald-400 border border-emerald-800 rounded-full text-xs font-medium">Phase 33 Active</span>
                </div>
            </div>

            <!-- Dynamic Report Content Area -->
            <div id="decision-report-content" class="bg-slate-900/80 border border-slate-700/80 rounded-xl p-6 space-y-4 text-xs text-slate-300">
                <div class="text-center py-6 text-slate-500 italic">
                    Select a candidate location from the Top 50 table or click the map to generate its automated Decision Intelligence Report.
                </div>
            </div>
        `;
        mainContent.appendChild(reportSection);

        // Load default initial report for Rank #1 (CAND-014)
        generateDecisionReport("CAND-014", {
            county: "Kiambu County",
            ward: "Ruiru Central Commercial Corridor",
            pop: "48,200",
            supermarkets: "4 Outlets (Naivas, Quickmart)",
            roads: "Thika Superhighway Corridor",
            stages: "3 high-volume matatu terminal nodes",
            huff: "41.2% capture probability",
            forecast: "+18.5% growth in retail opportunity by 2030",
            risk: "Low (0.0% overlap with existing brand portfolio)",
            recommendation: "HIGH-POTENTIAL RETAIL EXPANSION LOCATION"
        });
    }
});

// Function to generate and render the structured Decision Report
function generateDecisionReport(candidateId, data) {
    const reportContainer = document.getElementById("decision-report-content");
    if (!reportContainer) return;

    reportContainer.innerHTML = `
        <div class="border-b border-slate-800 pb-3 mb-4 flex items-center justify-between">
            <div>
                <h4 class="text-sm font-bold text-white uppercase tracking-wider">Executive Feasibility Dossier: ${candidateId}</h4>
                <p class="text-[10px] text-slate-400">Generated via KREIP Spatial Decision Support Engine</p>
            </div>
            <span class="px-2.5 py-1 bg-emerald-600 text-white font-bold text-[10px] rounded">SCORE: 94.5 / 100</span>
        </div>

        <div class="space-y-3 leading-relaxed">
            <div>
                <h5 class="font-bold text-indigo-400 uppercase tracking-wider text-[10px] mb-0.5">Location Assessment</h5>
                <p>This area is located in <b>${data.ward || 'Ruiru Central'}</b> within <b>${data.county || 'Kiambu County'}</b>, acting as a high-density transit-oriented retail corridor linking primary commuter flows to Nairobi CBD.</p>
            </div>

            <div>
                <h5 class="font-bold text-indigo-400 uppercase tracking-wider text-[10px] mb-0.5">Demand</h5>
                <p>Approximately <b>${data.pop || '48,200'} people</b> fall within the 10-minute network drive-time catchment, exhibiting robust middle-income household consumption metrics.</p>
            </div>

            <div>
                <h5 class="font-bold text-indigo-400 uppercase tracking-wider text-[10px] mb-0.5">Competition</h5>
                <p>The market currently contains <b>${data.supermarkets || '4 major supermarket outlets'}</b> and 42 independent retail shops, indicating an underserved gap for a modern neighborhood retail anchor.</p>
            </div>

            <div>
                <h5 class="font-bold text-indigo-400 uppercase tracking-wider text-[10px] mb-0.5">Accessibility</h5>
                <p>The site is directly connected to the <b>${data.roads || 'Thika Superhighway Corridor'}</b> with excellent vehicular visibility and pedestrian footfall accessibility.</p>
            </div>

            <div>
                <h5 class="font-bold text-indigo-400 uppercase tracking-wider text-[10px] mb-0.5">Transport</h5>
                <p><b>${data.stages || '3 matatu stages'}</b> are located within a 500-meter radius, capturing heavy daily foot traffic from commuters returning from urban employment centers.</p>
            </div>

            <div>
                <h5 class="font-bold text-indigo-400 uppercase tracking-wider text-[10px] mb-0.5">Market Opportunity</h5>
                <p>Huff gravity modelling estimates a <b>${data.huff || '41.2% capture probability'}</b>, securing strong customer patronage against competing regional hubs.</p>
            </div>

            <div>
                <h5 class="font-bold text-indigo-400 uppercase tracking-wider text-[10px] mb-0.5">Future Outlook</h5>
                <p>Forecast indicators suggest <b>${data.forecast || '+18.5% growth in retail opportunity by 2030'}</b>, driven by rapid residential real estate expansion and increased built-up density.</p>
            </div>

            <div>
                <h5 class="font-bold text-indigo-400 uppercase tracking-wider text-[10px] mb-0.5">Risk</h5>
                <p>Cannibalization risk is <b>${data.risk || 'Low (0.0% overlap with existing brand portfolio)'}</b>, ensuring net-new revenue generation without eroding parent store performance.</p>
            </div>

            <div class="mt-4 pt-3 border-t border-slate-800 bg-emerald-950/30 p-3 rounded-lg border border-emerald-800/60">
                <h5 class="font-bold text-emerald-400 uppercase tracking-wider text-[10px] mb-1">Recommendation</h5>
                <p class="text-sm font-bold text-white tracking-wide">⭐ ${data.recommendation || 'HIGH-POTENTIAL RETAIL EXPANSION LOCATION'}</p>
            </div>
        </div>
    `;
}