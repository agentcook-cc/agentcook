import { createBrowserRouter, Navigate } from "react-router-dom";
import ChatPage from "@/pages/ChatPage";
import LoginPage from "@/pages/LoginPage";
import NotFound from "@/pages/error/NotFound";
import ServerError from "@/pages/error/ServerError";

// BASE_URL is Vite's `base` ("/" in dev, "/app/" behind the gateway).
const basename = import.meta.env.BASE_URL.replace(/\/$/, "") || "/";

export const router = createBrowserRouter(
  [
    {
      path: "/",
      element: <Navigate to="/chat" replace />,
    },
    {
      path: "/login",
      element: <LoginPage />,
    },
    {
      path: "/chat",
      element: <ChatPage />,
    },
    {
      path: "/chat/:sessionId",
      element: <ChatPage />,
    },
    {
      path: "/500",
      element: <ServerError />,
    },
    {
      path: "*",
      element: <NotFound />,
    },
  ],
  { basename },
);
