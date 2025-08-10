import React, { useState, useEffect, useRef } from 'react';
import { AlertCircle, Wifi, WifiOff } from 'lucide-react';
import ScrapeForm from './components/ScrapeForm';
import ProgressTracker from './components/ProgressTracker';
import ResultsTable from './components/ResultsTable';
import { apiService } from './services/api';

function App() {
  // State management
  const [isConnected, setIsConnected] = useState(false);
  const [currentJob, setCurrentJob] = useState(null);
  const [jobStatus, setJobStatus] = useState(null);
  const [jobResult, setJobResult] = useState(null);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [liveMessages, setLiveMessages] = useState([]);

  // Refs
  const websocketRef = useRef(null);
  const statusCheckIntervalRef = useRef(null);

  // Check backend health on component mount
  useEffect(() => {
    checkBackendHealth();
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (websocketRef.current) {
        websocketRef.current.close();
      }
      if (statusCheckIntervalRef.current) {
        clearInterval(statusCheckIntervalRef.current);
      }
    };
  }, []);

  const checkBackendHealth = async () => {
    try {
      const health = await apiService.checkHealth();
      setIsConnected(health.status === 'healthy');
      
      if (!health.gemini_api) {
        setError('Warning: Gemini API connection failed. Please check your API key.');
      }
    } catch (error) {
      setIsConnected(false);
      setError(`Backend connection failed: ${error.message}`);
    }
  };

  const handleScrapeSubmit = async (formData) => {
    try {
      setError(null);
      setIsLoading(true);
      setJobResult(null);
      setLiveMessages([]);

      // Create scraping job
      const jobResponse = await apiService.createScrapeJob(
        formData.url,
        formData.dataType,
        formData.customInstructions
      );

      setCurrentJob(jobResponse.job_id);
      setJobStatus({
        status: 'pending',
        message: 'Job created and queued for processing'
      });

      // Set up WebSocket for real-time updates
      setupWebSocket(jobResponse.job_id);

      // Set up status polling as backup
      startStatusPolling(jobResponse.job_id);

    } catch (error) {
      setError(error.message);
      setIsLoading(false);
    }
  };

  const setupWebSocket = (jobId) => {
    const onMessage = (data) => {
      setLiveMessages(prev => [...prev, {
        timestamp: new Date().toLocaleTimeString(),
        message: data.message
      }]);
    };

    const onError = (error) => {
      console.warn('WebSocket error, falling back to polling:', error);
    };

    websocketRef.current = apiService.connectWebSocket(jobId, onMessage, onError);
  };

  const startStatusPolling = (jobId) => {
    statusCheckIntervalRef.current = setInterval(async () => {
      try {
        const status = await apiService.getJobStatus(jobId);
        setJobStatus(status);

        if (status.status === 'completed' || status.status === 'failed') {
          clearInterval(statusCheckIntervalRef.current);
          setIsLoading(false);

          if (websocketRef.current) {
            websocketRef.current.close();
          }

          if (status.status === 'completed') {
            // Fetch the result
            const result = await apiService.getJobResult(jobId);
            setJobResult(result);
          } else {
            setError(status.message || 'Job failed');
          }
        }
      } catch (error) {
        console.error('Status polling error:', error);
      }
    }, 2000); // Check every 2 seconds
  };

  const handleDownload = async (format) => {
    if (!currentJob) return;

    try {
      await apiService.downloadResult(currentJob, format);
    } catch (error) {
      setError(`Download failed: ${error.message}`);
    }
  };

  const resetApp = () => {
    setCurrentJob(null);
    setJobStatus(null);
    setJobResult(null);
    setError(null);
    setIsLoading(false);
    setLiveMessages([]);
    
    if (websocketRef.current) {
      websocketRef.current.close();
    }
    if (statusCheckIntervalRef.current) {
      clearInterval(statusCheckIntervalRef.current);
    }
  };

  return (
    <div className="container">
      {/* Header */}
      <header className="header">
        <h1>🦅 Falcon Parse</h1>
        <p>AI-powered web scraping and data extraction tool</p>
        
        {/* Connection Status */}
        <div style={{ 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'center',
          marginTop: 'var(--space-md)',
          gap: 'var(--space-sm)'
        }}>
          {isConnected ? (
            <>
              <Wifi size={16} style={{ color: 'var(--color-success)' }} />
              <span style={{ color: 'var(--color-success)', fontSize: '0.875rem' }}>
                Backend Connected
              </span>
            </>
          ) : (
            <>
              <WifiOff size={16} style={{ color: 'var(--color-error)' }} />
              <span style={{ color: 'var(--color-error)', fontSize: '0.875rem' }}>
                Backend Disconnected
              </span>
            </>
          )}
        </div>
      </header>

      {/* Error Display */}
      {error && (
        <div className="status-message status-error">
          <AlertCircle size={16} style={{ marginRight: 'var(--space-sm)' }} />
          {error}
        </div>
      )}

      {/* Main Content */}
      {!currentJob ? (
        // Initial form
        <ScrapeForm 
          onSubmit={handleScrapeSubmit} 
          isLoading={isLoading}
        />
      ) : (
        <>
          {/* Progress Tracker */}
          {jobStatus && (
            <ProgressTracker 
              jobId={currentJob}
              status={jobStatus.status}
              message={jobStatus.message}
              processingTime={jobResult?.processing_time}
              onUpdate={(progressData) => {
                // Handle real-time progress updates
                setJobStatus({
                  status: progressData.stage === 'completed' ? 'completed' : 
                         progressData.stage === 'failed' ? 'failed' : 
                         progressData.stage === 'cancelled' ? 'failed' :
                         progressData.stage === 'timeout' ? 'failed' : 'processing',
                  message: progressData.message
                });
                
                // Handle job completion/failure from WebSocket
                if (progressData.stage === 'completed' || 
                    progressData.stage === 'failed' || 
                    progressData.stage === 'cancelled' ||
                    progressData.stage === 'timeout') {
                  setIsLoading(false);
                  
                  if (websocketRef.current) {
                    websocketRef.current.close();
                  }
                  
                  if (statusCheckIntervalRef.current) {
                    clearInterval(statusCheckIntervalRef.current);
                  }
                  
                  // Fetch result if completed
                  if (progressData.stage === 'completed') {
                    apiService.getJobResult(currentJob)
                      .then(result => setJobResult(result))
                      .catch(err => setError(`Failed to fetch result: ${err.message}`));
                  }
                }
              }}
            />
          )}

          {/* Live Messages */}
          {liveMessages.length > 0 && (
            <div className="card">
              <h3 style={{ marginBottom: 'var(--space-md)', color: 'var(--color-primary)' }}>
                Live Updates
              </h3>
              <div style={{ 
                maxHeight: '200px', 
                overflowY: 'auto',
                background: 'var(--color-light)',
                padding: 'var(--space-md)',
                borderRadius: 'var(--radius-md)',
                fontSize: '0.875rem',
                fontFamily: 'var(--font-mono)'
              }}>
                {liveMessages.map((msg, index) => (
                  <div key={index} style={{ marginBottom: 'var(--space-xs)' }}>
                    <span style={{ color: 'var(--color-secondary)' }}>
                      [{msg.timestamp}]
                    </span>{' '}
                    {msg.message}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Results */}
          {jobResult && jobResult.status === 'completed' && (
            <ResultsTable 
              data={jobResult.data}
              columns={jobResult.columns}
              rowCount={jobResult.row_count}
              onDownload={handleDownload}
            />
          )}

          {/* Action Buttons */}
          <div style={{ 
            display: 'flex', 
            gap: 'var(--space-md)', 
            justifyContent: 'center',
            marginTop: 'var(--space-xl)'
          }}>
            <button 
              onClick={resetApp}
              className="btn btn-secondary"
            >
              Start New Extraction
            </button>
            {!isLoading && (
              <button 
                onClick={checkBackendHealth}
                className="btn btn-secondary"
              >
                Check Connection
              </button>
            )}
          </div>
        </>
      )}

      {/* Footer */}
      <footer style={{ 
        textAlign: 'center', 
        marginTop: 'var(--space-2xl)',
        padding: 'var(--space-lg)',
        color: 'var(--color-secondary)',
        fontSize: '0.875rem'
      }}>
        <p>
          Powered by <strong>Gemini AI</strong> • 
          Built with <strong>React</strong> + <strong>FastAPI</strong>
        </p>
      </footer>
    </div>
  );
}

export default App;