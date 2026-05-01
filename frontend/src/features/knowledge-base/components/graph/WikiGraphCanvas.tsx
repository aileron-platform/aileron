import React from 'react';
import Graph from 'graphology';
import { SigmaContainer, useCamera, useLoadGraph, useRegisterEvents } from '@react-sigma/core';
import '@react-sigma/core/lib/style.css';
import type { KnowledgeBaseGraphEdge, KnowledgeBaseGraphNode } from '@/shared/types/knowledgeBase';
import { graphNodeIdFromPath } from './graphUtils';

export interface WikiGraphControls {
  fit: () => void;
  zoomIn: () => void;
  zoomOut: () => void;
  reset: () => void;
  focusNode: (nodeId: string) => void;
}

interface WikiGraphCanvasProps {
  nodes: KnowledgeBaseGraphNode[];
  edges: KnowledgeBaseGraphEdge[];
  selectedPath: string;
  onSelect: (path: string) => void;
  onControlsReady?: (controls: WikiGraphControls | null) => void;
}

export const WikiGraphCanvas: React.FC<WikiGraphCanvasProps> = ({
  nodes,
  edges,
  selectedPath,
  onSelect,
  onControlsReady,
}) => {
  const selectedNodeId = graphNodeIdFromPath(selectedPath);

  return (
    <div className="h-full min-h-0 w-full" data-testid="wiki-graph-canvas">
      <SigmaContainer style={{ height: '100%', width: '100%', background: 'transparent' }}>
        <GraphLoader
          nodes={nodes}
          edges={edges}
          selectedNodeId={selectedNodeId}
        />
        <GraphEvents nodes={nodes} onSelect={onSelect} />
        <GraphController
          selectedNodeId={selectedNodeId}
          autoFitKey={`${nodes.length}:${edges.length}`}
          onControlsReady={onControlsReady}
        />
      </SigmaContainer>
    </div>
  );
};

const GraphLoader: React.FC<{
  nodes: KnowledgeBaseGraphNode[];
  edges: KnowledgeBaseGraphEdge[];
  selectedNodeId: string;
}> = ({ nodes, edges, selectedNodeId }) => {
  const loadGraph = useLoadGraph();

  React.useEffect(() => {
    const graph = new Graph({ type: 'undirected' });
    const radius = Math.max(120, nodes.length * 12);
    nodes.forEach((node, index) => {
      const angle = (index / Math.max(nodes.length, 1)) * Math.PI * 2;
      graph.addNode(node.id, {
        x: Math.cos(angle) * radius,
        y: Math.sin(angle) * radius,
        label: node.label,
        size: node.id === selectedNodeId ? 15 : 9,
        color: node.id === selectedNodeId ? '#2563eb' : '#64748b',
      });
    });
    edges.forEach((edge) => {
      if (graph.hasNode(edge.source) && graph.hasNode(edge.target) && !graph.hasEdge(edge.id)) {
        graph.addEdgeWithKey(edge.id, edge.source, edge.target, {
          size: Math.max(1, edge.weight),
          color: '#94a3b8',
        });
      }
    });
    loadGraph(graph);
  }, [edges, loadGraph, nodes, selectedNodeId]);

  return null;
};

const GraphEvents: React.FC<{
  nodes: KnowledgeBaseGraphNode[];
  onSelect: (path: string) => void;
}> = ({ nodes, onSelect }) => {
  const registerEvents = useRegisterEvents();
  const pathById = React.useMemo(() => new Map(nodes.map((node) => [node.id, node.path])), [nodes]);

  React.useEffect(() => {
    registerEvents({
      clickNode: ({ node }) => {
        const path = pathById.get(node);
        if (path) onSelect(path);
      },
    });
  }, [onSelect, pathById, registerEvents]);

  return null;
};

const GraphController: React.FC<{
  selectedNodeId: string;
  autoFitKey: string;
  onControlsReady?: (controls: WikiGraphControls | null) => void;
}> = ({ selectedNodeId, autoFitKey, onControlsReady }) => {
  const { reset, zoomIn, zoomOut, gotoNode } = useCamera({ duration: 180 });
  const skipFocusAfterFitRef = React.useRef<string | null>(null);
  const controls = React.useMemo<WikiGraphControls>(() => ({
    fit: reset,
    zoomIn,
    zoomOut,
    reset,
    focusNode: gotoNode,
  }), [gotoNode, reset, zoomIn, zoomOut]);

  React.useEffect(() => {
    onControlsReady?.(controls);

    return () => onControlsReady?.(null);
  }, [controls, onControlsReady]);

  React.useEffect(() => {
    reset();
    skipFocusAfterFitRef.current = selectedNodeId;
  }, [autoFitKey, reset, selectedNodeId]);

  React.useEffect(() => {
    if (selectedNodeId) {
      if (skipFocusAfterFitRef.current === selectedNodeId) {
        skipFocusAfterFitRef.current = null;
        return;
      }
      gotoNode(selectedNodeId);
    }
  }, [gotoNode, selectedNodeId]);

  return null;
};
