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
  const { mobilePanel, setMobilePanel } = useAppStore();

  return (
    <Box h="100vh" display="flex" flexDirection="column">
      <LineStatusBanner />

      {/* Desktop layout (lg+) */}
      <Grid
        display={{ base: "none", lg: "grid" }}
        templateColumns={{ lg: "350px 1fr", xl: "350px 1fr 320px" }}
        flex={1}
        overflow="hidden"
      >
        <GridItem h="100%" overflow="hidden">
          <ChatPanel />
        </GridItem>

        <GridItem h="100%" overflow="hidden">
          <CenterPanel />
        </GridItem>

        <GridItem h="100%" overflow="hidden" display={{ lg: "none", xl: "block" }}>
          <DetailPanel />
        </GridItem>
      </Grid>

      {/* Mobile layout (< lg) */}
      <Box
        display={{ base: "flex", lg: "none" }}
        flex={1}
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
              onClick={() => setMobilePanel(panel)}
            >
              {label}
            </Button>
          ))}
        </HStack>
      </Box>
    </Box>
  );
}
