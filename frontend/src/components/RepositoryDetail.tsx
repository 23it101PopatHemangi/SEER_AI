import React, { useEffect, useState, useRef } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useOktaAuth } from '@okta/okta-react';
import {
  Github,
  ArrowLeft,
  Calendar,
  Star,
  GitFork,
  GitBranch,
  Info,
  ChevronDown,
  ChevronUp,
  File,
  Folder,
  Circle,
  Clock,
  AlertCircle,
  GitPullRequest,
  CheckCircle,
  Settings,
  Cpu,
  Layers,
  Code2,
  Share2,
  Boxes,
  Zap,
} from 'lucide-react';
import { repositoryService, RepositoryDetail as IRepoDetail, IssueInfo, PullRequestInfo } from '../services/repositoryService';

type Tab = 'overview' | 'structure' | 'commits' | 'issues' | 'pull-requests';

const STAGES = [
  'Analyzing repository...',
  'Loading overview...',
  'Analyzing architecture...',
  'Detecting technologies...',
  'Loading key components...',
  'Analyzing API surface...',
  'Detecting code patterns...',
  'Finding integration points...',
  'Analyzing dependencies...',
  'Finalizing repository insights...'
];

export const RepositoryDetail: React.FC = () => {
  const { authState, oktaAuth } = useOktaAuth();
  const { projectId, repositoryId } = useParams<{ projectId: string; repositoryId: string }>();
  const navigate = useNavigate();

  const [detail, setDetail] = useState<IRepoDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>('overview');

  // Progressive analysis loading states
  const [analysisStage, setAnalysisStage] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const stageIntervalRef = useRef<any>(null);

  // Filtering states for Issues & PRs
  const [issueFilter, setIssueFilter] = useState<'all' | 'open' | 'closed'>('all');
  const [prFilter, setPrFilter] = useState<'all' | 'open' | 'closed' | 'merged'>('all');

  // Accordion toggle states on Overview tab
  const [expanded, setExpanded] = useState<Record<string, boolean>>({
    tech: true,
    arch: true,
    components: false,
    api: false,
    patterns: false,
    integrations: false,
    deps: false,
  });

  const toggleSection = (section: string) => {
    setExpanded((prev) => ({ ...prev, [section]: !prev[section] }));
  };

  useEffect(() => {
    const loadDetail = async () => {
      if (!projectId || !repositoryId) return;
      
      // Reset progressive loader states
      setLoading(true);
      setError(null);
      setAnalysisStage(0);

      // Increment loader stages progressively every 500ms while request is in-flight
      stageIntervalRef.current = setInterval(() => {
        setAnalysisStage((prev) => (prev < 8 ? prev + 1 : prev));
      }, 500);

      try {
        let email = '';
        if (authState?.isAuthenticated) {
          const user = await oktaAuth.getUser();
          email = user.email || '';
        }
        
        // Fetch raw telemetry details from DB/GitHub
        const data = await repositoryService.getRepositoryDetail(projectId, repositoryId, email);
        setDetail(data);

        // Clear automatic tick and step through remaining stages smoothly
        if (stageIntervalRef.current) {
          clearInterval(stageIntervalRef.current);
        }

        // Run remaining loading steps at 300ms intervals for smooth progressive completion
        setAnalysisStage((currentStage) => {
          let next = currentStage;
          const finalizeInterval = setInterval(() => {
            if (next < STAGES.length - 1) {
              next += 1;
              setAnalysisStage(next);
            } else {
              clearInterval(finalizeInterval);
              setLoading(false);
            }
          }, 300);
          return currentStage;
        });

      } catch (err: any) {
        console.error(err);
        setError(err.message || 'Failed to retrieve repository details.');
        if (stageIntervalRef.current) {
          clearInterval(stageIntervalRef.current);
        }
        setLoading(false);
      }
    };

    if (authState) {
      loadDetail();
    }

    return () => {
      if (stageIntervalRef.current) {
        clearInterval(stageIntervalRef.current);
      }
    };
  }, [projectId, repositoryId, authState, oktaAuth]);

  const formatDate = (isoString: string) => {
    try {
      const date = new Date(isoString);
      return date.toLocaleDateString(undefined, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      });
    } catch (e) {
      return 'N/A';
    }
  };

  const getRelativeTime = (isoString: string) => {
    try {
      const diffMs = Date.now() - new Date(isoString).getTime();
      const diffMins = Math.floor(diffMs / 60000);
      const diffHours = Math.floor(diffMins / 60);
      const diffDays = Math.floor(diffHours / 24);

      if (diffMins < 1) return 'just now';
      if (diffMins < 60) return `${diffMins}m ago`;
      if (diffHours < 24) return `${diffHours}h ago`;
      if (diffDays === 1) return 'yesterday';
      return `${diffDays} days ago`;
    } catch (e) {
      return 'some time ago';
    }
  };

  // Render Progressive Loading State with Skeletons
  if (loading) {
    return (
      <div className="p-8 max-w-4xl mx-auto flex flex-col items-center justify-center min-h-[500px] space-y-8">
        
        {/* Animated Progress Indicator */}
        <div className="w-full max-w-md bg-slate-200 dark:bg-slate-800 h-2 rounded-full overflow-hidden">
          <div
            className="bg-primary-600 h-full transition-all duration-300 ease-out"
            style={{ width: `${((analysisStage + 1) / STAGES.length) * 100}%` }}
          />
        </div>

        {/* Current loading step message */}
        <div className="text-center space-y-2">
          <div className="inline-flex items-center space-x-2">
            <div className="w-4 h-4 border-2 border-primary-500 border-t-transparent rounded-full animate-spin"></div>
            <h3 className="text-base font-bold text-slate-850 dark:text-slate-100">
              {STAGES[analysisStage]}
            </h3>
          </div>
          <p className="text-xs text-slate-400 dark:text-slate-500">
            Running static telemetry checkers. Do not close this page.
          </p>
        </div>

        {/* Skeleton panels simulating layout structure */}
        <div className="w-full space-y-6 pt-4 animate-pulse">
          <div className="h-28 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800/80 rounded-xl p-6 space-y-4">
            <div className="h-5 bg-slate-200 dark:bg-slate-800 rounded w-1/4"></div>
            <div className="grid grid-cols-2 gap-4">
              <div className="h-4 bg-slate-150 dark:bg-slate-850 rounded w-3/4"></div>
              <div className="h-4 bg-slate-150 dark:bg-slate-850 rounded w-1/2"></div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="md:col-span-2 h-44 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800/80 rounded-xl p-6 space-y-3">
              <div className="h-4 bg-slate-200 dark:bg-slate-800 rounded w-1/3"></div>
              <div className="h-3 bg-slate-150 dark:bg-slate-850 rounded w-full"></div>
              <div className="h-3 bg-slate-150 dark:bg-slate-850 rounded w-5/6"></div>
              <div className="h-3 bg-slate-150 dark:bg-slate-850 rounded w-4/5"></div>
            </div>
            <div className="h-44 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800/80 rounded-xl p-6 space-y-3">
              <div className="h-4 bg-slate-200 dark:bg-slate-800 rounded w-1/2"></div>
              <div className="h-8 bg-slate-150 dark:bg-slate-850 rounded-full w-full"></div>
              <div className="h-3 bg-slate-150 dark:bg-slate-850 rounded w-3/4"></div>
            </div>
          </div>
        </div>

      </div>
    );
  }

  // Render Error state
  if (error || !detail) {
    return (
      <div className="p-8 max-w-xl mx-auto text-center space-y-4">
        <div className="inline-flex items-center justify-center p-3 bg-red-50 dark:bg-red-950/20 text-red-500 rounded-xl border border-red-200 dark:border-red-800/40">
          <AlertCircle className="w-8 h-8" />
        </div>
        <h2 className="text-xl font-bold text-slate-900 dark:text-white">Failed to load repository</h2>
        <p className="text-sm text-slate-500 dark:text-slate-400">{error || 'An unexpected error occurred.'}</p>
        <Link
          to={`/projects/${projectId}/repositories`}
          className="inline-flex items-center space-x-2 text-sm font-semibold text-primary-600 dark:text-primary-400 hover:underline"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Repositories</span>
        </Link>
      </div>
    );
  }

  const { metadata, languages, file_structure, commits, issues, pull_requests, analysis } = detail;

  // Filter Issues
  const filteredIssues = issues.filter((issue) => {
    if (issueFilter === 'all') return true;
    return issue.state.toLowerCase() === issueFilter;
  });

  // Filter PRs
  const filteredPRs = pull_requests.filter((pr) => {
    if (prFilter === 'all') return true;
    if (prFilter === 'merged') return pr.is_merged;
    if (prFilter === 'closed') return pr.state.toLowerCase() === 'closed' && !pr.is_merged;
    return pr.state.toLowerCase() === prFilter;
  });

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      
      {/* Back link & Header */}
      <div className="space-y-4">
        <Link
          to={`/projects/${projectId}/repositories`}
          className="inline-flex items-center space-x-2 text-xs font-semibold text-slate-500 hover:text-slate-900 dark:hover:text-white transition"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Repositories</span>
        </Link>

        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center space-x-3">
            <div className="p-3 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 rounded-xl">
              <Github className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h1 className="text-2xl font-extrabold text-slate-900 dark:text-white">
                  {metadata.name}
                </h1>
                <span className="text-[10px] font-bold uppercase tracking-wider bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 px-2 py-0.5 rounded border border-slate-200 dark:border-slate-700">
                  Public
                </span>
              </div>
              <p className="text-xs text-slate-400 dark:text-slate-500 mt-0.5">
                Connected to project &bull; Owner: {metadata.owner}
              </p>
            </div>
          </div>

          <a
            href={metadata.github_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center space-x-2 text-xs font-semibold bg-white dark:bg-slate-900 hover:bg-slate-50 dark:hover:bg-slate-800/80 border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300 px-4 py-2.5 rounded-lg shadow-sm transition"
          >
            <Github className="w-4 h-4" />
            <span>Open on GitHub</span>
          </a>
        </div>
      </div>

      {/* Tabs List */}
      <div className="border-b border-slate-200 dark:border-slate-800 flex overflow-x-auto space-x-6">
        {(['overview', 'structure', 'commits', 'issues', 'pull-requests'] as Tab[]).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`pb-4 text-sm font-semibold capitalize border-b-2 transition duration-150 whitespace-nowrap px-1 ${
              activeTab === tab
                ? 'border-primary-500 text-primary-600 dark:text-primary-400 font-bold'
                : 'border-transparent text-slate-500 hover:text-slate-900 dark:hover:text-slate-300'
            }`}
          >
            {tab.replace('-', ' ')}
          </button>
        ))}
      </div>

      {/* Active Tab Panels */}
      <div className="space-y-6">
        
        {/* T1. Overview Tab */}
        {activeTab === 'overview' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            
            {/* Left Column: Repository Info & Expandable Telemetry Analysis */}
            <div className="lg:col-span-2 space-y-6">
              
              {/* Repository Metadata */}
              <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800/85 rounded-xl p-6 shadow-sm space-y-4">
                <h3 className="text-sm font-bold text-slate-800 dark:text-slate-200 uppercase tracking-widest border-b border-slate-100 dark:border-slate-800 pb-2">
                  Repository Info
                </h3>
                
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-y-4 gap-x-6 text-sm">
                  <div className="space-y-1">
                    <span className="text-xs text-slate-400 dark:text-slate-500 block">Default Branch</span>
                    <div className="flex items-center space-x-1.5 font-semibold text-slate-800 dark:text-slate-200">
                      <GitBranch className="w-4 h-4 text-slate-400" />
                      <span>{metadata.default_branch}</span>
                    </div>
                  </div>
                  <div className="space-y-1">
                    <span className="text-xs text-slate-400 dark:text-slate-500 block">Primary Language</span>
                    <div className="flex items-center space-x-1.5 font-semibold text-slate-800 dark:text-slate-200">
                      <Circle className="w-3 h-3 text-primary-500" />
                      <span>{metadata.primary_language || 'None'}</span>
                    </div>
                  </div>
                  <div className="space-y-1">
                    <span className="text-xs text-slate-400 dark:text-slate-500 block">Stars</span>
                    <div className="flex items-center space-x-1.5 font-semibold text-slate-800 dark:text-slate-200">
                      <Star className="w-4 h-4 text-amber-500" />
                      <span>{metadata.stars}</span>
                    </div>
                  </div>
                  <div className="space-y-1">
                    <span className="text-xs text-slate-400 dark:text-slate-500 block">Forks</span>
                    <div className="flex items-center space-x-1.5 font-semibold text-slate-800 dark:text-slate-200">
                      <GitFork className="w-4 h-4 text-slate-400" />
                      <span>{metadata.forks}</span>
                    </div>
                  </div>
                  <div className="space-y-1">
                    <span className="text-xs text-slate-400 dark:text-slate-500 block">Open Issues</span>
                    <div className="flex items-center space-x-1.5 font-semibold text-slate-800 dark:text-slate-200">
                      <Info className="w-4 h-4 text-slate-400" />
                      <span>{metadata.open_issues_count}</span>
                    </div>
                  </div>
                  <div className="space-y-1">
                    <span className="text-xs text-slate-400 dark:text-slate-500 block">Last Pushed</span>
                    <div className="flex items-center space-x-1.5 font-semibold text-slate-800 dark:text-slate-200">
                      <Clock className="w-4 h-4 text-slate-400" />
                      <span>{formatDate(metadata.last_pushed_at)}</span>
                    </div>
                  </div>
                </div>

                <div className="pt-4 border-t border-slate-100 dark:border-slate-800 text-xs text-slate-400 dark:text-slate-500 flex flex-col sm:flex-row gap-4 justify-between">
                  <span>Created: {formatDate(metadata.created_at)}</span>
                  <span>Last Synced: {formatDate(metadata.updated_at)}</span>
                </div>
              </div>

              {/* Rich Static Code Analysis Accordion Sections */}
              <div className="space-y-4">
                
                {/* 1. Architecture Overview */}
                <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800/85 rounded-xl overflow-hidden shadow-sm transition">
                  <button
                    onClick={() => toggleSection('arch')}
                    className="w-full flex items-center justify-between px-6 py-4 hover:bg-slate-50 dark:hover:bg-slate-800/20 text-left font-bold text-sm text-slate-800 dark:text-slate-200"
                  >
                    <div className="flex items-center space-x-2">
                      <Cpu className="w-4.5 h-4.5 text-primary-500" />
                      <span>Architecture Overview</span>
                    </div>
                    {expanded.arch ? <ChevronUp className="w-4.5 h-4.5" /> : <ChevronDown className="w-4.5 h-4.5" />}
                  </button>
                  {expanded.arch && (
                    <div className="px-6 pb-5 pt-3 text-sm text-slate-650 dark:text-slate-400 border-t border-slate-100 dark:border-slate-800/50">
                      {analysis?.architecture_overview ? (
                        <div className="space-y-2">
                          {analysis.architecture_overview.split('\n').map((line, index) => {
                            const cleanLine = line.replace(/&bull;|\u2022/g, '').trim();
                            if (!cleanLine) return null;
                            const parts = cleanLine.split(':');
                            const title = parts[0];
                            const value = parts.slice(1).join(':').trim();
                            return (
                              <div key={index} className="flex items-start space-x-2">
                                <span className="w-1.5 h-1.5 rounded-full bg-primary-500 mt-2 shrink-0" />
                                <span className="text-slate-650 dark:text-slate-350">
                                  <strong className="text-slate-800 dark:text-slate-200">{title}:</strong> {value}
                                </span>
                              </div>
                            );
                          })}
                        </div>
                      ) : (
                        <span className="text-slate-400 dark:text-slate-500 italic">Not detected</span>
                      )}
                    </div>
                  )}
                </div>

                {/* 2. Frameworks & Technologies */}
                <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800/85 rounded-xl overflow-hidden shadow-sm transition">
                  <button
                    onClick={() => toggleSection('tech')}
                    className="w-full flex items-center justify-between px-6 py-4 hover:bg-slate-50 dark:hover:bg-slate-800/20 text-left font-bold text-sm text-slate-800 dark:text-slate-200"
                  >
                    <div className="flex items-center space-x-2">
                      <Layers className="w-4.5 h-4.5 text-primary-500" />
                      <span>Technologies & Frameworks</span>
                    </div>
                    {expanded.tech ? <ChevronUp className="w-4.5 h-4.5" /> : <ChevronDown className="w-4.5 h-4.5" />}
                  </button>
                  {expanded.tech && (
                    <div className="px-6 pb-5 pt-3 border-t border-slate-100 dark:border-slate-800/50">
                      {analysis?.technologies && analysis.technologies.length > 0 ? (
                        <div className="flex flex-wrap gap-2">
                          {analysis.technologies.map((t) => (
                            <span
                              key={t}
                              className="px-2.5 py-1 text-xs font-semibold bg-primary-50 dark:bg-primary-950/20 text-primary-600 dark:text-primary-400 rounded-md border border-primary-100 dark:border-primary-900/30"
                            >
                              {t}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span className="text-sm text-slate-400 dark:text-slate-500 italic">Not detected</span>
                      )}
                    </div>
                  )}
                </div>

                {/* 3. Key Components */}
                <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800/85 rounded-xl overflow-hidden shadow-sm transition">
                  <button
                    onClick={() => toggleSection('components')}
                    className="w-full flex items-center justify-between px-6 py-4 hover:bg-slate-50 dark:hover:bg-slate-800/20 text-left font-bold text-sm text-slate-800 dark:text-slate-200"
                  >
                    <div className="flex items-center space-x-2">
                      <Code2 className="w-4.5 h-4.5 text-primary-500" />
                      <span>Key Components</span>
                    </div>
                    {expanded.components ? <ChevronUp className="w-4.5 h-4.5" /> : <ChevronDown className="w-4.5 h-4.5" />}
                  </button>
                  {expanded.components && (
                    <div className="px-6 pb-5 pt-3 text-xs font-mono text-slate-650 dark:text-slate-400 border-t border-slate-100 dark:border-slate-800/50 space-y-1.5">
                      {analysis?.key_components && analysis.key_components.length > 0 ? (
                        analysis.key_components.map((c) => (
                          <div key={c} className="flex items-center space-x-2 py-0.5">
                            <File className="w-3.5 h-3.5 text-slate-450 shrink-0" />
                            <span>{c}</span>
                          </div>
                        ))
                      ) : (
                        <span className="text-sm font-sans text-slate-400 dark:text-slate-500 italic">Not detected</span>
                      )}
                    </div>
                  )}
                </div>

                {/* 4. API Surface */}
                <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800/85 rounded-xl overflow-hidden shadow-sm transition">
                  <button
                    onClick={() => toggleSection('api')}
                    className="w-full flex items-center justify-between px-6 py-4 hover:bg-slate-50 dark:hover:bg-slate-800/20 text-left font-bold text-sm text-slate-800 dark:text-slate-200"
                  >
                    <div className="flex items-center space-x-2">
                      <Share2 className="w-4.5 h-4.5 text-primary-500" />
                      <span>API Surface</span>
                    </div>
                    {expanded.api ? <ChevronUp className="w-4.5 h-4.5" /> : <ChevronDown className="w-4.5 h-4.5" />}
                  </button>
                  {expanded.api && (
                    <div className="px-6 pb-5 pt-3 text-xs font-mono text-slate-650 dark:text-slate-400 border-t border-slate-100 dark:border-slate-800/50 space-y-1.5">
                      {analysis?.api_surface && analysis.api_surface.length > 0 ? (
                        analysis.api_surface.map((api) => (
                          <div key={api} className="flex items-center space-x-2 py-0.5">
                            <Zap className="w-3.5 h-3.5 text-amber-500 shrink-0" />
                            <span>{api}</span>
                          </div>
                        ))
                      ) : (
                        <span className="text-sm font-sans text-slate-400 dark:text-slate-500 italic">Not detected</span>
                      )}
                    </div>
                  )}
                </div>

                {/* 5. Code Patterns */}
                <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800/85 rounded-xl overflow-hidden shadow-sm transition">
                  <button
                    onClick={() => toggleSection('patterns')}
                    className="w-full flex items-center justify-between px-6 py-4 hover:bg-slate-50 dark:hover:bg-slate-800/20 text-left font-bold text-sm text-slate-800 dark:text-slate-200"
                  >
                    <div className="flex items-center space-x-2">
                      <Layers className="w-4.5 h-4.5 text-primary-500" />
                      <span>Code Patterns</span>
                    </div>
                    {expanded.patterns ? <ChevronUp className="w-4.5 h-4.5" /> : <ChevronDown className="w-4.5 h-4.5" />}
                  </button>
                  {expanded.patterns && (
                    <div className="px-6 pb-5 pt-3 text-sm text-slate-650 dark:text-slate-400 border-t border-slate-100 dark:border-slate-800/50 space-y-2">
                      {analysis?.code_patterns && analysis.code_patterns.length > 0 ? (
                        analysis.code_patterns.map((pattern) => (
                          <div key={pattern} className="flex items-center space-x-2">
                            <span className="w-1.5 h-1.5 rounded-full bg-primary-500 shrink-0" />
                            <span>{pattern}</span>
                          </div>
                        ))
                      ) : (
                        <span className="text-slate-400 dark:text-slate-500 italic">Not detected</span>
                      )}
                    </div>
                  )}
                </div>

                {/* 6. Integration Points */}
                <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800/85 rounded-xl overflow-hidden shadow-sm transition">
                  <button
                    onClick={() => toggleSection('integrations')}
                    className="w-full flex items-center justify-between px-6 py-4 hover:bg-slate-50 dark:hover:bg-slate-800/20 text-left font-bold text-sm text-slate-800 dark:text-slate-200"
                  >
                    <div className="flex items-center space-x-2">
                      <Share2 className="w-4.5 h-4.5 text-primary-500" />
                      <span>Integration Points</span>
                    </div>
                    {expanded.integrations ? <ChevronUp className="w-4.5 h-4.5" /> : <ChevronDown className="w-4.5 h-4.5" />}
                  </button>
                  {expanded.integrations && (
                    <div className="px-6 pb-5 pt-3 text-sm text-slate-650 dark:text-slate-400 border-t border-slate-100 dark:border-slate-800/50 space-y-2">
                      {analysis?.integration_points && analysis.integration_points.length > 0 ? (
                        analysis.integration_points.map((integration) => (
                          <div key={integration} className="flex items-center space-x-2">
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
                            <span>{integration}</span>
                          </div>
                        ))
                      ) : (
                        <span className="text-slate-400 dark:text-slate-500 italic">Not detected</span>
                      )}
                    </div>
                  )}
                </div>

                {/* 7. Dependencies */}
                <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800/85 rounded-xl overflow-hidden shadow-sm transition">
                  <button
                    onClick={() => toggleSection('deps')}
                    className="w-full flex items-center justify-between px-6 py-4 hover:bg-slate-50 dark:hover:bg-slate-800/20 text-left font-bold text-sm text-slate-800 dark:text-slate-200"
                  >
                    <div className="flex items-center space-x-2">
                      <Boxes className="w-4.5 h-4.5 text-primary-500" />
                      <span>Dependencies</span>
                    </div>
                    {expanded.deps ? <ChevronUp className="w-4.5 h-4.5" /> : <ChevronDown className="w-4.5 h-4.5" />}
                  </button>
                  {expanded.deps && (
                    <div className="px-6 pb-5 pt-3 border-t border-slate-100 dark:border-slate-800/50">
                      {analysis?.dependencies && analysis.dependencies.length > 0 ? (
                        <div className="flex flex-wrap gap-1.5">
                          {analysis.dependencies.map((dep) => (
                            <span
                              key={dep}
                              className="px-2 py-0.5 text-[10px] font-semibold bg-slate-100 dark:bg-slate-800 text-slate-650 dark:text-slate-400 rounded border border-slate-200 dark:border-slate-700/60"
                            >
                              {dep}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span className="text-sm text-slate-400 dark:text-slate-500 italic">Not detected</span>
                      )}
                    </div>
                  )}
                </div>

              </div>

            </div>

            {/* Right Column: Languages distribution */}
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800/85 rounded-xl p-6 shadow-sm space-y-4 h-fit">
              <h3 className="text-sm font-bold text-slate-800 dark:text-slate-200 uppercase tracking-widest border-b border-slate-100 dark:border-slate-800 pb-2">
                Languages
              </h3>
              
              {Object.keys(languages).length > 0 ? (
                <div className="space-y-4">
                  {/* Progress Bar composite */}
                  <div className="h-3 w-full rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden flex">
                    {Object.entries(languages).map(([lang, percentage], index) => {
                      const colors = ['bg-primary-500', 'bg-emerald-500', 'bg-amber-500', 'bg-rose-500', 'bg-sky-500', 'bg-indigo-500'];
                      const colorClass = colors[index % colors.length];
                      return (
                        <div
                          key={lang}
                          className={`${colorClass} h-full`}
                          style={{ width: `${percentage}%` }}
                          title={`${lang}: ${percentage}%`}
                        />
                      );
                    })}
                  </div>

                  {/* Legends list */}
                  <div className="space-y-2">
                    {Object.entries(languages).map(([lang, percentage], index) => {
                      const colors = ['bg-primary-500', 'bg-emerald-500', 'bg-amber-500', 'bg-rose-500', 'bg-sky-500', 'bg-indigo-500'];
                      const dotColor = colors[index % colors.length];
                      return (
                        <div key={lang} className="flex items-center justify-between text-xs font-medium">
                          <div className="flex items-center space-x-2">
                            <span className={`w-2.5 h-2.5 rounded-full ${dotColor}`} />
                            <span className="text-slate-700 dark:text-slate-300">{lang}</span>
                          </div>
                          <span className="text-slate-500 dark:text-slate-400 font-bold">{percentage}%</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : (
                <p className="text-xs text-slate-400 dark:text-slate-500 text-center py-6">
                  No language byte data returned.
                </p>
              )}
            </div>

          </div>
        )}

        {/* T2. Structure Tab */}
        {activeTab === 'structure' && (
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800/85 rounded-xl p-6 shadow-sm">
            <h3 className="text-sm font-bold text-slate-800 dark:text-slate-200 uppercase tracking-widest border-b border-slate-100 dark:border-slate-800 pb-3 mb-4">
              File Tree Structure
            </h3>
            
            {file_structure.length > 0 ? (
              <div className="font-mono text-xs text-slate-600 dark:text-slate-300 space-y-2 max-h-[600px] overflow-y-auto pr-4">
                {file_structure.map((item) => {
                  const parts = item.path.split('/');
                  const depth = parts.length - 1;
                  const name = parts[parts.length - 1];
                  const isFolder = item.type === 'tree';

                  return (
                    <div
                      key={item.path}
                      className="flex items-center space-x-2 py-0.5 hover:bg-slate-50 dark:hover:bg-slate-800/40 rounded transition"
                      style={{ paddingLeft: `${depth * 16}px` }}
                    >
                      {isFolder ? (
                        <Folder className="w-4 h-4 text-primary-500 dark:text-primary-400 shrink-0" />
                      ) : (
                        <File className="w-4 h-4 text-slate-400 dark:text-slate-500 shrink-0" />
                      )}
                      <span className={isFolder ? 'font-bold text-slate-800 dark:text-slate-200' : ''}>
                        {name}
                      </span>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-xs text-slate-400 dark:text-slate-500 text-center py-12">
                Empty file structure list returned.
              </p>
            )}
          </div>
        )}

        {/* T3. Commits Tab */}
        {activeTab === 'commits' && (
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800/85 rounded-xl p-6 shadow-sm space-y-6">
            <h3 className="text-sm font-bold text-slate-800 dark:text-slate-200 uppercase tracking-widest border-b border-slate-100 dark:border-slate-800 pb-2">
              Recent Commits
            </h3>

            {commits.length > 0 ? (
              <div className="space-y-8 relative pl-4 border-l border-slate-200 dark:border-slate-855 ml-4 py-2">
                {(() => {
                  const formatDateHeader = (isoString: string) => {
                    try {
                      const date = new Date(isoString);
                      return date.toLocaleDateString('en-US', {
                        month: 'short',
                        day: 'numeric',
                        year: 'numeric'
                      });
                    } catch (e) {
                      return 'Unknown Date';
                    }
                  };

                  const groups: Record<string, typeof commits> = {};
                  commits.forEach((commit) => {
                    const groupKey = formatDateHeader(commit.date);
                    if (!groups[groupKey]) {
                      groups[groupKey] = [];
                    }
                    groups[groupKey].push(commit);
                  });

                  return Object.entries(groups).map(([dateKey, groupCommits]) => (
                    <div key={dateKey} className="space-y-4 relative">
                      <div className="absolute -left-[21px] top-1 w-2.5 h-2.5 rounded-full bg-slate-350 dark:bg-slate-700 border border-white dark:border-slate-900" />
                      <div className="text-xs font-bold text-slate-400 dark:text-slate-500">
                        Commits on {dateKey}
                      </div>

                      <div className="space-y-3 pl-2">
                        {groupCommits.map((commit) => (
                          <div
                            key={commit.sha}
                            className="bg-slate-50/50 dark:bg-slate-900/40 hover:bg-slate-100/50 dark:hover:bg-slate-800/20 p-4 border border-slate-150 dark:border-slate-800 rounded-lg flex items-center justify-between gap-4 transition group"
                          >
                            <div className="space-y-1.5 min-w-0">
                              <p className="font-semibold text-sm text-slate-850 dark:text-slate-200 leading-snug truncate">
                                {commit.message}
                              </p>
                              <div className="flex items-center space-x-2 text-xs text-slate-400 dark:text-slate-500">
                                <div className="w-4 h-4 rounded-full bg-primary-100 dark:bg-primary-950/40 text-primary-600 dark:text-primary-400 flex items-center justify-center font-extrabold text-[9px] border border-primary-200/60 dark:border-primary-900/50">
                                  {commit.author ? commit.author.substring(0, 1).toUpperCase() : 'U'}
                                </div>
                                <span className="font-bold text-slate-600 dark:text-slate-400">
                                  {commit.author}
                                </span>
                                <span>committed {getRelativeTime(commit.date)}</span>
                              </div>
                            </div>

                            <div className="shrink-0 flex items-center space-x-1">
                              <span className="font-mono text-xs bg-slate-100 dark:bg-slate-800 text-slate-650 dark:text-slate-400 px-2.5 py-1 rounded border border-slate-200 dark:border-slate-700">
                                {commit.sha.substring(0, 7)}
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ));
                })()}
              </div>
            ) : (
              <p className="text-xs text-slate-400 dark:text-slate-500 text-center py-12">
                No commits found in the repository.
              </p>
            )}
          </div>
        )}

        {/* T4. Issues Tab */}
        {activeTab === 'issues' && (
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800/85 rounded-xl p-6 shadow-sm space-y-6">
            
            <div className="flex flex-col sm:flex-row justify-between sm:items-center gap-4 border-b border-slate-100 dark:border-slate-800 pb-4">
              <h3 className="text-sm font-bold text-slate-800 dark:text-slate-200 uppercase tracking-widest">
                Repository Issues
              </h3>
              
              <div className="flex items-center space-x-1.5 bg-slate-100 dark:bg-slate-805 p-0.5 rounded-lg border border-slate-205 dark:border-slate-705 text-xs">
                {(['all', 'open', 'closed'] as const).map((filter) => (
                  <button
                    key={filter}
                    onClick={() => setIssueFilter(filter)}
                    className={`px-3 py-1 rounded-md capitalize font-semibold transition ${
                      issueFilter === filter
                        ? 'bg-white dark:bg-slate-950 text-primary-600 dark:text-primary-400 shadow-sm'
                        : 'text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
                    }`}
                  >
                    {filter}
                  </button>
                ))}
              </div>
            </div>

            {filteredIssues.length > 0 ? (
              <div className="divide-y divide-slate-100 dark:divide-slate-800/60">
                {filteredIssues.map((issue) => (
                  <div key={issue.number} className="py-4.5 first:pt-0 last:pb-0 flex items-start space-x-3.5 text-sm">
                    <div className="shrink-0 mt-0.5">
                      {issue.state === 'open' ? (
                        <AlertCircle className="w-4 h-4 text-emerald-500" />
                      ) : (
                        <CheckCircle className="w-4 h-4 text-purple-500" />
                      )}
                    </div>

                    <div className="space-y-1.5 min-w-0 flex-1">
                      <div className="flex items-start justify-between gap-4">
                        <h4 className="font-semibold text-slate-900 dark:text-slate-100 hover:text-primary-600 dark:hover:text-primary-400 transition leading-snug">
                          {issue.title}
                        </h4>
                        <span className="text-xs text-slate-400 shrink-0 font-medium">
                          #{issue.number}
                        </span>
                      </div>

                      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-slate-400 dark:text-slate-500">
                        <span>by {issue.author}</span>
                        <span>&bull;</span>
                        <span>opened {formatDate(issue.created_at)}</span>
                        
                        {issue.labels.length > 0 && (
                          <>
                            <span>&bull;</span>
                            <div className="flex flex-wrap gap-1">
                              {issue.labels.map((label) => (
                                <span
                                  key={label}
                                  className="px-1.5 py-0.5 rounded-full text-[9px] font-bold bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 border border-slate-200 dark:border-slate-700/60"
                                >
                                  {label}
                                </span>
                              ))}
                            </div>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-400 dark:text-slate-500 text-center py-12">
                No issues match the selected state.
              </p>
            )}
          </div>
        )}

        {/* T5. Pull Requests Tab */}
        {activeTab === 'pull-requests' && (
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-850 rounded-xl p-6 shadow-sm space-y-6">
            
            <div className="flex flex-col sm:flex-row justify-between sm:items-center gap-4 border-b border-slate-100 dark:border-slate-800 pb-4">
              <h3 className="text-sm font-bold text-slate-800 dark:text-slate-200 uppercase tracking-widest">
                Repository Pull Requests
              </h3>
              
              <div className="flex items-center space-x-1.5 bg-slate-100 dark:bg-slate-805 p-0.5 rounded-lg border border-slate-205 dark:border-slate-705 text-xs">
                {(['all', 'open', 'closed', 'merged'] as const).map((filter) => (
                  <button
                    key={filter}
                    onClick={() => setPrFilter(filter)}
                    className={`px-3 py-1 rounded-md capitalize font-semibold transition ${
                      prFilter === filter
                        ? 'bg-white dark:bg-slate-950 text-primary-600 dark:text-primary-400 shadow-sm'
                        : 'text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
                    }`}
                  >
                    {filter}
                  </button>
                ))}
              </div>
            </div>

            {filteredPRs.length > 0 ? (
              <div className="divide-y divide-slate-100 dark:divide-slate-800/60">
                {filteredPRs.map((pr) => (
                  <div key={pr.number} className="py-4.5 first:pt-0 last:pb-0 flex items-start space-x-3.5 text-sm">
                    <div className="shrink-0 mt-0.5">
                      {pr.is_merged ? (
                        <GitPullRequest className="w-4 h-4 text-purple-500" />
                      ) : pr.state === 'open' ? (
                        <GitPullRequest className="w-4 h-4 text-emerald-500" />
                      ) : (
                        <GitPullRequest className="w-4 h-4 text-red-500" />
                      )}
                    </div>

                    <div className="space-y-1.5 min-w-0 flex-1">
                      <div className="flex items-start justify-between gap-4">
                        <h4 className="font-semibold text-slate-900 dark:text-slate-100 hover:text-primary-600 dark:hover:text-primary-400 transition leading-snug">
                          {pr.title}
                        </h4>
                        <span className="text-xs text-slate-400 shrink-0 font-medium">
                          #{pr.number}
                        </span>
                      </div>

                      <div className="flex items-center space-x-2 text-xs text-slate-400 dark:text-slate-500">
                        <span>by {pr.author}</span>
                        <span>&bull;</span>
                        <span>opened {formatDate(pr.created_at)}</span>
                        <span>&bull;</span>
                        <span className={`font-semibold capitalize ${
                          pr.is_merged
                            ? 'text-purple-500'
                            : pr.state === 'open'
                            ? 'text-emerald-500'
                            : 'text-red-500'
                        }`}>
                          {pr.is_merged ? 'merged' : pr.state}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-400 dark:text-slate-500 text-center py-12">
                No pull requests match the selected state.
              </p>
            )}
          </div>
        )}

      </div>
    </div>
  );
};
export default RepositoryDetail;
