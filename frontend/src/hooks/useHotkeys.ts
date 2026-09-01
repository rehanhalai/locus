import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useCaseStore } from "../stores/useCaseStore";

export function useHotkeys() {
  const navigate = useNavigate();
  const togglePlay = useCaseStore((s) => s.togglePlay);
  const stepFrame = useCaseStore((s) => s.stepFrame);
  const toggleTaskDrawer = useCaseStore((s) => s.toggleTaskDrawer);
  const activeCaseId = useCaseStore((s) => s.activeCaseId);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't trigger shortcuts if user is typing in an input or textarea
      const target = e.target as HTMLElement;
      if (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable) {
        return;
      }

      switch (e.key) {
        case "1":
          if (activeCaseId) {
            e.preventDefault();
            navigate("/investigate");
          }
          break;
        case "2":
          if (activeCaseId) {
            e.preventDefault();
            navigate("/search");
          }
          break;
        case "3":
          if (activeCaseId) {
            e.preventDefault();
            navigate("/export");
          }
          break;
        case "4":
          if (activeCaseId) {
            e.preventDefault();
            navigate("/audit");
          }
          break;
        case "0":
          e.preventDefault();
          navigate("/cases");
          break;
        case " ":
          e.preventDefault();
          togglePlay();
          break;
        case "[":
          e.preventDefault();
          stepFrame(-1);
          break;
        case "]":
          e.preventDefault();
          stepFrame(1);
          break;
        case "t":
        case "T":
          if (!e.ctrlKey && !e.metaKey) {
            e.preventDefault();
            toggleTaskDrawer();
          }
          break;
        default:
          break;
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [navigate, togglePlay, stepFrame, toggleTaskDrawer, activeCaseId]);
}
