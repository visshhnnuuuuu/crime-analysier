# 🎨 apps/web — Frontend Application (Next.js)

This is the Next.js frontend for the **Criminal Agent Platform**. It acts as the **Interface Layer** for investigators, analysts, supervisors, and policymakers.

---

## 🛠️ Tech Stack & Visual Assets

* **Core Framework**: React & Next.js (App Router, Tailwind CSS, TypeScript).
* **Data Visualization**: Recharts / D3.js for dashboards.
* **Network Graphs**: Cytoscape.js for interactive suspect network visualization.
* **Geospatial Maps**: Leaflet / Mapbox GL for interactive crime hotspot density maps.
* **State Management**: Zustand for global chat sessions and filter settings.

---

## 📁 Directory Structure

```
apps/web/
├── app/
│   ├── layout.tsx              # Root HTML structure and font setup
│   ├── page.tsx                # Landing dashboard entry
│   ├── login/                  # Role-based Keycloak authentication portal
│   ├── chat/                   # Natural language conversational search (voice + text)
│   ├── dashboard/              # Aggregated trends, demographic insights, and metrics
│   ├── network/                # Inter-accused link and node visualization viewer
│   ├── fir/                    # Detailed FIR lookup and timelines
│   └── admin/                  # System overrides, governance logs, and settings
├── components/
│   ├── chat/                   # ChatInterface, MessageBubble, VoiceInput modules
│   ├── network/                # Cytoscape Graph wrapper, NodeDetail sidecards
│   ├── map/                    # HotspotMap canvas, TimeSlider controllers
│   └── common/                 # Reusable buttons, modals, and RoleGuard structures
├── hooks/                      # Custom React hooks (e.g. useChatSession, useMapLayers)
├── lib/                        # Client API calls, Bhashini translation helpers, constants
├── stores/                     # Zustand stores for state persistence
├── styles/                     # Tailwind classes and custom theme tokens
└── types/                      # TypeScript definitions (FIR, Person, AuditLog schemas)
```

---

## 🚀 Running the App

Run the development server from this folder (or from the root using workspaces):
```bash
# From root directory:
npm run dev --workspace=web

# Or from apps/web:
npm run dev
```

The app will start on port `3000`. Open [http://localhost:3000](http://localhost:3000) to view it.
