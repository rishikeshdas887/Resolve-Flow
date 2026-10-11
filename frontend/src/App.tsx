import React, { useEffect, useState } from 'react';
import { api } from './api/client';
import { CreateTicketModal } from './components/CreateTicketModal';
import { LoadingSpinner } from './components/Feedback';
import { Navbar, type NavTab, Sidebar } from './components/Navigation';
import { ApprovalsPage } from './pages/ApprovalsPage';
import { AuditPage } from './pages/AuditPage';
import { DashboardPage } from './pages/DashboardPage';
import { EvalsPage } from './pages/EvalsPage';
import { KnowledgePage } from './pages/KnowledgePage';
import { LoginPage } from './pages/LoginPage';
import { TicketDetailPage } from './pages/TicketDetailPage';
import { TicketsPage } from './pages/TicketsPage';
import type { Ticket, User } from './types';
import './styles/design-tokens.css';

export const App: React.FC = () => {
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [authChecking, setAuthChecking] = useState(true);

  // Navigation
  const [currentTab, setCurrentTab] = useState<NavTab>('dashboard');
  const [selectedTicketId, setSelectedTicketId] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);

  // Pending Approvals badge counter
  const [pendingApprovalsCount, setPendingApprovalsCount] = useState<number>(0);

  // Check existing session
  useEffect(() => {
    const checkAuth = async () => {
      const token = api.getToken();
      if (!token) {
        setAuthChecking(false);
        return;
      }

      try {
        const user = await api.getMe();
        setCurrentUser(user);
      } catch {
        api.clearAuth();
        setCurrentUser(null);
      } finally {
        setAuthChecking(false);
      }
    };

    checkAuth();
  }, []);

  // Poll pending approvals count when logged in
  useEffect(() => {
    if (!currentUser) return;

    const refreshPendingCount = async () => {
      try {
        const approvals = await api.listApprovals({ status: 'pending' });
        setPendingApprovalsCount(approvals.length);
      } catch {
        // ignore
      }
    };

    refreshPendingCount();
    const interval = setInterval(refreshPendingCount, 8000);
    return () => clearInterval(interval);
  }, [currentUser]);

  const handleLoginSuccess = (user: User) => {
    setCurrentUser(user);
  };

  const handleLogout = () => {
    api.clearAuth();
    setCurrentUser(null);
    setCurrentTab('dashboard');
    setSelectedTicketId(null);
  };

  const handleSelectTicket = (ticketId: string) => {
    setSelectedTicketId(ticketId);
  };

  const handleTicketCreated = (ticket: Ticket) => {
    setShowCreateModal(false);
    setSelectedTicketId(ticket.id);
  };

  if (authChecking) {
    return (
      <div
        style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: 'var(--color-canvas)',
        }}
      >
        <LoadingSpinner message="Connecting to ResolveFlow Operations..." size="lg" />
      </div>
    );
  }

  if (!currentUser) {
    return <LoginPage onLoginSuccess={handleLoginSuccess} />;
  }

  return (
    <div className="rf-app">
      {/* Sidebar Navigation */}
      <Sidebar
        currentTab={currentTab}
        onSelectTab={(tab) => {
          setCurrentTab(tab);
          setSelectedTicketId(null);
        }}
        currentUser={currentUser}
        onLogout={handleLogout}
        pendingApprovalsCount={pendingApprovalsCount}
      />

      {/* Main Content Area */}
      <div className="rf-main-content">
        <Navbar
          currentTab={currentTab}
          onSelectTab={(tab) => {
            setCurrentTab(tab);
            setSelectedTicketId(null);
          }}
          currentUser={currentUser}
          onLogout={handleLogout}
          pendingApprovalsCount={pendingApprovalsCount}
        />

        <main style={{ flex: 1, minHeight: 0 }}>
          {selectedTicketId ? (
            <TicketDetailPage
              ticketId={selectedTicketId}
              onBack={() => setSelectedTicketId(null)}
              onNavigateToApprovals={() => {
                setSelectedTicketId(null);
                setCurrentTab('approvals');
              }}
            />
          ) : currentTab === 'dashboard' ? (
            <DashboardPage
              onNavigateToTickets={() => setCurrentTab('tickets')}
              onNavigateToApprovals={() => setCurrentTab('approvals')}
              onSelectTicket={handleSelectTicket}
              onCreateTicketClick={() => setShowCreateModal(true)}
            />
          ) : currentTab === 'tickets' ? (
            <TicketsPage
              onSelectTicket={handleSelectTicket}
              onCreateTicketClick={() => setShowCreateModal(true)}
            />
          ) : currentTab === 'approvals' ? (
            <ApprovalsPage
              currentUser={currentUser}
              onSelectTicket={handleSelectTicket}
            />
          ) : currentTab === 'knowledge' ? (
            <KnowledgePage currentUser={currentUser} />
          ) : currentTab === 'evals' ? (
            <EvalsPage currentUser={currentUser} />
          ) : currentTab === 'audit' ? (
            <AuditPage onSelectTicket={handleSelectTicket} />
          ) : null}
        </main>
      </div>

      {/* Create Ticket Modal */}
      {showCreateModal && (
        <CreateTicketModal
          onClose={() => setShowCreateModal(false)}
          onTicketCreated={handleTicketCreated}
        />
      )}
    </div>
  );
};

export default App;
