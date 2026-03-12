import { Navigate, Route, Routes } from 'react-router-dom';
import { Layout } from './components/Layout';
import { AuthProvider, useAuth } from './hooks/useAuth';
import { ConnectorsPage } from './pages/ConnectorsPage';
import { BacktestsPage } from './pages/BacktestsPage';
import { DashboardPage } from './pages/DashboardPage';
import { LoginPage } from './pages/LoginPage';
import { OrdersPage } from './pages/OrdersPage';
import { RunDetailPage } from './pages/RunDetailPage';

function Protected({ children }: { children: React.ReactNode }) {
  const { token, loading } = useAuth();
  if (loading) return <div className="loading-screen">Chargement...</div>;
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <Protected>
            <Layout>
              <DashboardPage />
            </Layout>
          </Protected>
        }
      />
      <Route
        path="/backtests"
        element={
          <Protected>
            <Layout>
              <BacktestsPage />
            </Layout>
          </Protected>
        }
      />
      <Route
        path="/runs/:runId"
        element={
          <Protected>
            <Layout>
              <RunDetailPage />
            </Layout>
          </Protected>
        }
      />
      <Route
        path="/orders"
        element={
          <Protected>
            <Layout>
              <OrdersPage />
            </Layout>
          </Protected>
        }
      />
      <Route
        path="/connectors"
        element={
          <Protected>
            <Layout>
              <ConnectorsPage />
            </Layout>
          </Protected>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  );
}
