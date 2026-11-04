import { Navigate, createBrowserRouter } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { useAuthStore } from "@/stores/authStore";
import { Live } from "@/routes/Live";
import { Login } from "@/routes/Login";
import { Register } from "@/routes/Register";
import { History } from "@/routes/History";
import { SessionDetail } from "@/routes/SessionDetail";
import { Calibration } from "@/routes/Calibration";
import { Settings } from "@/routes/Settings";
import { Breathing } from "@/routes/Breathing";
import { Explain } from "@/routes/Explain";
import { Sensors } from "@/routes/Sensors";

/** "/" → /live when authed, else /login. */
function RootRedirect() {
  const authed = useAuthStore.getState().isAuthenticated();
  return <Navigate to={authed ? "/live" : "/login"} replace />;
}

export const router = createBrowserRouter([
  { path: "/", element: <RootRedirect /> },
  { path: "/login", element: <Login /> },
  { path: "/register", element: <Register /> },
  // Public on purpose: this is the "hand someone the link" walkthrough of the
  // whole pipeline. It reads the unauthenticated /demo/session endpoint, so it
  // needs neither a login nor the AppShell's live WebSocket.
  { path: "/explain", element: <Explain /> },
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <AppShell />,
        children: [
          { path: "/live", element: <Live /> },
          { path: "/sensors", element: <Sensors /> },
          { path: "/history", element: <History /> },
          { path: "/history/:sessionId", element: <SessionDetail /> },
          { path: "/calibration", element: <Calibration /> },
          { path: "/breathing", element: <Breathing /> },
          { path: "/settings", element: <Settings /> },
          { path: "/demo", element: <Live /> },
        ],
      },
    ],
  },
  { path: "*", element: <Navigate to="/" replace /> },
]);
