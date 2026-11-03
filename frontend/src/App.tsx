import { useState, useCallback } from "react";
import Layout from "./components/Layout";
import Overview from "./pages/Overview";
import NewEvaluation from "./pages/NewEvaluation";
import EvaluationResult from "./pages/EvaluationResult";
import History from "./pages/History";
import Analytics from "./pages/Analytics";
import Providers from "./pages/Providers";
import type { Page } from "./types/navigation";

export default function App() {
  const [page, setPage] = useState<Page>({ id: "overview" });
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const navigate = useCallback((p: Page) => {
    setPage(p);
    // Scroll smoothly to top on page navigation
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, []);

  const handleRefreshCurrent = useCallback(() => {
    setRefreshTrigger((prev) => prev + 1);
  }, []);

  const renderActivePage = () => {
    switch (page.id) {
      case "overview":
        return <Overview navigate={navigate} refreshTrigger={refreshTrigger} />;
      case "new-evaluation":
        return <NewEvaluation navigate={navigate} />;
      case "result":
        return <EvaluationResult runId={page.runId} navigate={navigate} />;
      case "history":
        return <History navigate={navigate} refreshTrigger={refreshTrigger} />;
      case "analytics":
        return <Analytics refreshTrigger={refreshTrigger} />;
      case "providers":
        return <Providers refreshTrigger={refreshTrigger} />;
      default:
        return <Overview navigate={navigate} refreshTrigger={refreshTrigger} />;
    }
  };

  return (
    <Layout
      page={page}
      navigate={navigate}
      onRefreshCurrent={handleRefreshCurrent}
    >
      {renderActivePage()}
    </Layout>
  );
}
