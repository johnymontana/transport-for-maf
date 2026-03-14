"use client";

import { useEffect, useState } from "react";
import { Box, HStack, Text, Badge } from "@chakra-ui/react";
import { getLines } from "@/lib/api";
import { TFL_LINE_COLORS } from "@/lib/graphStyles";

interface LineInfo {
  lineId: string;
  name: string;
  color: string;
  stationCount: number;
}

export function LineStatusBanner() {
  const [lines, setLines] = useState<LineInfo[]>([]);

  useEffect(() => {
    getLines()
      .then((data) => setLines(data.lines))
      .catch(() => {});
  }, []);

  if (lines.length === 0) {
    return (
      <Box
        bg="gray.800"
        color="white"
        px={4}
        py={1.5}
        fontSize="xs"
        textAlign="center"
      >
        TfL Explorer - Loading lines...
      </Box>
    );
  }

  return (
    <Box bg="gray.800" px={4} py={1.5} overflow="hidden">
      <HStack gap={3} overflowX="auto" css={{ "&::-webkit-scrollbar": { display: "none" } }}>
        <Text color="gray.400" fontSize="xs" flexShrink={0} fontWeight="bold">
          Lines:
        </Text>
        {lines.map((line) => (
          <Badge
            key={line.lineId}
            bg={TFL_LINE_COLORS[line.lineId] || line.color || "gray.600"}
            color={
              ["circle", "hammersmith-city", "waterloo-city"].includes(line.lineId)
                ? "black"
                : "white"
            }
            fontSize="10px"
            px={2}
            py={0.5}
            borderRadius="sm"
            flexShrink={0}
          >
            {line.name}
          </Badge>
        ))}
      </HStack>
    </Box>
  );
}
