// ============================================================================
// KREIP — Interactive Leaflet Map & Spatial Layer Integration
// ============================================================================

const mapContainer = document.getElementById('map');
if (mapContainer) {
    // Initialize Leaflet Map centered on Nairobi Metropolitan Region and expose globally
    window.kreipMap = L.map('map', {
        zoomControl: false,
        attributionControl: true
    }).setView([-1.2921, 36.8219], 10);
    
    const map = window.kreipMap;

    // Add Zoom Control to Top-Right
    L.control.zoom({ position: 'topright' }).addTo(map);

    // Dark Basemap Tiles
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        maxZoom: 19,
        subdomains: 'abcd',
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
    }).addTo(map);

    // Layer Groups for Toggle Control
    const layerGroups = {
        population: L.layerGroup(),
        lulc: L.layerGroup(),
        boundaries: L.layerGroup(),
        supermarkets: L.layerGroup(),
        shops: L.layerGroup(),
        wholesalers: L.layerGroup(),
        malls: L.layerGroup(),
        markets: L.layerGroup(),
        roads: L.layerGroup(),
        transport: L.layerGroup(),
        congestion: L.layerGroup(),
        huff: L.layerGroup(),
        marketGap: L.layerGroup(),
        top50: L.layerGroup()
    };

    // Register Layer Controls
    const overlayMaps = {
        "2020 Population Baseline": layerGroups.population,
        "2025 LULC Classification": layerGroups.lulc,
        "Administrative Boundaries": layerGroups.boundaries,
        "Supermarkets": layerGroups.supermarkets,
        "Retail Shops": layerGroups.shops,
        "Wholesalers": layerGroups.wholesalers,
        "Malls & Shopping Centres": layerGroups.malls,
        "Open-Air Markets": layerGroups.markets,
        "Road Network": layerGroups.roads,
        "Matatu Stages & Terminals": layerGroups.transport,
        "High-Activity Business Zones": layerGroups.congestion,
        "Huff Market Influence": layerGroups.huff,
        "Market Gap / Underserved Areas": layerGroups.marketGap,
        "Top 50 Expansion Sites": layerGroups.top50
    };

    const layerControl = L.control.layers(null, overlayMaps, { collapsed: false, position: 'topright' }).addTo(map);

    // ============================================================================
    // Dynamic Multi-Layer Legends Control
    // ============================================================================
    const legendContainer = L.control({ position: 'bottomright' });

    legendContainer.onAdd = function () {
        const div = L.DomUtil.create('div', 'info legend bg-slate-900/90 p-3 rounded-lg border border-slate-700/80 text-slate-100 text-xs shadow-xl');
        div.id = 'dynamic-legend-content';
        updateLegendContent(div);
        return div;
    };
    legendContainer.addTo(map);

    function updateLegendContent(divElement) {
        const activeLegends = [];

        if (map.hasLayer(layerGroups.population)) {
            activeLegends.push(`
                <div class="mb-3">
                    <p class="font-bold text-indigo-400 mb-1 uppercase tracking-wider text-[10px]">2020 Population Baseline</p>
                    <div class="flex items-center gap-2 mb-1"><span class="w-3 h-3 rounded-sm bg-blue-200"></span> Low Density (0 - 46)</div>
                    <div class="flex items-center gap-2 mb-1"><span class="w-3 h-3 rounded-sm bg-blue-500"></span> Medium Density (46 - 397)</div>
                    <div class="flex items-center gap-2 mb-1"><span class="w-3 h-3 rounded-sm bg-yellow-400"></span> High Density (397 - 1,218)</div>
                    <div class="flex items-center gap-2"><span class="w-3 h-3 rounded-sm bg-red-600"></span> Core Urban Concentration (1,218+)</div>
                </div>
            `);
        }

        if (map.hasLayer(layerGroups.lulc)) {
            activeLegends.push(`
                <div class="mb-3">
                    <p class="font-bold text-emerald-400 mb-1 uppercase tracking-wider text-[10px]">2025 LULC Classification</p>
                    <div class="flex items-center gap-2 mb-1"><span class="w-3 h-3 rounded-sm bg-emerald-600/70"></span> Built-up / Urban Fabric</div>
                    <div class="flex items-center gap-2 mb-1"><span class="w-3 h-3 rounded-sm bg-green-500/70"></span> Vegetation / Agriculture</div>
                    <div class="flex items-center gap-2"><span class="w-3 h-3 rounded-sm bg-amber-600/70"></span> Barren / Open Land</div>
                </div>
            `);
        }

        if (map.hasLayer(layerGroups.supermarkets) || map.hasLayer(layerGroups.shops) || map.hasLayer(layerGroups.transport)) {
            activeLegends.push(`
                <div class="mb-3">
                    <p class="font-bold text-amber-400 mb-1 uppercase tracking-wider text-[10px]">Retail & Mobility Ecosystem</p>
                    <div class="flex items-center gap-2 mb-1"><span class="w-2.5 h-2.5 rounded-full bg-red-500"></span> Supermarket Outlets</div>
                    <div class="flex items-center gap-2 mb-1"><span class="w-2.5 h-2.5 rounded-full bg-orange-500"></span> Independent Retail Shops</div>
                    <div class="flex items-center gap-2 mb-1"><span class="w-2.5 h-2.5 rounded-full bg-cyan-400"></span> Matatu Transit Stages</div>
                    <div class="flex items-center gap-2"><span class="w-2.5 h-2.5 rounded-full bg-emerald-400"></span> Top 50 Opportunity Sites</div>
                </div>
            `);
        }

        if (activeLegends.length === 0) {
            divElement.innerHTML = `<p class="text-slate-400 italic">Toggle map layers above to view legends.</p>`;
        } else {
            divElement.innerHTML = activeLegends.join('<hr class="border-slate-700 my-2">');
        }
    }

    map.on('overlayadd overlayremove', () => {
        const legendDiv = document.getElementById('dynamic-legend-content');
        if (legendDiv) updateLegendContent(legendDiv);
    });

    // Robust API Fetch & GeoJSON Loader with Geometry Validation Filter
    async function loadMapLayer(endpoint, layerGroup, styleOptions, popupCallback, filterFn = null) {
        try {
            const response = await fetch(`http://127.0.0.1:8000/api/${endpoint}`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const data = await response.json();
            
            if (data && data.type === "FeatureCollection" && data.features) {
                L.geoJSON(data, {
                    filter: (feature) => {
                        // Ensure features have valid geometry arrays before rendering
                        if (!feature.geometry || !feature.geometry.coordinates) return false;
                        // Run custom filter if provided
                        if (filterFn && !filterFn(feature)) return false;
                        return true;
                    },
                    style: styleOptions,
                    pointToLayer: (feature, latlng) => {
                        return styleOptions.pointType === "circle" 
                            ? L.circleMarker(latlng, styleOptions) 
                            : L.marker(latlng);
                    },
                    onEachFeature: (feature, layer) => {
                        if (popupCallback) {
                            layer.bindPopup(popupCallback(feature.properties));
                        }
                    }
                }).addTo(layerGroup);
            }
        } catch (error) {
            console.warn(`Could not load endpoint /api/${endpoint}:`, error);
        }
    }

    // 1. Load 2020 Population Baseline Vector Grid (Clean Heatmap Stylized)
    async function loadPopulationBaseline() {
        try {
            const response = await fetch('http://127.0.0.1:8000/api/population');
            if (!response.ok) throw new Error('Failed to fetch population grid');
            const data = await response.json();

            const popLayer = L.geoJSON(data, {
                style: function(feature) {
                    let val = feature.properties.population || feature.properties.pop || 0;
                    let color = '#3b82f6';

                    if (val > 1218.951) color = '#dc2626';      // Red (Dense)
                    else if (val > 397.115) color = '#facc15'; // Yellow (Moderate-High)
                    else if (val > 46.219) color = '#38bdf8';  // Cyan (Moderate)
                    else color = '#1e3a8a';                    // Deep Blue (Low)

                    return {
                        fillColor: color,
                        weight: 0,
                        stroke: false,
                        fillOpacity: 0.45
                    };
                },
                onEachFeature: (feature, layer) => {
                    let val = feature.properties.population || feature.properties.pop || 0;
                    layer.bindPopup(`<b>2020 Population Baseline</b><br>Cell Density: ${val.toFixed(1)} residents`);
                }
            });

            layerGroups.population.addLayer(popLayer);
        } catch (error) {
            console.warn("Could not load 2020 population baseline:", error);
        }
    }

    // 2. Load 2025 LULC Classification Features
    async function loadLULCLayer() {
        try {
            const response = await fetch('http://127.0.0.1:8000/api/lulc');
            if (!response.ok) throw new Error('Failed to fetch LULC features');
            const data = await response.json();

            const lulcLayer = L.geoJSON(data, {
                style: function(feature) {
                    let code = feature.properties.class || feature.properties.gridcode || 1;
                    let color = code === 2 ? '#059669' : '#10b981'; // Builtup vs Greenery
                    return {
                        color: color,
                        weight: 0.5,
                        fillColor: color,
                        fillOpacity: 0.35
                    };
                },
                onEachFeature: (feature, layer) => {
                    layer.bindPopup(`<b>2025 LULC Classification</b><br>Land Cover Type: ${feature.properties.class || 'Urban / Built-up Fabric'}`);
                }
            });

            layerGroups.lulc.addLayer(lulcLayer);
        } catch (error) {
            console.warn("Could not load 2025 LULC layer:", error);
        }
    }

    // Initialize & Load All Spatial Layers
    function initializeMapLayers() {
        // Core Baselines
        loadPopulationBaseline();
        loadLULCLayer();

        // Administrative Boundaries
        loadMapLayer('boundaries', layerGroups.boundaries, { 
            color: '#818cf8', weight: 1.5, opacity: 0.8, fillOpacity: 0.02 
        }, p => `<b>Administrative Ward:</b> ${p.sub_county || p.NAME_1 || p.name || 'Boundary Area'}`);

        // Retail & Commercial Ecosystem
        const retailCategories = [
            { key: 'supermarkets', group: layerGroups.supermarkets, color: '#ef4444', filter: p => (p.category || p.amenity || '').toLowerCase().includes('supermarket') },
            { key: 'shops', group: layerGroups.shops, color: '#f97316', filter: p => (p.category || p.amenity || '').toLowerCase().includes('shop') || (p.shop || '') !== '' },
            { key: 'wholesalers', group: layerGroups.wholesalers, color: '#eab308', filter: p => (p.category || p.amenity || '').toLowerCase().includes('wholesale') },
            { key: 'malls', group: layerGroups.malls, color: '#ec4899', filter: p => (p.category || p.amenity || '').toLowerCase().includes('mall') || (p.amenity || '') === 'mall' },
            { key: 'markets', group: layerGroups.markets, color: '#8b5cf6', filter: p => (p.category || p.amenity || '').toLowerCase().includes('market') }
        ];

        retailCategories.forEach(cat => {
            loadMapLayer('retail', cat.group, {
                radius: 5, fillColor: cat.color, color: '#000', weight: 1, fillOpacity: 0.85, pointType: 'circle'
            }, p => `<b>${cat.key.toUpperCase()}:</b> ${p.name || p.amenity || 'Commercial Outlet'}`);
        });

        // Infrastructure & Mobility (Road Network kept disabled on startup to optimize performance, toggleable via layer control)
        loadMapLayer('roads', layerGroups.roads, { 
            color: '#475569',      // Clean slate road color
            weight: 1.2,           // Crisp stroke width
            opacity: 0.85,         // High visibility
            dashArray: null        // Forces completely solid lines (removes dashes)
        }, p => `<b>Road Corridor:</b> ${p.highway || p.name || 'Primary Access Road'}`);

        loadMapLayer('transport', layerGroups.transport, { 
            radius: 5, fillColor: '#06b6d4', color: '#fff', weight: 1, fillOpacity: 0.9, pointType: 'circle' 
        }, p => `<b>Matatu Terminal / Stage:</b> ${p.name || p.station || 'Transit Node'}`);

        loadMapLayer('forecast', layerGroups.congestion, { 
            color: '#a855f7', weight: 1, fillColor: '#a855f7', fillOpacity: 0.3 
        }, p => `<b>High-Activity Business Zone:</b> ${p.growth_rate || 'Commercial Hub'}`);

        loadMapLayer('market-gap', layerGroups.marketGap, { 
            color: '#f59e0b', weight: 1, fillColor: '#f59e0b', fillOpacity: 0.3 
        }, p => `<b>Market Gap Index:</b> ${p.gap_score || 'Underserved Retail Pocket'}`);

        // Top 50 Expansion Candidate Sites
        loadMapLayer('candidates/top50', layerGroups.top50, { 
            radius: 8, fillColor: '#10b981', color: '#fff', weight: 2, fillOpacity: 0.95, pointType: 'circle' 
        }, p => `<b>Rank #${p.rank || 'N/A'} Expansion Site:</b> ${p.candidate_id || p.ward || 'Opportunity Location'}`);

        // Set Default Visible Layers (Excluding heavy road network from default startup render)
        layerGroups.boundaries.addTo(map);
        layerGroups.supermarkets.addTo(map);
        layerGroups.transport.addTo(map);
        layerGroups.top50.addTo(map);
    }

    // Initialize map and adjust container layout
    initializeMapLayers();
    setTimeout(() => {
        map.invalidateSize();
    }, 250);
}