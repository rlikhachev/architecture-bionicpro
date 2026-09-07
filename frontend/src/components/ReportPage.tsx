import React, { useCallback, useEffect, useState } from 'react';

const API_URL = process.env.REACT_APP_API_URL || '';

interface SessionInfo {
  authenticated: boolean;
  session_id?: string;
  user_id?: string;
  username?: string;
}

const ReportPage: React.FC = () => {
  const [checking, setChecking] = useState(true);
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reportLink, setReportLink] = useState<string | null>(null);

  const fetchSession = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/auth/session`, {
        credentials: 'include'
      });
      if (response.status === 401) {
        setSession({ authenticated: false });
        return;
      }
      const data: SessionInfo = await response.json();
      setSession(data);
    } catch {
      setSession({ authenticated: false });
    } finally {
      setChecking(false);
    }
  }, []);

  useEffect(() => {
    fetchSession();
  }, [fetchSession]);

  const login = () => {
    window.location.href = `${API_URL}/auth/login`;
  };

  const logout = async () => {
    try {
      await fetch(`${API_URL}/auth/logout`, {
        method: 'POST',
        credentials: 'include'
      });
    } finally {
      setSession({ authenticated: false });
      setReportLink(null);
    }
  };

  const downloadReport = async () => {
    try {
      setLoading(true);
      setError(null);
      setReportLink(null);

      const response = await fetch(`${API_URL}/reports`, {
        credentials: 'include'
      });

      if (response.status === 401) {
        setSession({ authenticated: false });
        setError('Not authenticated');
        return;
      }
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.detail || body?.error || `Request failed with status ${response.status}`);
      }

      const contentType = response.headers.get('content-type') || '';
      if (contentType.includes('application/json')) {
        const body = await response.json();
        if (body.report_url) {
          setReportLink(body.report_url);
        } else {
          const blob = new Blob([JSON.stringify(body, null, 2)], { type: 'application/json' });
          triggerDownload(blob);
        }
      } else {
        const blob = await response.blob();
        triggerDownload(blob);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  const triggerDownload = (blob: Blob) => {
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'report.json';
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };

  if (checking) {
    return <div className="flex items-center justify-center min-h-screen bg-gray-100">Loading...</div>;
  }

  if (!session?.authenticated) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
        <button
          onClick={login}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Login
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
      <div className="p-8 bg-white rounded-lg shadow-md">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold">Usage Reports</h1>
          <span className="ml-6 text-sm text-gray-600">{session.username}</span>
        </div>

        <button
          onClick={downloadReport}
          disabled={loading}
          className={`px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 ${
            loading ? 'opacity-50 cursor-not-allowed' : ''
          }`}
        >
          {loading ? 'Generating Report...' : 'Download Report'}
        </button>

        <button
          onClick={logout}
          className="ml-3 px-4 py-2 bg-gray-500 text-white rounded hover:bg-gray-600"
        >
          Logout
        </button>

        {reportLink && (
          <div className="mt-4 p-4 bg-green-100 text-green-700 rounded break-all">
            <a href={reportLink} target="_blank" rel="noopener noreferrer">
              {reportLink}
            </a>
          </div>
        )}

        {error && (
          <div className="mt-4 p-4 bg-red-100 text-red-700 rounded">
            {error}
          </div>
        )}
      </div>
    </div>
  );
};

export default ReportPage;
