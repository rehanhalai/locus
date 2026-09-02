import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import type { BackgroundTask, RoomId } from "../types";

interface CaseStoreState {
  activeCaseId: string | null;
  activeEvidenceId: string | null;
  activeCaseNumber: string | null;
  activeCaseName: string | null;
  investigatorName: string;
  activeRoom: RoomId;
  taskDrawerOpen: boolean;
  runningTasks: BackgroundTask[];

  // Playback state
  masterPlayheadTime: string; // ISO string UTC
  isPlaying: boolean;
  playbackSpeed: number;
  timelineStart: string;
  timelineEnd: string;
  focusedCameraId: number | null;
  cameraOffsets: Record<number, number>; // camera_id -> offset in seconds

  // Actions
  setActiveCase: (caseId: string | null, caseNumber?: string, caseName?: string) => void;
  setActiveEvidenceId: (evidenceId: string | null) => void;
  setActiveRoom: (room: RoomId) => void;
  setTaskDrawerOpen: (open: boolean) => void;
  toggleTaskDrawer: () => void;
  setInvestigatorName: (name: string) => void;
  setFocusedCameraId: (camId: number | null) => void;
  setCameraOffset: (camId: number, offsetSeconds: number) => void;

  // Task actions
  addOrUpdateTask: (task: BackgroundTask) => void;
  removeTask: (taskId: string) => void;

  // Playback actions
  setMasterPlayheadTime: (isoTime: string) => void;
  setIsPlaying: (playing: boolean) => void;
  togglePlay: () => void;
  setPlaybackSpeed: (speed: number) => void;
  setTimelineBounds: (start: string, end: string) => void;
  stepFrame: (direction: 1 | -1, fps?: number) => void;
}

export const useCaseStore = create<CaseStoreState>()(
  persist(
    (set, get) => ({
      activeCaseId: null,
      activeEvidenceId: null,
      activeCaseNumber: null,
      activeCaseName: null,
      investigatorName: "Investigator Pande",
      activeRoom: "cases",
      taskDrawerOpen: false,
      runningTasks: [],

      masterPlayheadTime: new Date().toISOString(),
      isPlaying: false,
      playbackSpeed: 1,
      timelineStart: new Date(Date.now() - 3600 * 1000).toISOString(),
      timelineEnd: new Date().toISOString(),
      focusedCameraId: null,
      cameraOffsets: {},

      setActiveCase: (caseId, caseNumber, caseName) =>
        set({
          activeCaseId: caseId,
          activeCaseNumber: caseNumber || (caseId ? `CAS-${caseId.slice(0, 6)}` : null),
          activeCaseName: caseName || null,
        }),

      setActiveEvidenceId: (evidenceId) => set({ activeEvidenceId: evidenceId }),
      setActiveRoom: (room) => set({ activeRoom: room }),
      setTaskDrawerOpen: (open) => set({ taskDrawerOpen: open }),
      toggleTaskDrawer: () => set((state) => ({ taskDrawerOpen: !state.taskDrawerOpen })),
      setInvestigatorName: (name) => set({ investigatorName: name }),
      setFocusedCameraId: (camId) => set({ focusedCameraId: camId }),
      setCameraOffset: (camId, offsetSeconds) =>
        set((state) => ({
          cameraOffsets: { ...state.cameraOffsets, [camId]: offsetSeconds },
        })),

      addOrUpdateTask: (task) =>
        set((state) => {
          const idx = state.runningTasks.findIndex((t) => t.task_id === task.task_id);
          if (idx >= 0) {
            const updated = [...state.runningTasks];
            updated[idx] = { ...updated[idx], ...task };
            return { runningTasks: updated };
          }
          return { runningTasks: [task, ...state.runningTasks] };
        }),

      removeTask: (taskId) =>
        set((state) => ({
          runningTasks: state.runningTasks.filter((t) => t.task_id !== taskId),
        })),

      setMasterPlayheadTime: (isoTime) => set({ masterPlayheadTime: isoTime }),
      setIsPlaying: (playing) => set({ isPlaying: playing }),
      togglePlay: () => set((state) => ({ isPlaying: !state.isPlaying })),
      setPlaybackSpeed: (speed) => set({ playbackSpeed: speed }),
      setTimelineBounds: (start, end) => set({ timelineStart: start, timelineEnd: end }),

      stepFrame: (direction, fps = 25) => {
        const { masterPlayheadTime } = get();
        const currentMs = new Date(masterPlayheadTime).getTime();
        const frameMs = 1000 / fps;
        const newMs = currentMs + direction * frameMs;
        set({ masterPlayheadTime: new Date(newMs).toISOString() });
      },
    }),
    {
      name: "locus-forensic-store",
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        activeCaseId: state.activeCaseId,
        activeEvidenceId: state.activeEvidenceId,
        activeCaseNumber: state.activeCaseNumber,
        activeCaseName: state.activeCaseName,
        investigatorName: state.investigatorName,
        activeRoom: state.activeRoom,
        runningTasks: state.runningTasks,
        cameraOffsets: state.cameraOffsets,
      }),
    }
  )
);
