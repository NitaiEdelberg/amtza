import { Component } from "react";

/**
 * Catches render-time exceptions so a bug in one component doesn't leave the
 * player staring at a blank white page — which is what React does by default
 * once an error escapes rendering.
 *
 * Has to be a class: there is no hook equivalent of componentDidCatch.
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { failed: false };
  }

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error, info) {
    // Kept visible in the console for debugging a deployed build.
    console.error("Unhandled UI error:", error, info);
  }

  render() {
    if (!this.state.failed) return this.props.children;

    const isHe = this.props.language === "he";
    return (
      <div className="error-boundary" role="alert">
        <div className="error-boundary__emoji">😵‍💫</div>
        <h2>{isHe ? "משהו השתבש" : "Something went wrong"}</h2>
        <p>
          {isHe
            ? "המשחק נתקל בתקלה. רענון הדף אמור לפתור את זה."
            : "The game hit an unexpected error. Reloading should fix it."}
        </p>
        <button className="btn btn--primary" onClick={() => window.location.reload()}>
          {isHe ? "רענון" : "Reload"}
        </button>
      </div>
    );
  }
}
