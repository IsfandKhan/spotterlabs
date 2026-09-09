import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { ThemeProvider } from "next-themes"
import { createBrowserRouter, RouterProvider } from "react-router-dom"

import { App } from "./App"
import "./index.css"
import { History } from "./pages/History"
import { PlanTrip } from "./pages/PlanTrip"
import { TripResult } from "./pages/TripResult"

const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <PlanTrip /> },
      { path: "trips/:id", element: <TripResult /> },
      { path: "history", element: <History /> },
    ],
  },
])

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider attribute="class" defaultTheme="light" enableSystem={false} disableTransitionOnChange>
      <RouterProvider router={router} />
    </ThemeProvider>
  </StrictMode>,
)
