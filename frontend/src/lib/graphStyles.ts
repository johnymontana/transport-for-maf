/**
 * TfL line colors and NVL graph styling.
 */

export const TFL_LINE_COLORS: Record<string, string> = {
  bakerloo: "#B36305",
  central: "#E32017",
  circle: "#FFD300",
  district: "#00782A",
  "hammersmith-city": "#F3A9BB",
  jubilee: "#A0A5A9",
  metropolitan: "#9B0056",
  northern: "#000000",
  piccadilly: "#003688",
  victoria: "#0098D4",
  "waterloo-city": "#95CDBA",
  elizabeth: "#6950A1",
  "london-overground": "#EE7C0E",
  dlr: "#00A4A7",
};

export const NODE_COLORS: Record<string, string> = {
  Station: "#DA7194",
  Line: "#003688",
  BikePoint: "#2F9E44",
  Zone: "#F79767",
  Disruption: "#E03131",
  // Memory node types
  Message: "#6366F1",
  Entity: "#2F9E44",
  Preference: "#F79767",
  ToolCall: "#D0BFFF",
  Conversation: "#6366F1",
};

export function getNodeColor(type: string, properties?: Record<string, unknown>): string {
  if (type === "Line" && properties?.color) {
    return properties.color as string;
  }
  return NODE_COLORS[type] || "#888888";
}

export function getNodeSize(type: string, properties?: Record<string, unknown>): number {
  if (type === "Station") {
    const zone = properties?.zone as string | undefined;
    if (zone) {
      const zoneNum = parseInt(zone, 10);
      if (!isNaN(zoneNum)) return Math.max(8, 20 - zoneNum * 2);
    }
    return 12;
  }
  if (type === "Line") return 16;
  if (type === "BikePoint") return 6;
  return 10;
}
