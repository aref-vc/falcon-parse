import React, { useState, useEffect } from 'react';
import { Clock, CheckCircle, XCircle, AlertCircle, StopCircle } from 'lucide-react';
import { cancelJob } from '../services/api';

const ProgressTracker = ({ jobId, status, message, processingTime, onUpdate }) => {
  const [progress, setProgress] = useState({});
  const [showCancel, setShowCancel] = useState(false);
  const [stuckWarning, setStuckWarning] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [ws, setWs] = useState(null);

  useEffect(() => {
    if (!jobId) return;

    // Prevent rapid reconnection attempts
    const connectionDelay = setTimeout(() => {
      const websocket = new WebSocket(`ws://localhost:8010/ws/${jobId}`);
      setWs(websocket);
    
    websocket.onopen = () => {
      console.log('WebSocket connected for job:', jobId);
    };
    
    websocket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setProgress(data);
      
      if (onUpdate) {
        onUpdate(data);
      }
      
      // Show cancel option if job is taking too long or appears stuck
      const progressAge = data.progress_age || 0;
      if (progressAge > 30 || data.is_stuck) {  // 30 seconds without progress
        setStuckWarning(true);
        setShowCancel(true);
      }
      
      // Hide cancel for completed/failed jobs
      if (data.stage === 'completed' || data.stage === 'failed' || data.stage === 'cancelled') {
        setShowCancel(false);
        setStuckWarning(false);
      }
    };

    websocket.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    websocket.onclose = () => {
      console.log('WebSocket disconnected');
    };

      // Auto-detect stuck jobs - show cancel after 45 seconds
      const stuckTimer = setTimeout(() => {
        if (status === 'processing') {
          setStuckWarning(true);
          setShowCancel(true);
        }
      }, 45000);

      return () => {
        websocket.close();
        clearTimeout(stuckTimer);
      };
    }, 100); // Small delay to prevent rapid reconnects

    return () => {
      clearTimeout(connectionDelay);
      if (ws) {
        ws.close();
      }
    };
  }, [jobId, status, onUpdate]);

  const handleCancel = async () => {
    if (!jobId || cancelling) return;
    
    setCancelling(true);
    try {
      await cancelJob(jobId);
      setProgress({ 
        message: "🛑 Job cancelled by user", 
        stage: "cancelled",
        progress_age: 0
      });
      setShowCancel(false);
      setStuckWarning(false);
    } catch (error) {
      console.error('Cancel failed:', error);
      alert('Failed to cancel job. Please try again.');
    } finally {
      setCancelling(false);
    }
  };

  const getStatusInfo = () => {
    const currentStage = progress.stage || status;
    const currentMessage = progress.message || message;
    
    // Enhanced stage-based progress calculation
    const stageProgress = {
      'pending': 5,
      'initializing': 10,
      'loading': 25,
      'loading_slow': 30,
      'content_loaded': 45,
      'dynamic_content': 55,
      'ai_processing': 65,
      'ai_thinking': 75,
      'ai_completed': 85,
      'data_processing': 90,
      'exporting': 95,
      'completed': 100,
      'cancelled': 0,
      'timeout': 0,
      'failed': 0
    };
    
    let progressPercent = stageProgress[currentStage] || 20;
    
    switch (currentStage) {
      case 'pending':
      case 'initializing':
        return {
          icon: Clock,
          color: 'var(--color-warning)',
          text: 'Initializing',
          progress: progressPercent
        };
      case 'loading':
      case 'loading_slow':
      case 'content_loaded':
      case 'dynamic_content':
        return {
          icon: Clock,
          color: 'var(--color-accent)',
          text: 'Loading Content',
          progress: progressPercent
        };
      case 'ai_processing':
      case 'ai_thinking':
      case 'ai_completed':
        return {
          icon: Clock,
          color: 'var(--color-accent)',
          text: 'AI Processing',
          progress: progressPercent
        };
      case 'data_processing':
      case 'exporting':
        return {
          icon: Clock,
          color: 'var(--color-accent)',
          text: 'Finalizing',
          progress: progressPercent
        };
      case 'completed':
        return {
          icon: CheckCircle,
          color: 'var(--color-success)',
          text: 'Completed',
          progress: 100
        };
      case 'cancelled':
        return {
          icon: StopCircle,
          color: 'var(--color-warning)',
          text: 'Cancelled',
          progress: 0
        };
      case 'timeout':
        return {
          icon: XCircle,
          color: 'var(--color-error)',
          text: 'Timed Out',
          progress: 0
        };
      case 'failed':
        return {
          icon: XCircle,
          color: 'var(--color-error)',
          text: 'Failed',
          progress: 0
        };
      default:
        return {
          icon: Clock,
          color: 'var(--color-accent)',
          text: 'Processing',
          progress: progressPercent
        };
    }
  };

  const statusInfo = getStatusInfo();
  const StatusIcon = statusInfo.icon;

  return (
    <div className="card">
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 'var(--space-md)' }}>
        <StatusIcon 
          size={24} 
          style={{ color: statusInfo.color, marginRight: 'var(--space-sm)' }} 
        />
        <h3 style={{ margin: 0, color: statusInfo.color }}>
          {statusInfo.text}
        </h3>
      </div>

      {statusInfo.text !== 'Failed' && statusInfo.text !== 'Timed Out' && statusInfo.text !== 'Cancelled' && (
        <div className="progress-container">
          <div className="progress-bar">
            <div 
              className="progress-fill"
              style={{ width: `${statusInfo.progress}%` }}
            />
          </div>
          <div className="progress-text">
            {statusInfo.progress}% Complete
          </div>
        </div>
      )}

      {(progress.message || message) && (
        <div className={`status-message ${
          statusInfo.text === 'Failed' || statusInfo.text === 'Timed Out' ? 'status-error' : 
          statusInfo.text === 'Completed' ? 'status-success' : 
          'status-warning'
        }`}>
          {progress.message || message}
        </div>
      )}
      
      {stuckWarning && progress.stage !== 'completed' && progress.stage !== 'failed' && (
        <div className="stuck-warning" style={{
          background: 'rgba(255, 193, 7, 0.1)',
          border: '1px solid var(--color-warning)',
          borderRadius: 'var(--border-radius)',
          padding: 'var(--space-sm)',
          margin: 'var(--space-sm) 0',
          fontSize: '0.875rem'
        }}>
          ⚠️ Job may be stuck - no progress for {Math.floor(progress.progress_age || 0)}s
        </div>
      )}
      
      {showCancel && progress.stage !== 'completed' && progress.stage !== 'failed' && progress.stage !== 'cancelled' && (
        <div style={{ marginTop: 'var(--space-md)', textAlign: 'center' }}>
          <button 
            onClick={handleCancel}
            disabled={cancelling}
            className="btn btn-warning"
            style={{
              background: 'var(--color-warning)',
              color: 'white',
              border: 'none',
              padding: 'var(--space-sm) var(--space-md)',
              borderRadius: 'var(--border-radius)',
              cursor: cancelling ? 'not-allowed' : 'pointer',
              opacity: cancelling ? 0.7 : 1
            }}
          >
            {cancelling ? '⏳ Cancelling...' : '🛑 Cancel Job'}
          </button>
        </div>
      )}
      
      {progress.progress_age > 0 && progress.stage !== 'completed' && progress.stage !== 'failed' && (
        <div className="progress-details" style={{
          textAlign: 'center',
          color: 'var(--color-secondary)',
          fontSize: '0.75rem',
          marginTop: 'var(--space-sm)'
        }}>
          Stage: {progress.stage || status} | Last update: {Math.floor(progress.progress_age || 0)}s ago
        </div>
      )}

      {processingTime && (
        <div style={{ 
          textAlign: 'center', 
          color: 'var(--color-secondary)', 
          fontSize: '0.875rem',
          marginTop: 'var(--space-md)'
        }}>
          Processing time: {processingTime.toFixed(2)} seconds
        </div>
      )}
    </div>
  );
};

export default ProgressTracker;