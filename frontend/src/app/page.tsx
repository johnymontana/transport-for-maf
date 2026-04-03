"use client";

import { Box, Grid, GridItem, HStack, Tabs, Button } from "@chakra-ui/react";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { TransportMap } from "@/components/map/TransportMap";
import { TransportGraphView } from "@/components/graph/TransportGraphView";
import { MemoryGraphView } from "@/components/graph/MemoryGraphView";
import { DetailPanel } from "@/components/detail/DetailPanel";
import { LineStatusBanner } from "@/components/LineStatusBanner";
import { useAppStore } from "@/store/useAppStore";
import type { MainView, MobilePanel } from "@/store/useAppStore";

function CenterPanel() {
  const { mainView, setMainView } = useAppStore();

  return (
    <Box h="100%" display="flex" flexDirection="column">
      <Tabs.Root
        value={mainView}
        onValueChange={(e) => setMainView(e.value as MainView)}
        size="sm"
        variant="line"
      >
        <Tabs.List bg="white" borderBottom="1px solid" borderColor="gray.200" px={2}>
          <Tabs.Trigger value="map" px={4} py={2} fontSize="sm">
            Map
          </Tabs.Trigger>
          <Tabs.Trigger value="graph" px={4} py={2} fontSize="sm">
            Transport Graph
          </Tabs.Trigger>
          <Tabs.Trigger value="memory" px={4} py={2} fontSize="sm">
            Memory Graph
          </Tabs.Trigger>
        </Tabs.List>
      </Tabs.Root>

      <Box flex={1} overflow="hidden">
        {mainView === "map" && <TransportMap />}
        {mainView === "graph" && <TransportGraphView />}
        {mainView === "memory" && <MemoryGraphView />}
      </Box>
    </Box>
  );
}

const mobileNavItems: { panel: MobilePanel; label: string }[] = [
  { panel: "chat", label: "Chat" },
  { panel: "main", label: "Map" },
  { panel: "detail", label: "Detail" },
];

export default function Home() {
  const { mobilePanel, setMobilePanel, setMainView } = useAppStore();

  const handleMobileNav = (panel: MobilePanel) => {
    setMobilePanel(panel);
    // "Map" tab should always show the geographic map, not a previously active sub-tab
    if (panel === "main") {
      setMainView("map");
    }
  };

  return (
    <Box h="100vh" display="flex" flexDirection="column">
      {/* Skip navigation link for keyboard users */}
      <a
        href="#main-content"
        style={{
          position: "absolute",
          left: "-9999px",
          top: "auto",
          zIndex: 9999,
        }}
        onFocus={(e) => {
          e.currentTarget.style.position = "fixed";
          e.currentTarget.style.top = "0";
          e.currentTarget.style.left = "0";
          e.currentTarget.style.padding = "8px 16px";
          e.currentTarget.style.background = "#2B6CB0";
          e.currentTarget.style.color = "white";
          e.currentTarget.style.fontWeight = "bold";
          e.currentTarget.style.fontSize = "14px";
        }}
        onBlur={(e) => {
          e.currentTarget.style.position = "absolute";
          e.currentTarget.style.left = "-9999px";
        }}
      >
        Skip to main content
      </a>

      <Box as="nav" aria-label="Line filters">
        <LineStatusBanner />
      </Box>

      {/* Desktop layout (lg+) */}
      <Box as="main" id="main-content" flex={1} overflow="hidden">
        <Grid
          display={{ base: "none", lg: "grid" }}
          templateColumns={{ lg: "350px 1fr 280px", xl: "350px 1fr 320px" }}
          h="100%"
          overflow="hidden"
        >
          <GridItem as="aside" aria-label="Chat assistant" h="100%" overflow="hidden">
            <ChatPanel />
          </GridItem>

          <GridItem as="section" aria-label="Map and visualizations" h="100%" overflow="hidden">
            <CenterPanel />
          </GridItem>

          <GridItem as="aside" aria-label="Station details" h="100%" overflow="hidden">
            <DetailPanel />
          </GridItem>
        </Grid>

        {/* Mobile layout (< lg) */}
        <Box
          display={{ base: "flex", lg: "none" }}
          h="100%"
          flexDirection="column"
          overflow="hidden"
        >
          <Box flex={1} overflow="hidden">
            {mobilePanel === "chat" && <ChatPanel />}
            {mobilePanel === "main" && <CenterPanel />}
            {mobilePanel === "detail" && <DetailPanel />}
          </Box>

          {/* Bottom navigation */}
          <HStack
            as="nav"
            aria-label="Navigation"
            bg="white"
            borderTop="1px solid"
            borderColor="gray.200"
            justify="space-around"
            py={2}
            flexShrink={0}
          >
            {mobileNavItems.map(({ panel, label }) => (
              <Button
                key={panel}
                variant="ghost"
                size="sm"
                color={mobilePanel === panel ? "blue.600" : "gray.500"}
                fontWeight={mobilePanel === panel ? "bold" : "normal"}
                onClick={() => handleMobileNav(panel)}
              >
                {label}
              </Button>
            ))}
          </HStack>
        </Box>
      </Box>
    </Box>
  );
}
