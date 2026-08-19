import React from 'react';
import { Routes, Route, useNavigate, Navigate } from 'react-router-dom';
import { Security, LoginCallback } from '@okta/okta-react';
import { OktaAuth, toRelativeUrl } from '@okta/okta-auth-js';
import { oktaConfig } from './oktaConfig';
import { Login } from './components/Login';
import { AppLayout } from './components/AppLayout';
import { RequiredAuth } from './components/RequiredAuth';
import { ProjectsHome } from './components/ProjectsHome';
import { ProjectOverview } from './components/ProjectOverview';
import { PlaceholderView } from './components/PlaceholderView';
import { Repositories } from './components/Repositories';
import { RepositoryDetail } from './components/RepositoryDetail';
import { ThemeProvider } from './context/ThemeContext';

const oktaAuth = new OktaAuth(oktaConfig);

export const App: React.FC = () => {
  const navigate = useNavigate();

  const restoreOriginalUri = (_oktaAuth: OktaAuth, originalUri: string) => {
    // If original URL is /login/callback, fall back to /projects to avoid cycles
    const target = originalUri === '/login/callback' || !originalUri ? '/projects' : originalUri;
    navigate(toRelativeUrl(target, window.location.origin));
  };

  return (
    <ThemeProvider>
      <Security oktaAuth={oktaAuth} restoreOriginalUri={restoreOriginalUri}>
        <Routes>
          {/* Public login routes */}
          <Route path="/login" element={<Login />} />
          <Route path="/login/callback" element={<LoginCallback />} />

          {/* Protected routes wrapped in AppLayout */}
          <Route element={<RequiredAuth />}>
            <Route element={<AppLayout />}>
              <Route path="/" element={<Navigate to="/projects" replace />} />
              <Route path="/dashboard" element={<Navigate to="/projects" replace />} />
              <Route path="/projects" element={<ProjectsHome />} />
              
              {/* Project workspace specific routes */}
              <Route path="/projects/:projectId" element={<Navigate to="overview" replace />} />
              <Route path="/projects/:projectId/overview" element={<ProjectOverview />} />
              
              {/* Codebase / Repositories connected flow */}
              <Route path="/projects/:projectId/repositories" element={<Repositories />} />
              <Route path="/projects/:projectId/repositories/:repositoryId" element={<RepositoryDetail />} />
              
              {/* Placeholders for out-of-scope sections */}
              <Route
                path="/projects/:projectId/architecture"
                element={
                  <PlaceholderView
                    title="Architecture Mapping"
                    description="Architecture insights will appear after repository analysis."
                  />
                }
              />
              <Route
                path="/projects/:projectId/backlog"
                element={
                  <PlaceholderView
                    title="Jira / Backlog Management"
                    description="No Jira project connected yet. Issue tracking indicators will load here."
                  />
                }
              />
              <Route
                path="/projects/:projectId/analytics"
                element={
                  <PlaceholderView
                    title="Platform Analytics"
                    description="Analytical metrics will appear after connecting repository and backlog data."
                  />
                }
              />
              <Route
                path="/projects/:projectId/risk"
                element={
                  <PlaceholderView
                    title="ML Risk Forecaster"
                    description="Risk analysis will appear after sufficient project data is available."
                  />
                }
              />
              <Route
                path="/projects/:projectId/ai-insights"
                element={
                  <PlaceholderView
                    title="AI Insights Sandbox"
                    description="AI insights will appear after project data is connected."
                  />
                }
              />
              
              {/* Global settings placeholder */}
              <Route
                path="/projects/:projectId/settings"
                element={
                  <PlaceholderView
                    title="Settings"
                    description="Manage project configuration and credentials integration settings."
                  />
                }
              />
            </Route>
          </Route>

          {/* Wildcard redirect */}
          <Route path="*" element={<Navigate to="/projects" replace />} />
        </Routes>
      </Security>
    </ThemeProvider>
  );
};

export default App;
