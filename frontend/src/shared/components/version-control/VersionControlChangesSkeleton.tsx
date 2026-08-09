/**
 * Shared first-load skeleton for the version-control changes surface.
 * Rendered while the changes query is loading its very first page
 * (`isLoading && !data`) across workspace/knowledge-base/marketplace tabs.
 */
export interface VersionControlChangesSkeletonProps {
  testId?: string;
}

export const VersionControlChangesSkeleton = ({
  testId = 'vc-changes-skeleton',
}: VersionControlChangesSkeletonProps) => (
  <div
    data-testid={testId}
    className="h-full space-y-3 p-3"
    aria-busy="true"
    aria-live="polite"
  >
    <div className="h-9 animate-pulse rounded-md bg-muted/60" />
    <div className="h-5 w-24 animate-pulse rounded bg-muted/50" />
    <div className="space-y-2">
      <div className="h-8 animate-pulse rounded-md bg-muted/40" />
      <div className="h-8 animate-pulse rounded-md bg-muted/40" />
    </div>
    <div className="h-5 w-28 animate-pulse rounded bg-muted/50" />
    <div className="space-y-2">
      <div className="h-8 animate-pulse rounded-md bg-muted/40" />
      <div className="h-8 animate-pulse rounded-md bg-muted/40" />
    </div>
  </div>
);
