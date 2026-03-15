import { create } from "zustand";
import type { GraphData, Line, MapMarker, Station } from "@/lib/types";
import { v4 as uuid } from "uuid";

export type MainView = "map" | "graph" | "memory";
export type MobilePanel = "chat" | "main" | "detail";

interface AppState {
  // Session
  sessionId: string;

  // Selection
  selectedStation: Station | null;
  selectedLine: Line | null;

  // Map
  mapCenter: { lat: number; lon: number };
  mapZoom: number;
  mapMarkers: MapMarker[];
  routeCoordinates: [number, number][] | null;

  // Graph
  graphData: GraphData | null;

  // View
  mainView: MainView;
  mobilePanel: MobilePanel;

  // Actions
  setSelectedStation: (station: Station | null) => void;
  setSelectedLine: (line: Line | null) => void;
  panMapTo: (lat: number, lon: number, zoom?: number) => void;
  setMapMarkers: (markers: MapMarker[]) => void;
  addMapMarkers: (markers: MapMarker[]) => void;
  setRouteCoordinates: (coords: [number, number][] | null) => void;
  setGraphData: (data: GraphData | null) => void;
  setMainView: (view: MainView) => void;
  setMobilePanel: (panel: MobilePanel) => void;
  clearSelection: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  // Initial state
  sessionId: uuid(),
  selectedStation: null,
  selectedLine: null,
  mapCenter: { lat: 51.505, lon: -0.09 },
  mapZoom: 12,
  mapMarkers: [],
  routeCoordinates: null,
  graphData: null,
  mainView: "map",
  mobilePanel: "main",

  // Actions
  setSelectedStation: (station) =>
    set((state) => ({
      selectedStation: station,
      selectedLine: null,
      ...(station
        ? { mapCenter: { lat: station.lat, lon: station.lon }, mapZoom: 15 }
        : {}),
    })),

  setSelectedLine: (line) =>
    set({ selectedLine: line, selectedStation: null }),

  panMapTo: (lat, lon, zoom) =>
    set((state) => ({
      mapCenter: { lat, lon },
      ...(zoom !== undefined ? { mapZoom: zoom } : {}),
    })),

  setMapMarkers: (markers) => set({ mapMarkers: markers }),

  addMapMarkers: (markers) =>
    set((state) => ({
      mapMarkers: [...state.mapMarkers, ...markers],
    })),

  setRouteCoordinates: (coords) => set({ routeCoordinates: coords }),

  setGraphData: (data) => set({ graphData: data }),

  setMainView: (view) => set({ mainView: view }),

  setMobilePanel: (panel) => set({ mobilePanel: panel }),

  clearSelection: () =>
    set({
      selectedStation: null,
      selectedLine: null,
      mapMarkers: [],
      routeCoordinates: null,
      graphData: null,
    }),
}));
