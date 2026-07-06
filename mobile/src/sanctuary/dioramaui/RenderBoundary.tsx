/**
 * Error boundary around the diorama canvas. A render/commit crash inside
 * the Skia subtree lands here instead of taking down the app; the owner
 * records a watchdog strike and swaps to the classic screen. Renders
 * nothing in the crashed state -- the owner replaces the whole subtree on
 * the same commit.
 */

import React from "react";

type Props = {
  onCrash: () => void;
  children: React.ReactNode;
};

type State = { crashed: boolean };

export class RenderBoundary extends React.Component<Props, State> {
  state: State = { crashed: false };

  static getDerivedStateFromError(): State {
    return { crashed: true };
  }

  componentDidCatch(): void {
    this.props.onCrash();
  }

  render(): React.ReactNode {
    if (this.state.crashed) return null;
    return this.props.children;
  }
}
