"use client";

import { Box, Grid, GridItem, Tabs } from "@chakra-ui/react";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { TransportMap } from "@/components/map/TransportMap";
import { TransportGraphView } from "@/components/graph/TransportGraphView";
import { MemoryGraphView } from "@/components/graph/MemoryGraphView";
import { DetailPanel } from "@/components/detail/DetailPanel";
import { LineStatusBanner } from "@/components/LineStatusBanner";
import { useAppStore } from "@/store/useAppStore";
import type { MainView } from "@/store/useAppStore";

export default function Home() {
  const { mainView, setMainView } = useAppStore();

  return (
    <Box h="100vh" display="flex" flexDirection="column">
      {/* Line status banner */}
      <LineStatusBanner />

      {/* Three-panel layout */}
      <Grid
        templateColumns={{ base: "1fr", lg: "350px 1fr", xl: "350px 1fr 320px" }}
        flex={1}
        overflow="hidden"
      >
        {/* Left: Chat */}
        <GridItem h="100%" overflow="hidden" display={{ base: "none", lg: "block" }}>
          <ChatPanel />
        </GridItem>

        {/* Center: Map / Graph (tabbed) */}
        <GridItem h="100%" overflow="hidden">
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
        </GridItem>

        {/* Right: Detail panel */}
        <GridItem h="100%" overflow="hidden" display={{ base: "none", xl: "block" }}>
          <DetailPanel />
        </GridItem>
      </Grid>
    </Box>
  );
}
