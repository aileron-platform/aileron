import type React from 'react';
import { useCallback, useEffect, useRef, useState } from 'react';
import type { VersionControlFileChange } from '@/shared/version-control';

export type VersionControlFileGroup = 'staged' | 'unstaged';

interface UseVersionControlFileSelectionOptions {
  stagedFiles: VersionControlFileChange[];
  unstagedFiles: VersionControlFileChange[];
  onFileSelect?: (file: VersionControlFileChange | null, group: VersionControlFileGroup) => void;
}

const emptySelection = () => new Set<string>();

export function useVersionControlFileSelection({
  stagedFiles,
  unstagedFiles,
  onFileSelect,
}: UseVersionControlFileSelectionOptions) {
  const [selectedStagedPath, setSelectedStagedPath] = useState<string | null>(null);
  const [selectedUnstagedPath, setSelectedUnstagedPath] = useState<string | null>(null);
  const [selectedStagedPaths, setSelectedStagedPaths] = useState<Set<string>>(emptySelection);
  const [selectedUnstagedPaths, setSelectedUnstagedPaths] = useState<Set<string>>(emptySelection);
  const [lastSelectedStagedPath, setLastSelectedStagedPath] = useState<string | null>(null);
  const [lastSelectedUnstagedPath, setLastSelectedUnstagedPath] = useState<string | null>(null);

  const stagedFilesRef = useRef<VersionControlFileChange[]>([]);
  const unstagedFilesRef = useRef<VersionControlFileChange[]>([]);

  useEffect(() => {
    stagedFilesRef.current = stagedFiles;
    unstagedFilesRef.current = unstagedFiles;
  }, [stagedFiles, unstagedFiles]);

  const clearSelection = useCallback((group?: VersionControlFileGroup) => {
    if (!group || group === 'staged') {
      setSelectedStagedPath(null);
      setSelectedStagedPaths(emptySelection());
      setLastSelectedStagedPath(null);
    }
    if (!group || group === 'unstaged') {
      setSelectedUnstagedPath(null);
      setSelectedUnstagedPaths(emptySelection());
      setLastSelectedUnstagedPath(null);
    }
  }, []);

  const selectAll = useCallback((group: VersionControlFileGroup, files: VersionControlFileChange[]) => {
    const paths = new Set(files.map((file) => file.path));
    if (group === 'staged') {
      setSelectedStagedPaths(paths);
      setSelectedStagedPath(null);
      setSelectedUnstagedPath(null);
      setSelectedUnstagedPaths(emptySelection());
      return;
    }

    setSelectedUnstagedPaths(paths);
    setSelectedUnstagedPath(null);
    setSelectedStagedPath(null);
    setSelectedStagedPaths(emptySelection());
  }, []);

  const selectFile = useCallback((
    file: VersionControlFileChange,
    group: VersionControlFileGroup,
    event?: React.MouseEvent,
  ) => {
    if (event?.shiftKey) {
      event.preventDefault();
    }

    const isToggle = Boolean(event?.ctrlKey || event?.metaKey);
    const isRange = Boolean(event?.shiftKey);

    if (group === 'staged') {
      if (isToggle) {
        setSelectedStagedPaths((current) => {
          const next = new Set(current);
          if (next.has(file.path)) {
            next.delete(file.path);
          } else {
            next.add(file.path);
          }
          return next;
        });
      } else if (isRange && lastSelectedStagedPath) {
        const files = stagedFilesRef.current;
        const lastIndex = files.findIndex((candidate) => candidate.path === lastSelectedStagedPath);
        const currentIndex = files.findIndex((candidate) => candidate.path === file.path);

        if (lastIndex !== -1 && currentIndex !== -1) {
          const start = Math.min(lastIndex, currentIndex);
          const end = Math.max(lastIndex, currentIndex);
          setSelectedStagedPaths(new Set(files.slice(start, end + 1).map((candidate) => candidate.path)));
        } else {
          setSelectedStagedPaths(new Set([file.path]));
        }
      } else {
        setSelectedStagedPaths(new Set([file.path]));
      }

      setLastSelectedStagedPath(file.path);
      setSelectedStagedPath(file.path);
      setSelectedUnstagedPath(null);
      setSelectedUnstagedPaths(emptySelection());
      onFileSelect?.(file, group);
      return;
    }

    if (isToggle) {
      setSelectedUnstagedPaths((current) => {
        const next = new Set(current);
        if (next.has(file.path)) {
          next.delete(file.path);
        } else {
          next.add(file.path);
        }
        return next;
      });
    } else if (isRange && lastSelectedUnstagedPath) {
      const files = unstagedFilesRef.current;
      const lastIndex = files.findIndex((candidate) => candidate.path === lastSelectedUnstagedPath);
      const currentIndex = files.findIndex((candidate) => candidate.path === file.path);

      if (lastIndex !== -1 && currentIndex !== -1) {
        const start = Math.min(lastIndex, currentIndex);
        const end = Math.max(lastIndex, currentIndex);
        setSelectedUnstagedPaths(new Set(files.slice(start, end + 1).map((candidate) => candidate.path)));
      } else {
        setSelectedUnstagedPaths(new Set([file.path]));
      }
    } else {
      setSelectedUnstagedPaths(new Set([file.path]));
    }

    setLastSelectedUnstagedPath(file.path);
    setSelectedUnstagedPath(file.path);
    setSelectedStagedPath(null);
    setSelectedStagedPaths(emptySelection());
    onFileSelect?.(file, group);
  }, [lastSelectedStagedPath, lastSelectedUnstagedPath, onFileSelect]);

  const getActionPaths = useCallback((file: VersionControlFileChange, group: VersionControlFileGroup) => {
    const selectedPaths = group === 'staged' ? selectedStagedPaths : selectedUnstagedPaths;
    return selectedPaths.has(file.path) && selectedPaths.size > 1
      ? Array.from(selectedPaths)
      : [file.path];
  }, [selectedStagedPaths, selectedUnstagedPaths]);

  return {
    selectedStagedPath,
    selectedUnstagedPath,
    selectedStagedPaths,
    selectedUnstagedPaths,
    clearSelection,
    getActionPaths,
    selectAll,
    selectFile,
  };
}
