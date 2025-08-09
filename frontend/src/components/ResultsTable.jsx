import React from 'react';
import { Download } from 'lucide-react';

const ResultsTable = ({ data, columns, rowCount, onDownload }) => {
  if (!data || data.length === 0) {
    return (
      <div className="card">
        <div style={{ textAlign: 'center', padding: 'var(--space-2xl)' }}>
          <p style={{ color: 'var(--color-secondary)' }}>
            No data extracted. The page might not contain the requested information.
          </p>
        </div>
      </div>
    );
  }

  const handleCellClick = (cellContent) => {
    // Copy cell content to clipboard on click
    if (navigator.clipboard && cellContent) {
      navigator.clipboard.writeText(String(cellContent)).then(() => {
        // You could add a toast notification here
        console.log('Copied to clipboard:', cellContent);
      });
    }
  };

  const formatCellValue = (value) => {
    if (value === null || value === undefined) {
      return '';
    }
    
    if (typeof value === 'object') {
      return JSON.stringify(value);
    }
    
    return String(value);
  };

  return (
    <div>
      {/* Results Summary */}
      <div className="results-summary">
        <div className="summary-stat">
          <h3>{rowCount || data.length}</h3>
          <p>Rows Extracted</p>
        </div>
        <div className="summary-stat">
          <h3>{columns ? columns.length : Object.keys(data[0] || {}).length}</h3>
          <p>Columns Found</p>
        </div>
        <div className="summary-stat">
          <h3>{data.filter(row => 
            Object.values(row).some(val => val !== null && val !== undefined && val !== '')
          ).length}</h3>
          <p>Valid Entries</p>
        </div>
      </div>

      {/* Export Actions */}
      <div className="export-actions">
        <button
          onClick={() => onDownload('json')}
          className="btn btn-download"
        >
          <Download size={16} />
          Download JSON
        </button>
        <button
          onClick={() => onDownload('csv')}
          className="btn btn-download"
        >
          <Download size={16} />
          Download CSV
        </button>
      </div>

      {/* Data Table */}
      <div className="card">
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                {(columns || Object.keys(data[0] || {})).map((column) => (
                  <th key={column} title={column}>
                    {column.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.map((row, index) => (
                <tr key={index}>
                  {(columns || Object.keys(row)).map((column) => (
                    <td 
                      key={column}
                      title={formatCellValue(row[column])}
                      onClick={() => handleCellClick(row[column])}
                      style={{ cursor: row[column] ? 'pointer' : 'default' }}
                    >
                      {formatCellValue(row[column])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        
        <div style={{ 
          padding: 'var(--space-md)', 
          borderTop: '1px solid var(--color-border)',
          background: 'var(--color-light)',
          fontSize: '0.875rem',
          color: 'var(--color-secondary)',
          textAlign: 'center'
        }}>
          Showing {data.length} rows • Click any cell to copy its content
        </div>
      </div>
    </div>
  );
};

export default ResultsTable;