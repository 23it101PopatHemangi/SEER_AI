export interface Repository {
  id: string;
  project_id: string;
  github_url: string;
  owner: string;
  name: string;
  description?: string;
  default_branch: string;
  primary_language?: string;
  stars: number;
  forks: number;
  open_issues_count: number;
  created_at: string;
  updated_at: string;
  last_pushed_at: string;
  analysis_status?: string;
}

export interface CommitInfo {
  sha: string;
  message: string;
  author?: string;
  date: string;
}

export interface IssueInfo {
  number: number;
  title: string;
  state: string;
  author: string;
  created_at: string;
  updated_at: string;
  labels: string[];
}

export interface PullRequestInfo {
  number: number;
  title: string;
  state: string;
  author: string;
  created_at: string;
  updated_at: string;
  merged_at?: string;
  is_merged: boolean;
}

export interface FileNode {
  path: string;
  type: 'blob' | 'tree';
}

export interface AnalysisInfo {
  technologies: string[];
  architecture_overview?: string;
  key_components: string[];
  api_surface: string[];
  code_patterns: string[];
  integration_points: string[];
  dependencies: string[];
}

export interface RepositoryDetail {
  metadata: Repository;
  languages: Record<string, number>;
  file_structure: FileNode[];
  commits: CommitInfo[];
  issues: IssueInfo[];
  pull_requests: PullRequestInfo[];
  analysis?: AnalysisInfo;
}

const API_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000') + '/api';

export const repositoryService = {
  // Get all repositories connected to a specific project
  async getRepositories(projectId: string): Promise<Repository[]> {
    const res = await fetch(`${API_BASE}/projects/${projectId}/repositories`);
    if (!res.ok) {
      throw new Error('Failed to fetch repositories for project');
    }
    return res.json();
  },

  // Connect a new repository to a project (passing X-User-Email to allow authenticated GitHub App/OAuth usage)
  async connectRepository(projectId: string, githubUrl: string, userEmail?: string): Promise<Repository> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (userEmail) {
      headers['X-User-Email'] = userEmail;
    }

    const res = await fetch(`${API_BASE}/projects/${projectId}/repositories`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        repository_url: githubUrl.trim(),
      }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to connect repository. Make sure it is public and correct.');
    }
    return res.json();
  },

  // Fetch full details of a specific repository on-demand (passing X-User-Email to bypass rate limits using user token)
  async getRepositoryDetail(projectId: string, repositoryId: string, userEmail?: string): Promise<RepositoryDetail> {
    const headers: Record<string, string> = {};
    if (userEmail) {
      headers['X-User-Email'] = userEmail;
    }

    const res = await fetch(`${API_BASE}/projects/${projectId}/repositories/${repositoryId}`, {
      headers,
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to retrieve repository details.');
    }
    return res.json();
  },
};
export default repositoryService;
