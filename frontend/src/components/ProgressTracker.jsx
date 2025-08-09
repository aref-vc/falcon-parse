import React from 'react';
import { Clock, CheckCircle, XCircle, AlertCircle } from 'lucide-react';

const ProgressTracker = ({ status, message, processingTime }) => {
  const getStatusInfo = () => {
    switch (status) {
      case 'pending':
        return {
          icon: Clock,
          color: 'var(--color-warning)',
          text: 'Queued',
          progress: 10
        };
      case 'processing':
        // Determine progress based on message content
        let progress = 20;
        if (message) {
          const msg = message.toLowerCase();
          if (msg.includes('scraping') || msg.includes('loading content')) progress = 30;
          if (msg.includes('scroll') || msg.includes('pagination')) progress = 50;
          if (msg.includes('analyzing') || msg.includes('ai')) progress = 70;
          if (msg.includes('processing') || msg.includes('cleaning')) progress = 85;
          if (msg.includes('generating') || msg.includes('export')) progress = 95;
        }
        return {
          icon: Clock,
          color: 'var(--color-accent)',
          text: 'Processing',
          progress: progress
        };
      case 'completed':
        return {
          icon: CheckCircle,
          color: 'var(--color-success)',
          text: 'Completed',
          progress: 100
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
          icon: AlertCircle,
          color: 'var(--color-secondary)',
          text: 'Unknown',
          progress: 0
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

      {status !== 'failed' && (
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

      {message && (
        <div className={`status-message ${
          status === 'failed' ? 'status-error' : 
          status === 'completed' ? 'status-success' : 
          'status-warning'
        }`}>
          {message}
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